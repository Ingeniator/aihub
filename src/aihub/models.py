from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


# ----- Enums -----

class LeaderboardPrivacy(str, Enum):
    private = "private"
    public = "public"


class Status(str, Enum):
    win = "win"
    lose = "lose"
    tie = "tie"


class Winner(str, Enum):
    primary = "primary"
    tie = "tie"
    secondary = "secondary"
    neither = "neither"


class Role(str, Enum):
    user = "user"
    assistant = "assistant"


# ----- Leaderboard -----

class PresetPrice(BaseModel):
    value: float
    currency: str


class PresetLeaderboard(BaseModel):
    uid: str
    model: str
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    prompt: Optional[str] = None
    input_price: PresetPrice
    output_price: PresetPrice


class Leaderboard(BaseModel):
    project_id: str
    preset: PresetLeaderboard
    rating: float
    peak: float
    matches: int
    wins: int
    losses: int
    ties: int
    updated_at: datetime
    privacy: LeaderboardPrivacy


class LeaderboardPage(BaseModel):
    items: list[Leaderboard]
    page: int
    size: int
    total: int
    total_pages: int


class LeaderboardCreate(BaseModel):
    privacy: LeaderboardPrivacy
    preset: PresetLeaderboard
    rating: float
    peak: float
    matches: int
    wins: int
    losses: int
    ties: int


class LeaderboardUpdate(BaseModel):
    preset: PresetLeaderboard
    rating: float
    peak: float
    matches: int
    wins: int
    losses: int
    ties: int


# ----- ChatHistory -----

class ChatMessage(BaseModel):
    content: str
    role: Role
    status: Optional[Status] = None


class PresetSample(BaseModel):
    uid: str
    model: str
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    prompt: Optional[str] = None


class ChatHistory(BaseModel):
    uid: str
    project_id: str
    primary_preset: PresetSample
    secondary_preset: PresetSample
    primary_messages: list[ChatMessage]
    secondary_messages: list[ChatMessage]
    winner: Winner
    created_at: datetime
    author_id: str


class ChatHistoryPage(BaseModel):
    items: list[ChatHistory]
    page: int
    size: int
    total: int
    total_pages: int


class Project(BaseModel):
    id: str


class ProjectPage(BaseModel):
    items: list[Project]
    page: int
    size: int
    total: int
    total_pages: int


class ChatHistoryCreate(BaseModel):
    primary_preset: PresetSample
    secondary_preset: PresetSample
    primary_messages: list[ChatMessage]
    secondary_messages: list[ChatMessage]
    winner: Winner
    author_id: str


class ChatHistoryUpdate(BaseModel):
    primary_preset: PresetSample
    secondary_preset: PresetSample
    primary_messages: list[ChatMessage]
    secondary_messages: list[ChatMessage]
    winner: Winner
