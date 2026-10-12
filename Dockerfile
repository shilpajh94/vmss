```dockerfile
FROM pitsdevops.azurecr.io/pits-linux-base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/bin" sh \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PYTHON=3.13

WORKDIR /app

# Verify uv and Python selection
RUN uv --version \
    && python3 --version \
    && uv python find

COPY pyproject.toml uv.lock README.md ./

# Install dependencies without installing the application
RUN uv sync --frozen --no-dev --no-install-project -v

COPY src/ ./src/

# Install the application and remaining dependencies
RUN uv sync --frozen --no-dev --no-editable -v


FROM pitsdevops.azurecr.io/pits-linux-base AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /opt/python /opt/python
COPY --from=builder /app/.venv /app/.venv

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini
COPY alembic_tenant/ ./alembic_tenant/
COPY alembic_tenant.ini ./alembic_tenant.ini
COPY scripts/ ./scripts/

COPY .secrets/firebase-adminsdk.json /app/.secrets/firebase-adminsdk.json
COPY entrypoint.sh /entrypoint.sh

# Remove Windows CRLF if present and make executable
RUN sed -i 's/\r$//' /entrypoint.sh \
    && chmod 755 /entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

CMD ["uvicorn", "vmss_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```