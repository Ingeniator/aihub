from __future__ import annotations

from httpx import AsyncClient

_LB_PRESET = {
    "uid": "preset-1",
    "model": "gpt-4o",
    "input_price": {"value": 5.0, "currency": "USD"},
    "output_price": {"value": 15.0, "currency": "USD"},
}
_LB_CREATE = {
    "privacy": "public",
    "preset": _LB_PRESET,
    "rating": 1500.0,
    "peak": 1600.0,
    "matches": 10,
    "wins": 7,
    "losses": 2,
    "ties": 1,
}

_CH_CREATE = {
    "primary_preset": {"uid": "p1", "model": "gpt-4o"},
    "secondary_preset": {"uid": "p2", "model": "claude-3-5-sonnet"},
    "primary_messages": [{"content": "hi", "role": "user"}],
    "secondary_messages": [{"content": "hi", "role": "user"}],
    "winner": "primary",
    "author_id": "user-1",
}


async def _create_lb(client: AsyncClient, project: str) -> None:
    await client.post(f"/projects/{project}/leaderboard", json=_LB_CREATE)


async def _create_ch(client: AsyncClient, project: str) -> None:
    await client.post(f"/projects/{project}/arena/history", json=_CH_CREATE)


async def test_list_empty(client: AsyncClient):
    resp = await client.get("/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["total_pages"] == 0


async def test_list_from_leaderboard(client: AsyncClient):
    await _create_lb(client, "proj-a")
    resp = await client.get("/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "proj-a"


async def test_list_from_chat_history(client: AsyncClient):
    await _create_ch(client, "proj-b")
    resp = await client.get("/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "proj-b"


async def test_list_deduplicates_same_project(client: AsyncClient):
    await _create_lb(client, "proj-x")
    await _create_ch(client, "proj-x")
    resp = await client.get("/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "proj-x"


async def test_list_multiple_projects(client: AsyncClient):
    await _create_lb(client, "proj-1")
    await _create_ch(client, "proj-2")
    await _create_lb(client, "proj-3")
    resp = await client.get("/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    ids = {item["id"] for item in data["items"]}
    assert ids == {"proj-1", "proj-2", "proj-3"}


async def test_list_pagination(client: AsyncClient):
    for i in range(1, 4):
        await _create_lb(client, f"proj-pg-{i}")
    resp = await client.get("/projects", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["total_pages"] == 2
    assert len(data["items"]) == 2

    resp2 = await client.get("/projects", params={"page": 2, "page_size": 2})
    assert len(resp2.json()["items"]) == 1


async def test_list_total_pages(client: AsyncClient):
    for i in range(1, 6):
        await _create_ch(client, f"proj-tp-{i}")
    resp = await client.get("/projects", params={"page_size": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["total_pages"] == 2
