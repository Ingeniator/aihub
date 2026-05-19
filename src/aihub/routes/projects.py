from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from aihub.database import ChatHistoryRow, LeaderboardRow, get_db
from aihub.metrics import DB_ERRORS_TOTAL, DB_QUERY_SECONDS
from aihub.models import Project, ProjectPage

router = APIRouter()


@router.get("/projects", response_model=ProjectPage)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ProjectPage:
    op = "projects_list"
    try:
        with DB_QUERY_SECONDS.labels(operation=op).time():
            all_ids = union(
                select(LeaderboardRow.project_id.label("id")),
                select(ChatHistoryRow.project_id.label("id")),
            ).subquery()
            total = await db.scalar(select(func.count()).select_from(all_ids)) or 0
            rows = await db.execute(
                select(all_ids.c.id)
                .order_by(all_ids.c.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            items = [Project(id=r[0]) for r in rows]
    except Exception:
        DB_ERRORS_TOTAL.labels(operation=op).inc()
        raise
    return ProjectPage(
        items=items,
        page=page,
        size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
