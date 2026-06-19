"""Load test: push 1000+ log entries/sec and measure latency."""
import asyncio
import random
import statistics
import time
from datetime import datetime, timezone

import httpx
import numpy as np

BASE_URL = "http://localhost:8000"
API_KEY = ""  # Set this before running

MESSAGES = [
    "GET /api/users 200 OK in {}ms",
    "POST /api/orders 201 Created",
    "Connection to db-host-{} failed after {}s",
    "User {} authenticated successfully",
    "Cache miss for key session:{}",
    "Payment processed for amount ${}",
    "Email sent to {}@example.com",
    "Job {} completed in {}s",
]

LEVELS = ["INFO", "INFO", "INFO", "WARNING", "ERROR", "CRITICAL"]
SERVICES = ["api", "payments", "auth", "worker", "database"]


def random_entry():
    msg = random.choice(MESSAGES).format(*[random.randint(1, 9999) for _ in range(5)])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": random.choice(LEVELS),
        "service": random.choice(SERVICES),
        "message": msg,
        "metadata": {"request_id": f"req_{random.randint(10000, 99999)}"},
    }


async def send_batch(client: httpx.AsyncClient, entries: list, latencies: list) -> None:
    start = time.perf_counter()
    try:
        r = await client.post(
            f"{BASE_URL}/api/v1/logs/ingest",
            json={"entries": entries},
            headers={"X-Api-Key": API_KEY},
            timeout=30,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)
        if r.status_code != 202:
            print(f"Error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Request failed: {e}")


async def run_load_test(
    duration_seconds: int = 30,
    batch_size: int = 100,
    concurrency: int = 10,
) -> None:
    if not API_KEY:
        print("ERROR: Set API_KEY before running the load test")
        return

    print(f"Load test: {batch_size} entries/batch, {concurrency} concurrent, {duration_seconds}s")
    latencies: list[float] = []
    total_entries = 0
    start_time = time.monotonic()

    async with httpx.AsyncClient() as client:
        tasks: list[asyncio.Task] = []

        while time.monotonic() - start_time < duration_seconds:
            entries = [random_entry() for _ in range(batch_size)]
            task = asyncio.create_task(send_batch(client, entries, latencies))
            tasks.append(task)
            total_entries += batch_size

            if len(tasks) >= concurrency:
                await asyncio.gather(*tasks)
                tasks = []

        if tasks:
            await asyncio.gather(*tasks)

    elapsed = time.monotonic() - start_time
    throughput = total_entries / elapsed

    arr = np.array(latencies)
    print(f"\n{'='*50}")
    print(f"Results ({total_entries} entries in {elapsed:.1f}s)")
    print(f"Throughput: {throughput:.0f} entries/sec")
    print(f"Latency (batch of {batch_size}):")
    print(f"  p50:  {np.percentile(arr, 50):.1f}ms")
    print(f"  p95:  {np.percentile(arr, 95):.1f}ms")
    print(f"  p99:  {np.percentile(arr, 99):.1f}ms")
    print(f"  max:  {np.max(arr):.1f}ms")
    print(f"{'='*50}")

    # Per-entry latency (batch latency / batch size)
    per_entry = arr / batch_size
    print(f"Per-entry latency: p95={np.percentile(per_entry, 95):.2f}ms")


if __name__ == "__main__":
    asyncio.run(run_load_test())
