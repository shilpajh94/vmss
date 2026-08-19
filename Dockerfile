# ─── Stage 1: Builder ────────────────────────────────────────────────────────
FROM pitsdevops.azurecr.io/pits-linux-base AS builder

# Install uv via standalone installer (no pip or external GHCR image required)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/bin" sh \
    && rm -rf /var/lib/apt/lists/*

# uv configurations for Docker builds:
# - UV_PYTHON_INSTALL_DIR: keeps managed Python in a fixed path to copy to runtime stage
# - UV_LINK_MODE=copy: avoids broken symlinks across multi-stage build
# - UV_COMPILE_BYTECODE=1: improves container startup performance
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/python

WORKDIR /app

# Copy dependency files and README first for layer caching
COPY pyproject.toml uv.lock README.md ./

# Install ONLY dependencies first (this caches the expensive part)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source code so the project itself can be built
COPY src/ ./src/

# Install the project itself
RUN uv sync --frozen --no-dev --no-editable


# ─── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM pitsdevops.azurecr.io/pits-linux-base AS runtime

WORKDIR /app

# Copy Python installation and virtual environment from builder stage
COPY --from=builder /opt/python /opt/python
COPY --from=builder /app/.venv /app/.venv

# Copy application source and migration files
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini
COPY alembic_tenant/ ./alembic_tenant/
COPY alembic_tenant.ini ./alembic_tenant.ini

# Ensure the venv binaries are on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "vmss_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
