"""PulseMetrics Agent — tails log files and ships them to the API."""
import argparse
import signal
import sys
import time

from pulsemetrics_agent.batcher import Batcher
from pulsemetrics_agent.buffer import DiskBuffer
from pulsemetrics_agent.shipper import Shipper
from pulsemetrics_agent.tailer import LogTailer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PulseMetrics Agent — ships log files to PulseMetrics"
    )
    parser.add_argument("--api-key", required=True, help="Application API key")
    parser.add_argument("--url", required=True, help="PulseMetrics server URL (e.g. http://localhost:8000)")
    parser.add_argument("--file", required=True, action="append", dest="files", help="Log file to tail (can repeat)")
    parser.add_argument("--batch-size", type=int, default=100, help="Lines per batch")
    parser.add_argument("--batch-interval", type=float, default=5.0, help="Seconds between forced flushes")
    parser.add_argument("--buffer-dir", default="/var/lib/pulsemetrics", help="Directory for disk buffer")
    args = parser.parse_args()

    buffer = DiskBuffer(args.buffer_dir)
    shipper = Shipper(args.url, args.api_key, buffer)
    batcher = Batcher(batch_size=args.batch_size, batch_interval=args.batch_interval)
    tailers = [LogTailer(f) for f in args.files]

    running = True

    def _stop(sig, frame):  # type: ignore[no-untyped-def]
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print(f"[pulsemetrics-agent] Tailing {args.files} → {args.url}", flush=True)
    for t in tailers:
        t.start()

    # Simple round-robin across tailers
    generators = [t.lines() for t in tailers]
    last_retry = time.monotonic()

    while running:
        for gen in generators:
            try:
                line = next(gen)
                batcher.add(line)
            except StopIteration:
                pass

        if batcher.should_flush():
            batch = batcher.flush()
            ok = shipper.ship(batch)
            if ok:
                print(f"[pulsemetrics-agent] Shipped {len(batch)} lines", flush=True)
            else:
                print(f"[pulsemetrics-agent] Buffered {len(batch)} lines (network error)", flush=True)

        # Retry buffered batches every 60s
        if time.monotonic() - last_retry > 60:
            shipped = shipper.retry_buffered()
            if shipped:
                print(f"[pulsemetrics-agent] Retried {shipped} buffered batches", flush=True)
            last_retry = time.monotonic()

        time.sleep(0.01)

    # Final flush on exit
    if len(batcher) > 0:
        shipper.ship(batcher.flush())

    shipper.close()
    for t in tailers:
        t.stop()
    print("[pulsemetrics-agent] Stopped", flush=True)


if __name__ == "__main__":
    main()
