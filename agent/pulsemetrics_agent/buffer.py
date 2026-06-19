import json
import os
import time
from pathlib import Path


class DiskBuffer:
    """Persists log batches to disk so they survive network failures."""

    def __init__(self, buffer_dir: str) -> None:
        self.dir = Path(buffer_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def write(self, batch: list[str]) -> Path:
        ts = int(time.time() * 1000)
        path = self.dir / f"batch_{ts}.json"
        path.write_text(json.dumps(batch))
        return path

    def list_pending(self) -> list[Path]:
        return sorted(self.dir.glob("batch_*.json"))

    def delete(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def total_size_mb(self) -> float:
        total = sum(p.stat().st_size for p in self.dir.glob("batch_*.json") if p.exists())
        return total / (1024 * 1024)
