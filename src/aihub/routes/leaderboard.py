from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aihub.database import LeaderboardRow, get_db
from aihub.metrics import DB_ERRORS_TOTAL, DB_QUERY_SECONDS
from aihub.models import (
    Leaderboard,
    LeaderboardCreate,
    LeaderboardPage,
    LeaderboardPrivacy,
    LeaderboardUpdate,
)

router = APIRouter()


def _to_model(row: LeaderboardRow) -> Leaderboard:
    return Leaderboard(
        project_id=row.project_id,
        preset=row.preset,
        rating=row.rating,
        peak=row.peak,
        matches=row.matches,
        wins=row.wins,
        losses=row.losses,
        ties=row.ties,
        updated_at=row.updated_at,
        privacy=row.privacy,
    )


@router.get("/projects/{project_id}/leaderboard", response_model=LeaderboardPage)
async def list_leaderboard(
    project_id: str,
    privacy: Optional[LeaderboardPrivacy] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardPage:
    op = "lb_list"
    try:
        with DB_QUERY_SECONDS.labels(operation=op).time():
            stmt = select(LeaderboardRow).where(LeaderboardRow.project_id == project_id)
            if privacy is not None:
                stmt = stmt.where(LeaderboardRow.privacy == privacy.value)
            total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            rows = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
            items = [_to_model(r) for r in rows.scalars()]
    except Exception:
        DB_ERRORS_TOTAL.labels(operation=op).inc()
        raise
    return LeaderboardPage(
        items=items,
        page=page,
        size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/projects/{project_id}/leaderboard", response_model=Leaderboard, status_code=201)
async def create_leaderboard(
    project_id: str,
    body: LeaderboardCreate,
    db: AsyncSession = Depends(get_db),
) -> Leaderboard:
    op = "lb_create"
    row = LeaderboardRow(
        project_id=project_id,
        preset_uid=body.preset.uid,
        preset=body.preset.model_dump(),
        rating=body.rating,
        peak=body.peak,
        matches=body.matches,
        wins=body.wins,
        losses=body.losses,
        ties=body.ties,
        updated_at=datetime.now(timezone.utc),
        privacy=body.privacy.value,
    )
    try:
        with DB_QUERY_SECONDS.labels(operation=op).time():
            db.add(row)
            await db.commit()
            await db.refresh(row)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Leaderboard entry already exists")
    except Exception:
        DB_ERRORS_TOTAL.labels(operation=op).inc()
        await db.rollback()
        raise
    return _to_model(row)


@router.get("/projects/{project_id}/leaderboard/{preset_uid}", response_model=Leaderboard)
async def get_leaderboard(
    project_id: str,
    preset_uid: str,
    db: AsyncSession = Depends(get_db),
) -> Leaderboard:
    op = "lb_get"
    try:
        with DB_QUERY_SECONDS.labels(operation=op).time():
            row = await db.get(LeaderboardRow, (project_id, preset_uid))
    except Exception:
        DB_ERRORS_TOTAL.labels(operation=op).inc()
        raise
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _to_model(row)


@router.patch("/projects/{project_id}/leaderboard/{preset_uid}", response_model=Leaderboard)
async def update_leaderboard(
    project_id: str,
    preset_uid: str,
    body: LeaderboardUpdate,
    db: AsyncSession = Depends(get_db),
) -> Leaderboard:
    op = "lb_update"
    try:
        with DB_QUERY_SECONDS.labels(operation=op).time():
            row = await db.get(LeaderboardRow, (project_id, preset_uid))
            if row is None:
                raise HTTPException(status_code=404, detail="Not found")
            row.preset = body.preset.model_dump()
            row.rating = body.rating
            row.peak = body.peak
            row.matches = body.matches
            row.wins = body.wins
            row.losses = body.losses
            row.ties = body.ties
            row.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(row)
    except HTTPException:
        raise
    except Exception:
        DB_ERRORS_TOTAL.labels(operation=op).inc()
        raise
    return _to_model(row)


@router.delete("/projects/{project_id}/leaderboard/{preset_uid}", status_code=204)
async def delete_leaderboard(
    project_id: str,
    preset_uid: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    op = "lb_delete"
    try:
        with DB_QUERY_SECONDS.labels(operation=op).time():
            row = await db.get(LeaderboardRow, (project_id, preset_uid))
            if row is None:
                raise HTTPException(status_code=404, detail="Not found")
            await db.delete(row)
            await db.commit()
    except HTTPException:
        raise
    except Exception:
        DB_ERRORS_TOTAL.labels(operation=op).inc()
        raise
