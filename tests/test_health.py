from __future__ import annotations

import pytest
from httpx import AsyncClient


async def test_livez(client: AsyncClient):
    resp = await client.get("/livez")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readyz(client: AsyncClient):
    resp = await client.get("/readyz")
    assert resp.status_code == 200


async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["components"]["postgres"] == "ok"


async def test_metrics(client: AsyncClient):
    # Trigger at least one DB operation so operation labels are populated
    await client.get("/projects/p/leaderboard")
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "aihub_db_query_seconds" in body
    assert "aihub_db_errors_total" in body
    assert "http_request_duration" in body
    assert "http_requests_total" in body
