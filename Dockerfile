FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev --no-editable

# ---- test stage: adds dev deps + tests on top of builder ----
FROM builder AS test
RUN uv sync --frozen --no-editable
COPY tests/ tests/
COPY config.yaml .
CMD ["uv", "run", "pytest", "tests/", "-v", "--tb=short"]

# ---- runtime stage ----
FROM python:3.13-slim AS runtime

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY config.yaml .
COPY entrypoint.py .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 5000

CMD ["python", "-m", "entrypoint"]
