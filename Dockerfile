FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY dprr_mcp/ dprr_mcp/
RUN uv sync --no-dev --frozen

FROM python:3.13-slim

WORKDIR /app
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

ENTRYPOINT ["dprr-server"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
