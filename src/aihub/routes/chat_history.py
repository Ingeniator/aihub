from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aihub.database import ChatHistoryRow, get_db
from aihub.metrics import DB_ERRORS_TOTAL, DB_QUERY_SECONDS
from aihub.models import (
    ChatHistory,
    ChatHistoryCreate,
    ChatHistoryPage,
    ChatHistoryUpdate,
)

router = APIRouter()


def _to_model(row: ChatHistoryRow) -> ChatHistory:
    return ChatHistory(
        uid=row.uid,
        project_id=row.project_id,
        primary_preset=row.primary_preset,
        secondary_preset=row.secondary_preset,
        primary_messages=row.primary_messages,
        secondary_messages=row.secondary_messages,
        winner=row.winner,
        created_at=row.created_at,
        author_id=row.author_id,
    )


@router.get("/projects/{project_id}/arena/history", response_model=ChatHistoryPage)
async def list_chat_history(
    project_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryPage:
    op = "ch_list"
    try:
        with DB_QUERY_SECONDS.labels(operation=op).time():
            stmt = select(ChatHistoryRow).where(ChatHistoryRow.project_id == project_id)
            total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            rows = await db.execute(
                stmt.order_by(ChatHistoryRow.created_at.desc()).offset((page - 1) * size).limit(size)
            )
            items = [_to_model(r) for r in rows.scalars()]
    except Exception:
        DB_ERRORS_TOTAL.labels(operation=op).inc()
        raise
    return ChatHistoryPage(items=items, page=page, size=size, total=total)


@router.post("/projects/{project_id}/arena/history", response_model=ChatHistory, status_code=201)
async def create_chat_history(
    project_id: str,
    body: ChatHistoryCreate,
    db: AsyncSession = Depends(get_db),
) -> ChatHistory:
    op = "ch_create"
    row = ChatHistoryRow(
        uid=str(uuid.uuid4()),
        project_id=project_id,
        primary_preset=body.primary_preset.model_dump(),
        secondary_preset=body.secondary_preset.model_dump(),
        primary_messages=[m.model_dump() for m in body.primary_messages],
        secondary_messages=[m.model_dump() for m in body.secondary_messages],
        winner=body.winner.value,
        created_at=datetime.now(timezone.utc),
        author_id=body.author_id,
    )
    try:
        with DB_QUERY_SECONDS.labels(operation=op).time():
            db.add(row)
            await db.commit()
            await db.refresh(row)
    except Exception:
        DB_ERRORS_TOTAL.labels(operation=op).inc()
        await db.rollback()
        raise
    return _to_model(row)


@router.get("/projects/{project_id}/arena/history/{uid}", response_model=ChatHistory)
async def get_chat_history(
    project_id: str,
    uid: str,
    db: AsyncSession = Depends(get_db),
) -> ChatHistory:
    op = "ch_get"
    try:
        with DB_QUERY_SECONDS.labels(operation=op).time():
            row = await db.get(ChatHistoryRow, uid)
    except Exception:
        DB_ERRORS_TOTAL.labels(operation=op).inc()
        raise
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Not found")
    return _to_model(row)


@router.patch("/projects/{project_id}/arena/history/{uid}", response_model=ChatHistory)
async def update_chat_history(
    project_id: str,
    uid: str,
    body: ChatHistoryUpdate,
    db: AsyncSession = Depends(get_db),
) -> ChatHistory:
    op = "ch_update"
    try:
        with DB_QUERY_SECONDS.labels(operation=op).time():
            row = await db.get(ChatHistoryRow, uid)
            if row is None or row.project_id != project_id:
                raise HTTPException(status_code=404, detail="Not found")
            row.primary_preset = body.primary_preset.model_dump()
            row.secondary_preset = body.secondary_preset.model_dump()
            row.primary_messages = [m.model_dump() for m in body.primary_messages]
            row.secondary_messages = [m.model_dump() for m in body.secondary_messages]
            row.winner = body.winner.value
            await db.commit()
            await db.refresh(row)
    except HTTPException:
        raise
    except Exception:
        DB_ERRORS_TOTAL.labels(operation=op).inc()
        raise
    return _to_model(row)


@router.delete("/projects/{project_id}/arena/history/{uid}", status_code=204)
async def delete_chat_history(
    project_id: str,
    uid: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    op = "ch_delete"
    try:
        with DB_QUERY_SECONDS.labels(operation=op).time():
            row = await db.get(ChatHistoryRow, uid)
            if row is None or row.project_id != project_id:
                raise HTTPException(status_code=404, detail="Not found")
            await db.delete(row)
            await db.commit()
    except HTTPException:
        raise
    except Exception:
        DB_ERRORS_TOTAL.labels(operation=op).inc()
        raise
