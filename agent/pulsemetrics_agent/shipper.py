import json
import time
from pathlib import Path

import httpx

from pulsemetrics_agent.buffer import DiskBuffer


class Shipper:
    """Sends batches to the PulseMetrics ingestion endpoint."""

    def __init__(self, url: str, api_key: str, buffer: DiskBuffer) -> None:
        self.url = url.rstrip("/") + "/api/v1/logs/ingest"
        self.api_key = api_key
        self.buffer = buffer
        self._client = httpx.Client(timeout=10, headers={"X-Api-Key": api_key})

    def ship(self, lines: list[str]) -> bool:
        """Try to ship lines. Returns True on success, buffers on failure."""
        entries = [{"message": line, "level": "INFO"} for line in lines if line.strip()]
        if not entries:
            return True
        try:
            r = self._client.post(self.url, json={"entries": entries})
            r.raise_for_status()
            return True
        except Exception:
            self.buffer.write(lines)
            return False

    def retry_buffered(self) -> int:
        """Retry all buffered batches. Returns count of successfully shipped batches."""
        shipped = 0
        for path in self.buffer.list_pending():
            try:
                data = json.loads(path.read_text())
                entries = [{"message": line, "level": "INFO"} for line in data if line.strip()]
                r = self._client.post(self.url, json={"entries": entries})
                r.raise_for_status()
                self.buffer.delete(path)
                shipped += 1
            except Exception:
                break  # Network still down, stop retrying
        return shipped

    def close(self) -> None:
        self._client.close()
