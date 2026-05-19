from __future__ import annotations

import pytest
from httpx import AsyncClient

PROJECT = "proj-test"

_PRESET = {
    "uid": "preset-1",
    "model": "gpt-4o",
    "temperature": 0.7,
    "input_price": {"value": 5.0, "currency": "USD"},
    "output_price": {"value": 15.0, "currency": "USD"},
}

_CREATE = {
    "privacy": "public",
    "preset": _PRESET,
    "rating": 1500.0,
    "peak": 1600.0,
    "matches": 10,
    "wins": 7,
    "losses": 2,
    "ties": 1,
}

_UPDATE = {
    "preset": _PRESET,
    "rating": 1620.0,
    "matches": 12,
    "wins": 9,
    "losses": 2,
    "ties": 1,
}


async def test_list_empty(client: AsyncClient):
    resp = await client.get(f"/projects/{PROJECT}/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["total_pages"] == 0


async def test_create(client: AsyncClient):
    resp = await client.post(f"/projects/{PROJECT}/leaderboard", json=_CREATE)
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == PROJECT
    assert data["preset"]["uid"] == "preset-1"
    assert data["rating"] == 1500.0
    assert data["peak"] == 1600.0
    assert data["privacy"] == "public"
    assert "updated_at" in data


async def test_create_conflict(client: AsyncClient):
    await client.post(f"/projects/{PROJECT}/leaderboard", json=_CREATE)
    resp = await client.post(f"/projects/{PROJECT}/leaderboard", json=_CREATE)
    assert resp.status_code == 409


async def test_list_populated(client: AsyncClient):
    await client.post(f"/projects/{PROJECT}/leaderboard", json=_CREATE)
    resp = await client.get(f"/projects/{PROJECT}/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["total_pages"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["preset"]["uid"] == "preset-1"


async def test_list_filter_privacy_no_match(client: AsyncClient):
    await client.post(f"/projects/{PROJECT}/leaderboard", json=_CREATE)
    resp = await client.get(f"/projects/{PROJECT}/leaderboard", params={"privacy": "private"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_list_filter_privacy_match(client: AsyncClient):
    await client.post(f"/projects/{PROJECT}/leaderboard", json=_CREATE)
    resp = await client.get(f"/projects/{PROJECT}/leaderboard", params={"privacy": "public"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_list_pagination(client: AsyncClient):
    preset2 = {**_PRESET, "uid": "preset-2"}
    await client.post(f"/projects/{PROJECT}/leaderboard", json=_CREATE)
    await client.post(f"/projects/{PROJECT}/leaderboard", json={**_CREATE, "preset": preset2})
    resp = await client.get(f"/projects/{PROJECT}/leaderboard", params={"page": 1, "page_size": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["total_pages"] == 2
    assert len(data["items"]) == 1


async def test_list_isolated_by_project(client: AsyncClient):
    await client.post(f"/projects/{PROJECT}/leaderboard", json=_CREATE)
    resp = await client.get("/projects/other-project/leaderboard")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_get(client: AsyncClient):
    await client.post(f"/projects/{PROJECT}/leaderboard", json=_CREATE)
    resp = await client.get(f"/projects/{PROJECT}/leaderboard/preset-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["preset"]["uid"] == "preset-1"
    assert data["preset"]["input_price"]["currency"] == "USD"


async def test_get_not_found(client: AsyncClient):
    resp = await client.get(f"/projects/{PROJECT}/leaderboard/nonexistent")
    assert resp.status_code == 404


async def test_update(client: AsyncClient):
    await client.post(f"/projects/{PROJECT}/leaderboard", json=_CREATE)
    resp = await client.patch(f"/projects/{PROJECT}/leaderboard/preset-1", json=_UPDATE)
    assert resp.status_code == 200
    data = resp.json()
    assert data["rating"] == 1620.0
    assert data["matches"] == 12
    assert data["wins"] == 9
    assert data["peak"] == 1600.0  # peak unchanged by update


async def test_update_not_found(client: AsyncClient):
    resp = await client.patch(f"/projects/{PROJECT}/leaderboard/nonexistent", json=_UPDATE)
    assert resp.status_code == 404


async def test_delete(client: AsyncClient):
    await client.post(f"/projects/{PROJECT}/leaderboard", json=_CREATE)
    resp = await client.delete(f"/projects/{PROJECT}/leaderboard/preset-1")
    assert resp.status_code == 204

    resp = await client.get(f"/projects/{PROJECT}/leaderboard/preset-1")
    assert resp.status_code == 404


async def test_delete_not_found(client: AsyncClient):
    resp = await client.delete(f"/projects/{PROJECT}/leaderboard/nonexistent")
    assert resp.status_code == 404
