FROM python:3.11-slim

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
# Copy the app package so hatchling can resolve the editable install
COPY app/ ./app/
# Embeddings run on onnxruntime (CPU), not PyTorch — no torch/CUDA pulled in.
RUN pip install --no-cache-dir -e ".[dev]"

# Copy the rest of the project (alembic, scripts, templates, etc.)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
