from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import Column, DateTime, Float, Index, Integer, JSON, String, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from aihub.config import Settings


class Base(DeclarativeBase):
    pass


class LeaderboardRow(Base):
    __tablename__ = "leaderboard"

    project_id = Column(String, primary_key=True)
    preset_uid = Column(String, primary_key=True)
    preset = Column(JSON, nullable=False)
    rating = Column(Float, nullable=False)
    peak = Column(Float, nullable=False)
    matches = Column(Integer, nullable=False)
    wins = Column(Integer, nullable=False)
    losses = Column(Integer, nullable=False)
    ties = Column(Integer, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    privacy = Column(String, nullable=False)


class ChatHistoryRow(Base):
    __tablename__ = "chat_history"

    uid = Column(String, primary_key=True)
    project_id = Column(String, nullable=False)
    primary_preset = Column(JSON, nullable=False)
    secondary_preset = Column(JSON, nullable=False)
    primary_messages = Column(JSON, nullable=False)
    secondary_messages = Column(JSON, nullable=False)
    winner = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    author_id = Column(String, nullable=False)

    __table_args__ = (Index("ix_chat_history_project_id", "project_id"),)


_engine = None
_session_factory: async_sessionmaker | None = None


def init_db(settings: Settings) -> None:
    global _engine, _session_factory
    pool = settings.postgres.pool
    _engine = create_async_engine(
        settings.postgres.dsn(),
        pool_pre_ping=True,
        pool_size=pool.size,
        max_overflow=pool.max_overflow,
        pool_timeout=pool.timeout,
        pool_recycle=pool.recycle,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def create_tables() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_db() -> bool:
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session
