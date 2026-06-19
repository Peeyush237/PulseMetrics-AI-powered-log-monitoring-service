"""Seed the database with sample data for development and demo."""
import asyncio
import json
import random
from datetime import datetime, timedelta, timezone

import httpx

BASE_URL = "http://localhost:8000"
EMAIL = "demo@example.com"
PASSWORD = "demo1234"
ORG = "Demo Corp"

SAMPLE_LOGS = [
    {"level": "INFO", "service": "api", "message": "GET /api/users 200 OK in 42ms"},
    {"level": "INFO", "service": "api", "message": "POST /api/orders 201 Created in 128ms"},
    {"level": "WARNING", "service": "payments", "message": "Stripe API latency above 2s threshold"},
    {"level": "ERROR", "service": "payments", "message": "Connection to db-host-1 failed after 3.2s"},
    {"level": "ERROR", "service": "payments", "message": "Failed to charge card: insufficient funds for user 4521"},
    {"level": "CRITICAL", "service": "auth", "message": "Failed login attempts exceeded limit for IP 192.168.1.100"},
    {"level": "INFO", "service": "worker", "message": "Processed 847 email notifications in 2.3s"},
    {"level": "ERROR", "service": "worker", "message": "Job queue backed up: 12487 pending tasks"},
    {"level": "WARNING", "service": "api", "message": "Rate limit approaching for tenant abc-corp"},
    {"level": "INFO", "service": "database", "message": "Vacuum completed on table users in 8.3s"},
    {"level": "ERROR", "service": "payments", "message": "OutOfMemory: cannot allocate 512MB for PDF generation"},
    {"level": "ERROR", "service": "api", "message": "Unhandled exception in request handler: NullPointerException"},
]


async def seed():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        # Register (or login)
        r = await client.post("/api/v1/auth/register", json={
            "org_name": ORG, "email": EMAIL, "password": PASSWORD
        })
        if r.status_code == 409:
            r = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Logged in as {EMAIL}")

        # Create application
        r = await client.post("/api/v1/applications", json={"name": "demo-app"}, headers=headers)
        if r.status_code == 409:
            apps = await client.get("/api/v1/applications", headers=headers)
            app = next(a for a in apps.json() if a["name"] == "demo-app")
            api_key = None
            print("App already exists, cannot re-show API key")
        else:
            app = r.json()
            api_key = app["api_key"]
            print(f"Created app: demo-app | API Key: {api_key}")

        if api_key is None:
            print("Cannot ingest without API key. Rotate it from the dashboard.")
            return

        # Create Slack channel (console for demo)
        r = await client.post("/api/v1/channels", json={
            "name": "console-alerts",
            "channel_type": "console",
            "config": {},
        }, headers=headers)
        ch_id = r.json().get("id")
        print(f"Created channel: console-alerts ({ch_id})")

        # Create a threshold rule
        r = await client.post(f"/api/v1/rules?application_id={app['id']}", json={
            "name": "Payment errors",
            "rule_type": "threshold",
            "config": {"filters": {"level": ">=ERROR", "service": "payments"}, "window_seconds": 300, "threshold": 3},
            "cooldown_seconds": 300,
            "channel_ids": [ch_id] if ch_id else [],
        }, headers=headers)
        print(f"Created rule: {r.json().get('name')}")

        # Create a novelty rule
        r = await client.post(f"/api/v1/rules?application_id={app['id']}", json={
            "name": "New error pattern",
            "rule_type": "novelty",
            "config": {"min_severity": "ERROR"},
            "cooldown_seconds": 300,
            "channel_ids": [ch_id] if ch_id else [],
        }, headers=headers)
        print(f"Created rule: {r.json().get('name')}")

        # Ingest sample logs
        ingest_headers = {"X-Api-Key": api_key}
        entries = []
        now = datetime.now(timezone.utc)
        for i in range(200):
            sample = random.choice(SAMPLE_LOGS).copy()
            sample["timestamp"] = (now - timedelta(minutes=random.randint(0, 1440))).isoformat()
            entries.append(sample)
            if len(entries) >= 50:
                r = await client.post("/api/v1/logs/ingest", json={"entries": entries}, headers=ingest_headers)
                print(f"Ingested batch: {r.json()}")
                entries = []

        if entries:
            r = await client.post("/api/v1/logs/ingest", json={"entries": entries}, headers=ingest_headers)
            print(f"Ingested final batch: {r.json()}")

        print("\nSeed complete! Visit http://localhost:8000/ui to explore the dashboard.")


if __name__ == "__main__":
    asyncio.run(seed())
