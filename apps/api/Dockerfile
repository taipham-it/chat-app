FROM ghcr.io/astral-sh/uv:0.11.28 AS uv

FROM python:3.13-slim AS builder
WORKDIR /app
ENV UV_LINK_MODE=copy
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
RUN addgroup --system messenger && adduser --system --ingroup messenger messenger
COPY --from=builder --chown=messenger:messenger /app/.venv ./.venv
COPY --chown=messenger:messenger alembic.ini ./
COPY --chown=messenger:messenger migrations ./migrations
COPY --chown=messenger:messenger app ./app
USER messenger
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" || exit 1
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
