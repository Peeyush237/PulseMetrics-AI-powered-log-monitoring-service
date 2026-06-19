import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    r = await client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "PulseMetrics"


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # Register
    r = await client.post("/api/v1/auth/register", json={
        "org_name": "Test Org",
        "email": "test@example.com",
        "password": "testpassword123",
    })
    assert r.status_code == 201
    tokens = r.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # Login
    r2 = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword123",
    })
    assert r2.status_code == 200

    # Wrong password
    r3 = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "wrong",
    })
    assert r3.status_code == 401


@pytest.mark.asyncio
async def test_application_crud(client: AsyncClient):
    # Register first
    reg = await client.post("/api/v1/auth/register", json={
        "org_name": "App Test Org",
        "email": "apptest@example.com",
        "password": "password123",
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create application
    r = await client.post("/api/v1/applications", json={"name": "my-app"}, headers=headers)
    assert r.status_code == 201
    app_data = r.json()
    assert app_data["name"] == "my-app"
    assert "api_key" in app_data
    api_key = app_data["api_key"]
    app_id = app_data["id"]

    # List
    r2 = await client.get("/api/v1/applications", headers=headers)
    assert r2.status_code == 200
    apps = r2.json()
    assert len(apps) >= 1

    # Ingest logs via API key
    r3 = await client.post(
        "/api/v1/logs/ingest",
        json={"entries": [{"message": "test log", "level": "INFO"}]},
        headers={"X-Api-Key": api_key},
    )
    assert r3.status_code == 202
    assert r3.json()["accepted"] == 1
