from __future__ import annotations

from prometheus_client import Counter, Histogram

DB_QUERY_SECONDS = Histogram(
    "aihub_db_query_seconds",
    "Database query latency in seconds",
    ["operation"],
)

DB_ERRORS_TOTAL = Counter(
    "aihub_db_errors_total",
    "Database query failures",
    ["operation"],
)
