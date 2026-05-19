"""Populate PostgreSQL tables with sample data for development.

Usage:
  python scripts/seed.py            # skip tables that already have data
  python scripts/seed.py --reset   # truncate and re-seed
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aihub.config import get_settings
from aihub.database import Base, ChatHistoryRow, LeaderboardRow

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Preset catalogue (uid → full PresetLeaderboard payload)
# ---------------------------------------------------------------------------

_PRESETS = [
    {
        "uid": "gpt-4o",
        "model": "gpt-4o",
        "temperature": 0.7,
        "top_p": 1.0,
        "max_tokens": 4096,
        "prompt": "You are a helpful, harmless, and honest assistant.",
        "input_price": {"value": 2.50, "currency": "USD"},
        "output_price": {"value": 10.00, "currency": "USD"},
    },
    {
        "uid": "claude-3-5-sonnet",
        "model": "claude-3-5-sonnet-20241022",
        "temperature": 0.7,
        "top_p": 1.0,
        "max_tokens": 4096,
        "prompt": "You are Claude, made by Anthropic.",
        "input_price": {"value": 3.00, "currency": "USD"},
        "output_price": {"value": 15.00, "currency": "USD"},
    },
    {
        "uid": "gemini-1-5-pro",
        "model": "gemini-1.5-pro",
        "temperature": 0.8,
        "top_p": 0.95,
        "max_tokens": 8192,
        "prompt": "You are a helpful AI assistant built by Google.",
        "input_price": {"value": 1.25, "currency": "USD"},
        "output_price": {"value": 5.00, "currency": "USD"},
    },
    {
        "uid": "gpt-4o-mini",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "top_p": 1.0,
        "max_tokens": 4096,
        "prompt": "You are a helpful, harmless, and honest assistant.",
        "input_price": {"value": 0.15, "currency": "USD"},
        "output_price": {"value": 0.60, "currency": "USD"},
    },
    {
        "uid": "claude-3-haiku",
        "model": "claude-3-haiku-20240307",
        "temperature": 0.5,
        "top_p": 1.0,
        "max_tokens": 2048,
        "prompt": "You are Claude, made by Anthropic.",
        "input_price": {"value": 0.25, "currency": "USD"},
        "output_price": {"value": 1.25, "currency": "USD"},
    },
    {
        "uid": "llama-3-1-70b",
        "model": "llama-3.1-70b-instruct",
        "temperature": 0.6,
        "top_p": 0.9,
        "max_tokens": 4096,
        "prompt": "You are a helpful open-source AI assistant.",
        "input_price": {"value": 0.88, "currency": "USD"},
        "output_price": {"value": 0.88, "currency": "USD"},
    },
]

# ---------------------------------------------------------------------------
# Leaderboard stats per preset — deterministic, descending by rating
# ---------------------------------------------------------------------------

_LEADERBOARD_STATS = {
    "gpt-4o":            {"rating": 1782, "peak": 1800, "matches": 112, "wins": 87, "losses": 19, "ties": 6},
    "claude-3-5-sonnet": {"rating": 1756, "peak": 1783, "matches": 98,  "wins": 81, "losses": 12, "ties": 5},
    "gemini-1-5-pro":    {"rating": 1634, "peak": 1670, "matches": 76,  "wins": 52, "losses": 21, "ties": 3},
    "gpt-4o-mini":       {"rating": 1521, "peak": 1545, "matches": 89,  "wins": 44, "losses": 42, "ties": 3},
    "claude-3-haiku":    {"rating": 1489, "peak": 1510, "matches": 67,  "wins": 31, "losses": 33, "ties": 3},
    "llama-3-1-70b":     {"rating": 1402, "peak": 1450, "matches": 54,  "wins": 18, "losses": 34, "ties": 2},
}

# ---------------------------------------------------------------------------
# Projects seeded
# ---------------------------------------------------------------------------

_PROJECTS = [
    {"id": "arena",    "privacy": "public"},
    {"id": "demo",     "privacy": "private"},
]

# ---------------------------------------------------------------------------
# Chat history conversation templates
# (primary_preset_uid, secondary_preset_uid, messages, winner)
# ---------------------------------------------------------------------------

_msg = lambda role, content, status=None: (  # noqa: E731
    {"role": role, "content": content, **({} if status is None else {"status": status})}
)

_CONVERSATIONS = [
    {
        "primary": "gpt-4o",
        "secondary": "claude-3-5-sonnet",
        "primary_messages": [
            _msg("user", "Write a Python function to reverse a linked list."),
            _msg("assistant", "```python\ndef reverse_list(head):\n    prev = None\n    curr = head\n    while curr:\n        nxt = curr.next\n        curr.next = prev\n        prev = curr\n        curr = nxt\n    return prev\n```\nThis runs in O(n) time and O(1) space.", "win"),
        ],
        "secondary_messages": [
            _msg("user", "Write a Python function to reverse a linked list."),
            _msg("assistant", "Here is an iterative solution:\n```python\ndef reverse(head):\n    prev, node = None, head\n    while node:\n        node.next, prev, node = prev, node, node.next\n    return prev\n```"),
        ],
        "winner": "primary",
    },
    {
        "primary": "claude-3-5-sonnet",
        "secondary": "gemini-1-5-pro",
        "primary_messages": [
            _msg("user", "Explain the key differences between REST and GraphQL."),
            _msg("assistant", "REST uses multiple endpoints, each returning fixed data shapes. GraphQL exposes a single endpoint where clients specify exactly what data they need — reducing over- and under-fetching. GraphQL also provides a strongly-typed schema and built-in introspection.", "win"),
        ],
        "secondary_messages": [
            _msg("user", "Explain the key differences between REST and GraphQL."),
            _msg("assistant", "REST is resource-based with fixed endpoints. GraphQL lets clients query a flexible schema. Key advantages of GraphQL: single request for nested data, strong typing, and self-documenting schema. REST is simpler to cache and more widely understood.", "win"),
        ],
        "winner": "tie",
    },
    {
        "primary": "gpt-4o-mini",
        "secondary": "claude-3-haiku",
        "primary_messages": [
            _msg("user", "Write a haiku about machine learning."),
            _msg("assistant", "Gradient descends —\nWeights adjust in silent loops;\nLoss finds its valley."),
        ],
        "secondary_messages": [
            _msg("user", "Write a haiku about machine learning."),
            _msg("assistant", "Data feeds the mind,\nPatterns bloom from noise and weight —\nModel learns to see.", "win"),
        ],
        "winner": "secondary",
    },
    {
        "primary": "gpt-4o",
        "secondary": "llama-3-1-70b",
        "primary_messages": [
            _msg("user", "Explain gradient descent step by step."),
            _msg("assistant", "1. Initialise weights randomly.\n2. Feed a batch forward to compute loss.\n3. Compute the gradient of the loss w.r.t. each weight (backprop).\n4. Update: w = w - lr × ∇w.\n5. Repeat until convergence.\nThe learning rate controls step size; too large and it diverges, too small and it stalls.", "win"),
        ],
        "secondary_messages": [
            _msg("user", "Explain gradient descent step by step."),
            _msg("assistant", "Gradient descent minimises a loss function. Start with random weights, compute the gradient, then move in the opposite direction scaled by the learning rate. Iterate until the loss stops improving."),
        ],
        "winner": "primary",
    },
    {
        "primary": "claude-3-5-sonnet",
        "secondary": "gpt-4o",
        "primary_messages": [
            _msg("user", "Debug this Python code:\ndef divide(a, b):\n    return a / b\nprint(divide(10, 0))"),
            _msg("assistant", "The function raises `ZeroDivisionError` when `b=0`. Fix:\n```python\ndef divide(a, b):\n    if b == 0:\n        raise ValueError('Divisor cannot be zero')\n    return a / b\n```\nOr return `None` / `float('inf')` depending on your domain.", "win"),
        ],
        "secondary_messages": [
            _msg("user", "Debug this Python code:\ndef divide(a, b):\n    return a / b\nprint(divide(10, 0))"),
            _msg("assistant", "You'll get a ZeroDivisionError. Add a guard:\n```python\ndef divide(a, b):\n    return a / b if b != 0 else None\n```"),
        ],
        "winner": "primary",
    },
    {
        "primary": "gemini-1-5-pro",
        "secondary": "gpt-4o-mini",
        "primary_messages": [
            _msg("user", "Translate to French: The quick brown fox jumps over the lazy dog."),
            _msg("assistant", "Le rapide renard brun saute par-dessus le chien paresseux.", "win"),
        ],
        "secondary_messages": [
            _msg("user", "Translate to French: The quick brown fox jumps over the lazy dog."),
            _msg("assistant", "Le renard brun rapide saute par-dessus le chien paresseux.", "win"),
        ],
        "winner": "tie",
    },
    {
        "primary": "llama-3-1-70b",
        "secondary": "claude-3-haiku",
        "primary_messages": [
            _msg("user", "What are the ethical implications of training AI on scraped web data?"),
            _msg("assistant", "Key concerns include: copyright violation of original creators, consent (people didn't agree to train AI), privacy leakage of personal data, and perpetuating biases present on the web. Mitigations include opt-out mechanisms, data provenance tracking, and licensing frameworks like C4 or The Pile."),
        ],
        "secondary_messages": [
            _msg("user", "What are the ethical implications of training AI on scraped web data?"),
            _msg("assistant", "Ethical concerns span copyright, consent, and bias. Creators whose work is used without compensation have legitimate grievances. Privacy is at risk if personal data is ingested. Bias encoded in web data gets amplified in models. The industry is moving toward licensed datasets and opt-out registries."),
        ],
        "winner": "neither",
    },
    {
        "primary": "gpt-4o",
        "secondary": "gemini-1-5-pro",
        "primary_messages": [
            _msg("user", "Write a SQL query to find the top 5 customers by total order value."),
            _msg("assistant", "```sql\nSELECT\n    c.customer_id,\n    c.name,\n    SUM(o.total_amount) AS total_value\nFROM customers c\nJOIN orders o ON o.customer_id = c.customer_id\nGROUP BY c.customer_id, c.name\nORDER BY total_value DESC\nLIMIT 5;\n```", "win"),
        ],
        "secondary_messages": [
            _msg("user", "Write a SQL query to find the top 5 customers by total order value."),
            _msg("assistant", "```sql\nSELECT customer_id, SUM(total_amount) AS revenue\nFROM orders\nGROUP BY customer_id\nORDER BY revenue DESC\nFETCH FIRST 5 ROWS ONLY;\n```\nNote: joins the customer name if needed."),
        ],
        "winner": "primary",
    },
    {
        "primary": "claude-3-haiku",
        "secondary": "gpt-4o-mini",
        "primary_messages": [
            _msg("user", "Write a regex to validate an email address."),
            _msg("assistant", r"`^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$`\n\nThis covers the most common cases. For strict RFC 5321 compliance a full parser is recommended."),
        ],
        "secondary_messages": [
            _msg("user", "Write a regex to validate an email address."),
            _msg("assistant", r"```\n^[\w.+-]+@[\w-]+\.[\w.]+$\n```\nSimple and works for most addresses. Doesn't handle quoted strings or IP literals.", "win"),
        ],
        "winner": "secondary",
    },
    {
        "primary": "gpt-4o",
        "secondary": "claude-3-5-sonnet",
        "primary_messages": [
            _msg("user", "Design a URL shortener system. What are the key components?"),
            _msg("assistant", "Core components:\n1. **API layer** — POST /shorten returns a short code.\n2. **ID generator** — Base62 encoding of an auto-increment or distributed ID (e.g. Snowflake).\n3. **KV store** — Redis or DynamoDB mapping code → URL with TTL.\n4. **Redirect service** — GET /{code} → 301/302 to original URL.\n5. **Analytics pipeline** — async click counting via Kafka or SQS.\n\nFor scale, use read replicas and CDN caching of 301s.", "win"),
        ],
        "secondary_messages": [
            _msg("user", "Design a URL shortener system. What are the key components?"),
            _msg("assistant", "Key components: (1) REST API to accept long URLs and return short codes, (2) ID generation using Base62 encoding, (3) a fast key-value store (Redis) for code→URL lookups, (4) a redirect service returning HTTP 302, and (5) an analytics store for click metrics. Shard the KV store for high throughput."),
        ],
        "winner": "primary",
    },
    {
        "primary": "gemini-1-5-pro",
        "secondary": "llama-3-1-70b",
        "primary_messages": [
            _msg("user", "Write a poem about the ocean at dawn."),
            _msg("assistant", "The tide pulls back in silver sheets,\nRevealing stones the night concealed;\nThe sky bleeds pink where darkness beats\nA slow retreat across the field\nOf water stretching, vast and still —\nThe first light paints the world with will."),
        ],
        "secondary_messages": [
            _msg("user", "Write a poem about the ocean at dawn."),
            _msg("assistant", "Before the sun has claimed its throne,\nThe ocean breathes in shades of grey;\nA heron stands, impossibly alone,\nAnd watches as the dark gives way\nTo copper, rose, and amber flame —\nThe sea and sky one moment the same.", "win"),
        ],
        "winner": "secondary",
    },
    {
        "primary": "claude-3-5-sonnet",
        "secondary": "claude-3-haiku",
        "primary_messages": [
            _msg("user", "What is the time complexity of merge sort and why?"),
            _msg("assistant", "Merge sort is **O(n log n)** in all cases.\n\n- The array is split in half log n times (the depth of the recursion tree).\n- At each level, merging all subarrays processes every element exactly once → O(n) per level.\n- Total: O(n) × O(log n) = **O(n log n)**.\n\nSpace complexity is O(n) for the temporary merge buffer.", "win"),
        ],
        "secondary_messages": [
            _msg("user", "What is the time complexity of merge sort and why?"),
            _msg("assistant", "O(n log n). Splitting takes O(log n) levels; each merge pass is O(n). So total is O(n log n) time, O(n) auxiliary space."),
        ],
        "winner": "primary",
    },
]


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def _now_minus(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


async def seed_leaderboard(session, project_id: str, privacy: str, dry_run: bool = False) -> int:
    inserted = 0
    for i, preset in enumerate(_PRESETS):
        uid = preset["uid"]
        existing = await session.get(LeaderboardRow, (project_id, uid))
        if existing is not None:
            log.debug("leaderboard.skip", project_id=project_id, preset_uid=uid)
            continue
        stats = _LEADERBOARD_STATS[uid]
        row = LeaderboardRow(
            project_id=project_id,
            preset_uid=uid,
            preset=preset,
            rating=stats["rating"],
            peak=stats["peak"],
            matches=stats["matches"],
            wins=stats["wins"],
            losses=stats["losses"],
            ties=stats["ties"],
            updated_at=_now_minus(i * 3),  # stagger update times
            privacy=privacy,
        )
        session.add(row)
        inserted += 1
        log.info("leaderboard.insert", project_id=project_id, preset_uid=uid, rating=stats["rating"])
    return inserted


async def seed_chat_history(session, project_id: str, author_id: str) -> int:
    count = await session.scalar(
        select(func.count()).select_from(ChatHistoryRow).where(ChatHistoryRow.project_id == project_id)
    )
    if count and count > 0:
        log.info("chat_history.skip", project_id=project_id, existing=count)
        return 0

    inserted = 0
    for i, conv in enumerate(_CONVERSATIONS):
        row = ChatHistoryRow(
            uid=str(uuid.uuid4()),
            project_id=project_id,
            primary_preset=next(p for p in _PRESETS if p["uid"] == conv["primary"]),
            secondary_preset=next(p for p in _PRESETS if p["uid"] == conv["secondary"]),
            primary_messages=conv["primary_messages"],
            secondary_messages=conv["secondary_messages"],
            winner=conv["winner"],
            created_at=_now_minus(len(_CONVERSATIONS) - i),  # oldest first
            author_id=author_id,
        )
        session.add(row)
        inserted += 1
        log.info(
            "chat_history.insert",
            project_id=project_id,
            primary=conv["primary"],
            secondary=conv["secondary"],
            winner=conv["winner"],
        )
    return inserted


async def run(reset: bool) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.postgres.dsn(), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        if reset:
            log.warning("reset: truncating tables")
            await session.execute(text("TRUNCATE leaderboard, chat_history"))
            await session.commit()

        total_lb = 0
        total_ch = 0
        for project in _PROJECTS:
            total_lb += await seed_leaderboard(session, project["id"], project["privacy"])
            total_ch += await seed_chat_history(session, project["id"], author_id="seed-script")

        await session.commit()

    await engine.dispose()
    log.info("seed.done", leaderboard_rows=total_lb, chat_history_rows=total_ch)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Truncate tables before seeding")
    args = parser.parse_args()

    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    asyncio.run(run(reset=args.reset))


if __name__ == "__main__":
    main()
