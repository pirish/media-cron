# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir build

COPY pyproject.toml README.md ./
COPY media_cron/ media_cron/

RUN python -m build --wheel --outdir /dist

# Stage 2: Minimal Non-Root Runtime
FROM python:3.11-slim

LABEL org.opencontainers.image.title="media-cron" \
      org.opencontainers.image.description="Pluggable media file organizer, sanitizer, and cleaner CLI" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    MEDIA_CRON_CONFIG=/config/config.yaml \
    PATH="/home/appuser/.local/bin:$PATH"

# Create dedicated non-root user and directories for mount targets
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g 10001 -m -s /sbin/nologin appuser && \
    mkdir -p /data /config /cache && \
    chown -R appuser:appuser /data /config /cache

WORKDIR /data

# Copy and install the wheel package from builder
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

USER 10001:10001

ENTRYPOINT ["media-cron"]
CMD ["--help"]
