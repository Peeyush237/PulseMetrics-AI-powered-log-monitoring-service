"""CPU text embeddings via ONNX Runtime — no PyTorch.

We run ``sentence-transformers/all-MiniLM-L6-v2`` through onnxruntime instead of
PyTorch. The output is identical in shape and meaning (384-dim, L2-normalized),
so the pgvector schema, the HNSW index, and the clustering logic are unchanged —
only the inference backend is lighter (onnxruntime ~50MB vs the torch stack ~750MB+).

sentence-transformers itself is intentionally NOT a dependency: it hard-requires
torch even when using its ONNX backend, which would defeat the purpose.
"""
from __future__ import annotations

import threading

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from transformers import AutoTokenizer

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Truncate to the model's training window. MiniLM was trained on 256 tokens;
# log lines are short, so this is rarely hit but bounds worst-case latency.
_MAX_TOKENS = 256

_lock = threading.Lock()
_session: ort.InferenceSession | None = None
_tokenizer = None  # type: ignore[var-annotated]


def _load() -> tuple[ort.InferenceSession, object]:
    """Lazily download the ONNX model + tokenizer and build a session (per worker process)."""
    global _session, _tokenizer
    if _session is None or _tokenizer is None:
        with _lock:
            if _session is None or _tokenizer is None:
                model_id = settings.embedding_model
                logger.info("loading_onnx_embedder", model=model_id)
                onnx_path = hf_hub_download(repo_id=model_id, filename="onnx/model.onnx")
                _tokenizer = AutoTokenizer.from_pretrained(model_id)
                _session = ort.InferenceSession(
                    onnx_path, providers=["CPUExecutionProvider"]
                )
    return _session, _tokenizer  # type: ignore[return-value]


def _mean_pool(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    """Mask-aware mean pooling over the token dimension (matches MiniLM's pooling layer)."""
    mask = attention_mask[..., None].astype(np.float32)  # [batch, seq, 1]
    summed = (token_embeddings * mask).sum(axis=1)  # [batch, dim]
    counts = np.clip(mask.sum(axis=1), a_min=1e-9, a_max=None)
    return summed / counts


def embed(text: str) -> np.ndarray:
    """Return a 384-dim, L2-normalized embedding as a float32 ndarray."""
    session, tokenizer = _load()
    encoded = tokenizer(
        text,
        padding=True,
        truncation=True,
        max_length=_MAX_TOKENS,
        return_tensors="np",
    )
    # Feed only the inputs the exported graph actually declares (e.g. some
    # exports omit token_type_ids); cast to int64, which onnxruntime expects.
    wanted = {i.name for i in session.get_inputs()}
    inputs = {
        name: encoded[name].astype(np.int64)
        for name in wanted
        if name in encoded
    }
    token_embeddings = session.run(None, inputs)[0]  # [1, seq, dim]
    pooled = _mean_pool(token_embeddings, encoded["attention_mask"])  # [1, dim]
    norm = np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), a_min=1e-12, a_max=None)
    normalized = pooled / norm
    return normalized[0].astype(np.float32)
