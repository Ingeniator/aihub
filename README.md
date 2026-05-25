# aihub

Async CRUD backend for the AI Arena suite. Stores **leaderboard entries** and **chat history** produced by model-vs-model arena sessions, groups them by project, and exposes them over a REST API.

Built with FastAPI + SQLAlchemy (asyncpg) + PostgreSQL. Includes Prometheus metrics, structured JSON logging, Vault secret injection, and multi-worker support out of the box.

---

## Features

| Area | Details |
|---|---|
| **REST API** | Projects, Leaderboard, Arena chat history — full CRUD with pagination |
| **Async I/O** | SQLAlchemy 2 async engine, asyncpg driver |
| **Observability** | Prometheus metrics (`/metrics`), multiprocess-safe; structlog JSON logs |
| **Health probes** | `/livez` (liveness), `/readyz` (readiness + DB check), `/health` (detailed) |
| **Config** | YAML file; supports `vault:KEY` secret refs and env-var substitution |
| **Multi-host PG** | Comma-separated host list, `target_session_attrs`, configurable SSL mode |
| **Connection pool** | Tunable size, overflow, timeout, recycle per `config.yaml` |

---

## API overview

### Projects
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/projects` | List all project IDs (union of leaderboard + history) |

### Leaderboard
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/projects/{project_id}/leaderboard` | List entries (filter by `privacy`, paginated) |
| `POST` | `/projects/{project_id}/leaderboard` | Create entry |
| `GET` | `/projects/{project_id}/leaderboard/{preset_uid}` | Get single entry |
| `PATCH` | `/projects/{project_id}/leaderboard/{preset_uid}` | Update entry |
| `DELETE` | `/projects/{project_id}/leaderboard/{preset_uid}` | Delete entry |

### Arena chat history
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/projects/{project_id}/arena/history` | List sessions (filter by `author_id`, date range) |
| `POST` | `/projects/{project_id}/arena/history` | Save a completed arena session |
| `GET` | `/projects/{project_id}/arena/history/{uid}` | Get single session |
| `PATCH` | `/projects/{project_id}/arena/history/{uid}` | Update session |
| `DELETE` | `/projects/{project_id}/arena/history/{uid}` | Delete session |

Interactive docs are available at `{root_path}/docs` (Swagger UI) once the service is running.

---

## Quick start

### Local (uv)

```bash
# 1. Install dependencies
uv sync

# 2. Start Postgres (or point config.yaml at an existing instance)
docker compose up -d postgres

# 3. Run dev server with auto-reload
make dev          # http://localhost:5000/ai/hub/docs
```

### Docker Compose (full stack)

```bash
make up           # builds image, starts postgres + aihub
make logs         # follow aihub logs
make down         # stop and remove containers
make down-v       # also remove postgres volume
```

Service is exposed at **http://localhost:5001** (mapped from container port 5000).

---

## Configuration

The service loads `config.yaml` from the project root (or the path in `AIHUB_CONFIG`).

```yaml
server:
  host: "0.0.0.0"
  port: 5000
  workers: 1
  root_path: "/ai/hub"   # ASGI root path prefix (e.g. behind a reverse proxy)
  silence_probes: true   # suppress /livez & /readyz from access logs
  debug: false

postgres:
  uri: "postgresql://localhost:5432"
  database: "aihub"
  user: "aihub"
  pass: "vault:POSTGRES_PASSWORD"   # resolved from Vault sidecar secrets
  target_session_attrs: "read-write"
  schema: "public"
  ssl_mode: "prefer"                # disable | prefer | require | verify-ca | verify-full
  pool:
    size: 5
    max_overflow: 10
    timeout: 30
    recycle: 1800
```

**Vault secrets** — place a sidecar file at `/vault/secrets/env` (override with `VAULT_SECRETS_PATH`).  
Supported formats: `KEY=value`, `export KEY=value`, `KEY: value`. Any `vault:KEY` placeholder in the YAML is replaced at startup.

**Environment variables** — standard `${VAR}` substitution is applied after vault resolution.

---

## Development

```bash
make test         # run pytest locally (SQLite in-memory, no Postgres needed)
make lint         # ruff check
make test-docker  # isolated Docker test runner
```

### Seeding sample data

```bash
make seed         # seed local DB (skips existing rows)
make seed-reset   # truncate tables and re-seed

make seed-docker        # seed via Docker
make seed-docker-reset  # truncate and re-seed via Docker
```

---

## Observability

### Prometheus metrics

`GET /metrics` — exposes default HTTP metrics (latency, request/response size, request count) plus DB connection pool stats. Multiprocess-safe: aggregates per-worker `.db` files when `PROMETHEUS_MULTIPROC_DIR` contains them, falls back to in-process registry otherwise.

### Structured logging

All log lines are emitted as JSON via **structlog**. Probe endpoints (`/livez`, `/readyz`) are silenced by default (`silence_probes: true`). Set `debug: true` to enable debug-level logs.

### Health probes

| Endpoint | Meaning |
|----------|---------|
| `GET /livez` | Always `200 {"status": "ok"}` — process is alive |
| `GET /readyz` | `200` if DB is reachable, `503` otherwise |
| `GET /health` | JSON breakdown: `{"status": "ok\|degraded", "components": {"postgres": "ok\|degraded"}}` |

---

## Project layout

```
aihub/
├── src/aihub/
│   ├── main.py           # FastAPI app, middleware, Prometheus setup
│   ├── config.py         # YAML config loader, Vault resolver
│   ├── database.py       # SQLAlchemy engine, ORM rows, session factory
│   ├── models.py         # Pydantic request/response schemas
│   ├── metrics.py        # Custom Prometheus counters and histograms
│   ├── logging_config.py # structlog setup
│   └── routes/
│       ├── projects.py       # GET /projects
│       ├── leaderboard.py    # CRUD /projects/{id}/leaderboard
│       └── chat_history.py   # CRUD /projects/{id}/arena/history
├── tests/
├── scripts/
│   └── seed.py           # DB seeder
├── config.yaml           # Local config (not committed with secrets)
├── config.docker.yaml    # Docker Compose config
├── docker-compose.yaml
├── Makefile
└── pyproject.toml
```

---

## Requirements

- Python ≥ 3.13
- PostgreSQL 14+ (or 17-alpine via Docker)
- [uv](https://github.com/astral-sh/uv) for local development
