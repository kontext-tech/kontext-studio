# Build stage
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /workspace

# Copy the workspace files needed to resolve kontext-api. The uv workspace and
# the generated SDK client are Python-only (py/), so ts/ and scripts/ are not
# required to resolve or run this package.
COPY pyproject.toml uv.lock* ./
COPY py/ ./py/

# Install kontext-api and its workspace dependencies.
# --no-editable installs real package files (no source-referencing .pth), so the
# runtime image only needs the venv; --relocatable keeps that venv portable.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv --relocatable && \
    uv sync --frozen --no-dev --no-editable --package kontext-api

# Runtime stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security (no home directory created by default)
RUN groupadd -r api && useradd -r -g api api

# Set working directory
WORKDIR /app

# Copy the self-contained venv from the builder stage
COPY --from=builder --chown=api:api /workspace/.venv /app/.venv

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER api

# Expose port
EXPOSE 8000

# Health check (stdlib only: `requests` is not a runtime dependency)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ping').read()"

# Run the application
CMD ["uvicorn", "kontext.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
