# Stage 1: Build viewer (runs on builder's native arch — output is static JS/CSS)
FROM --platform=$BUILDPLATFORM node:22-slim AS viewer-build
WORKDIR /app/packages/linked-past-viewer
COPY packages/linked-past-viewer/package.json packages/linked-past-viewer/package-lock.json ./
RUN npm ci
COPY packages/linked-past-viewer/ .
RUN npm run build

# Stage 2: Python runtime (multi-arch: amd64, arm64)
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md datasets.yaml ./
COPY packages/linked-past/ packages/linked-past/
COPY packages/linked-past-store/ packages/linked-past-store/
RUN uv sync --no-dev --frozen

# Copy built viewer assets (platform-independent static files)
COPY --from=viewer-build /app/packages/linked-past-viewer/dist/ packages/linked-past-viewer/dist/

ENV PATH="/app/.venv/bin:$PATH"
ENV LINKED_PAST_DATA_DIR="/data"
# Set to comma-separated dataset names (or "all") to auto-download on startup
# ENV LINKED_PAST_DATASETS="all"

# Data and index caches persist via volume
VOLUME /data

EXPOSE 8000

ENTRYPOINT ["linked-past-server"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
