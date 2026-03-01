FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY dprr_mcp/ dprr_mcp/
RUN uv sync --no-dev --frozen

# Copy local data and pre-build the Oxigraph store so the container starts instantly
COPY data/dprr.ttl /app/data/dprr.ttl
RUN DPRR_DATA_DIR=/app/data \
    .venv/bin/python -c "from dprr_mcp.store import ensure_initialized; ensure_initialized()"

FROM python:3.13-slim

RUN groupadd --system dprr && useradd --system --gid dprr dprr

WORKDIR /app
COPY --from=builder --chown=dprr:dprr /app /app

USER dprr
ENV PATH="/app/.venv/bin:$PATH"
ENV DPRR_DATA_DIR="/app/data"
EXPOSE 8000

ENTRYPOINT ["dprr-server"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
