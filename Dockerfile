FROM ghcr.io/astral-sh/uv:0.11.2 AS uv

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    CHARACTER_QUOTES_DATABASE=/data/character_quotes.sqlite3 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev \
    && useradd --create-home --uid 10001 app \
    && mkdir /data \
    && chown app:app /data

USER app

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).read()" || exit 1

CMD ["uvicorn", "character_quotes.api:app", "--host", "0.0.0.0", "--port", "8000"]
