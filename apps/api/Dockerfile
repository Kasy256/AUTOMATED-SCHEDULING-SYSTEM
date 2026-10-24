# syntax=docker/dockerfile:1
# Build from the repo root: docker build -f apps/api/Dockerfile .
FROM ghcr.io/astral-sh/uv:0.13.0-python3.12-trixie-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/engine/pyproject.toml packages/engine/
COPY apps/api/pyproject.toml apps/api/
RUN uv sync --frozen --no-dev --no-install-workspace --package cartlyf-api
COPY packages/engine packages/engine
COPY apps/api apps/api
RUN uv sync --frozen --no-dev --no-editable --package cartlyf-api

FROM python:3.12-slim-trixie AS runtime
RUN useradd --system --uid 10001 --no-create-home cartlyf
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY apps/api/alembic.ini apps/api/alembic.ini
COPY apps/api/migrations apps/api/migrations
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8000
# Access lines come from RequestLog as JSON. Client IPs (rate limits) come from X-Forwarded-For,
# trusted only from FORWARDED_ALLOW_IPS (the platform proxy's range; uvicorn's default is 127.0.0.1).
CMD ["uvicorn", "cartlyf_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000",      "--no-access-log", "--proxy-headers"]
