# ─── Stage 1: Builder ────────────────────────────────────────────────────────
FROM pitsdevops.azurecr.io/pits-linux-base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/bin" sh \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/python

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/

RUN uv sync --frozen --no-dev --no-editable


# ─── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM pitsdevops.azurecr.io/pits-linux-base AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python + virtual environment
COPY --from=builder /opt/python /opt/python
COPY --from=builder /app/.venv /app/.venv

# Application
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini
COPY alembic_tenant/ ./alembic_tenant/
COPY alembic_tenant.ini ./alembic_tenant.ini
COPY scripts/ ./scripts/

# Firebase credential is kept inside the image outside the PVC mount.
# The entrypoint will copy it to /var/storage after Kubernetes mounts the PVC.
COPY .secrets/firebase-adminsdk.json /app/.secrets/firebase-adminsdk.json

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

CMD ["uvicorn", "vmss_api.main:app", "--host", "0.0.0.0", "--port", "8000"]