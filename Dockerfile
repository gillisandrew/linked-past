FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY linked_past/ linked_past/
RUN uv sync --no-dev --frozen

ENV PATH="/app/.venv/bin:$PATH"
ENV LINKED_PAST_DATA_DIR="/app/data"
EXPOSE 8000

ENTRYPOINT ["linked-past-server"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
