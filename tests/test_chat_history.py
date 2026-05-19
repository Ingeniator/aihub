from __future__ import annotations

import pytest
from httpx import AsyncClient

PROJECT = "proj-ch"

_PRESET_PRIMARY = {"uid": "p-primary", "model": "gpt-4o", "temperature": 0.7}
_PRESET_SECONDARY = {"uid": "p-secondary", "model": "claude-3-5-sonnet", "temperature": 0.5}

_MSG_USER = {"content": "Hello", "role": "user"}
_MSG_ASSISTANT = {"content": "Hi there!", "role": "assistant", "status": "win"}

_CREATE = {
    "primary_preset": _PRESET_PRIMARY,
    "secondary_preset": _PRESET_SECONDARY,
    "primary_messages": [_MSG_USER, _MSG_ASSISTANT],
    "secondary_messages": [_MSG_USER, {"content": "Greetings!", "role": "assistant"}],
    "winner": "primary",
    "author_id": "user-42",
}

_UPDATE = {
    "primary_preset": _PRESET_PRIMARY,
    "secondary_preset": _PRESET_SECONDARY,
    "primary_messages": [_MSG_USER, _MSG_ASSISTANT],
    "secondary_messages": [_MSG_USER, {"content": "Updated reply", "role": "assistant"}],
    "winner": "tie",
}


async def test_list_empty(client: AsyncClient):
    resp = await client.get(f"/projects/{PROJECT}/arena/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


async def test_create(client: AsyncClient):
    resp = await client.post(f"/projects/{PROJECT}/arena/history", json=_CREATE)
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == PROJECT
    assert data["winner"] == "primary"
    assert data["author_id"] == "user-42"
    assert "uid" in data
    assert "created_at" in data
    assert len(data["uid"]) == 36  # UUID v4


async def test_create_uid_is_unique(client: AsyncClient):
    r1 = await client.post(f"/projects/{PROJECT}/arena/history", json=_CREATE)
    r2 = await client.post(f"/projects/{PROJECT}/arena/history", json=_CREATE)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["uid"] != r2.json()["uid"]


async def test_list_populated(client: AsyncClient):
    await client.post(f"/projects/{PROJECT}/arena/history", json=_CREATE)
    await client.post(f"/projects/{PROJECT}/arena/history", json=_CREATE)
    resp = await client.get(f"/projects/{PROJECT}/arena/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


async def test_list_pagination(client: AsyncClient):
    for _ in range(3):
        await client.post(f"/projects/{PROJECT}/arena/history", json=_CREATE)
    resp = await client.get(f"/projects/{PROJECT}/arena/history", params={"page": 1, "size": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2

    resp2 = await client.get(f"/projects/{PROJECT}/arena/history", params={"page": 2, "size": 2})
    assert len(resp2.json()["items"]) == 1


async def test_list_isolated_by_project(client: AsyncClient):
    await client.post(f"/projects/{PROJECT}/arena/history", json=_CREATE)
    resp = await client.get("/projects/other-project/arena/history")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_get(client: AsyncClient):
    r = await client.post(f"/projects/{PROJECT}/arena/history", json=_CREATE)
    uid = r.json()["uid"]
    resp = await client.get(f"/projects/{PROJECT}/arena/history/{uid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["uid"] == uid
    assert data["primary_preset"]["model"] == "gpt-4o"
    assert len(data["primary_messages"]) == 2


async def test_get_not_found(client: AsyncClient):
    resp = await client.get(f"/projects/{PROJECT}/arena/history/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_get_wrong_project(client: AsyncClient):
    r = await client.post(f"/projects/{PROJECT}/arena/history", json=_CREATE)
    uid = r.json()["uid"]
    resp = await client.get(f"/projects/other-project/arena/history/{uid}")
    assert resp.status_code == 404


async def test_update(client: AsyncClient):
    r = await client.post(f"/projects/{PROJECT}/arena/history", json=_CREATE)
    uid = r.json()["uid"]
    resp = await client.patch(f"/projects/{PROJECT}/arena/history/{uid}", json=_UPDATE)
    assert resp.status_code == 200
    data = resp.json()
    assert data["winner"] == "tie"
    assert data["secondary_messages"][0]["content"] == "Updated reply" or \
           data["secondary_messages"][1]["content"] == "Updated reply"
    assert data["uid"] == uid
    assert data["author_id"] == "user-42"  # immutable


async def test_update_not_found(client: AsyncClient):
    resp = await client.patch(
        f"/projects/{PROJECT}/arena/history/00000000-0000-0000-0000-000000000000",
        json=_UPDATE,
    )
    assert resp.status_code == 404


async def test_delete(client: AsyncClient):
    r = await client.post(f"/projects/{PROJECT}/arena/history", json=_CREATE)
    uid = r.json()["uid"]
    resp = await client.delete(f"/projects/{PROJECT}/arena/history/{uid}")
    assert resp.status_code == 204

    resp = await client.get(f"/projects/{PROJECT}/arena/history/{uid}")
    assert resp.status_code == 404


async def test_delete_not_found(client: AsyncClient):
    resp = await client.delete(
        f"/projects/{PROJECT}/arena/history/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404
