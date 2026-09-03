#!/bin/sh
set -e

mkdir -p /var/storage

# Optional: make sure the application user can write to it
chown -R appuser:appuser /var/storage 2>/dev/null || true

echo "Storage directory ready: /var/storage"

exec "$@"