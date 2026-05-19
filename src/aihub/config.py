from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

VAULT_SECRETS_PATH = os.environ.get("VAULT_SECRETS_PATH", "/vault/secrets/env")


def _find_config() -> Path:
    if env := os.environ.get("AIHUB_CONFIG"):
        return Path(env)
    src_relative = Path(__file__).resolve().parents[2] / "config.yaml"
    if src_relative.exists():
        return src_relative
    return Path("config.yaml")


CONFIG_PATH = _find_config()


def _load_vault_secrets(path: str | Path) -> dict[str, str]:
    """Load secrets from a vault sidecar file.

    Supported formats (auto-detected):
        KEY=value
        export KEY=value
        KEY: value
    """
    p = Path(path)
    if not p.exists():
        return {}
    secrets: dict[str, str] = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        if ": " in line:
            key, _, value = line.partition(": ")
        elif "=" in line:
            key, _, value = line.partition("=")
        else:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        secrets[key.strip()] = value
    return secrets


def _resolve_vault_refs(text: str, secrets: dict[str, str]) -> str:
    for key, value in secrets.items():
        text = text.replace(f"vault:{key}", value)
    return text


@dataclass(frozen=True)
class PoolConfig:
    size: int = 5          # number of persistent connections per worker
    max_overflow: int = 10  # extra connections allowed beyond size
    timeout: float = 30.0  # seconds to wait for a connection before raising
    recycle: int = 1800    # recycle connections older than this many seconds


@dataclass(frozen=True)
class PostgresConfig:
    uri: str        # e.g. "postgresql://host1:5432,host2:5432" — scheme optional, multi-host supported
    database: str
    user: str
    password: str   # mapped from 'pass' in yaml (reserved keyword)
    pool: PoolConfig = PoolConfig()

    def dsn(self) -> str:
        from urllib.parse import quote, urlparse

        raw = self.uri if "://" in self.uri else f"postgresql://{self.uri}"
        host_part = urlparse(raw).netloc  # preserves comma-separated hosts as-is
        pw = quote(self.password, safe="")
        return f"postgresql+asyncpg://{self.user}:{pw}@{host_part}/{self.database}"


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    root_path: str = ""
    timeout_keep_alive: int = 65
    silence_probes: bool = True
    debug: bool = False


@dataclass(frozen=True)
class Settings:
    postgres: PostgresConfig
    server: ServerConfig = ServerConfig()


def load_config(path: str | Path) -> Settings:
    text = Path(path).read_text()
    text = _resolve_vault_refs(text, _load_vault_secrets(VAULT_SECRETS_PATH))
    text = os.path.expandvars(text)
    raw = yaml.safe_load(text)
    pg = raw["postgres"]
    return Settings(
        postgres=PostgresConfig(
            uri=pg["uri"],
            database=pg["database"],
            user=pg["user"],
            password=pg["pass"],
            pool=PoolConfig(**pg.get("pool", {})),
        ),
        server=ServerConfig(**raw.get("server", {})),
    )


@lru_cache
def get_settings() -> Settings:
    return load_config(CONFIG_PATH)
