import subprocess
import sys
import time
from collections.abc import Generator


class LogTailer:
    """Tails a log file using subprocess, yielding lines."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._proc: subprocess.Popen | None = None

    def start(self) -> None:
        # Use 'tail -F' on Unix, PowerShell on Windows
        if sys.platform == "win32":
            cmd = ["powershell", "-Command", f"Get-Content -Path '{self.path}' -Wait -Tail 0"]
        else:
            cmd = ["tail", "-F", self.path]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

    def lines(self) -> Generator[str, None, None]:
        if self._proc is None:
            self.start()
        assert self._proc is not None
        assert self._proc.stdout is not None
        while True:
            line = self._proc.stdout.readline()
            if line:
                yield line.rstrip("\n")
            else:
                if self._proc.poll() is not None:
                    break
                time.sleep(0.01)

    def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            self._proc = None
