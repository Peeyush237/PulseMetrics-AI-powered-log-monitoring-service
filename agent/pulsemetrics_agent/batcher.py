import time
from collections import deque


class Batcher:
    """Accumulates lines and flushes when size or time threshold is hit."""

    def __init__(self, batch_size: int = 100, batch_interval: float = 5.0) -> None:
        self.batch_size = batch_size
        self.batch_interval = batch_interval
        self._buf: deque[str] = deque()
        self._last_flush = time.monotonic()

    def add(self, line: str) -> None:
        self._buf.append(line)

    def should_flush(self) -> bool:
        if len(self._buf) >= self.batch_size:
            return True
        if self._buf and (time.monotonic() - self._last_flush) >= self.batch_interval:
            return True
        return False

    def flush(self) -> list[str]:
        items = list(self._buf)
        self._buf.clear()
        self._last_flush = time.monotonic()
        return items

    def __len__(self) -> int:
        return len(self._buf)
