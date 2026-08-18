# ─── Stage 1: Builder ────────────────────────────────────────────────────────
FROM pitsdevops.azurecr.io/pits-linux-base AS builder

# Install uv (fast Python package manager)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies into /app/.venv
RUN uv sync --frozen --no-dev --no-editable

# ─── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM pitsdevops.azurecr.io/pits-linux-base AS runtime

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application source
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
