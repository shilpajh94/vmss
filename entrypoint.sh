#!/bin/sh
set -e

STORAGE_DIR="/app/var/storage"
FIREBASE_SOURCE="/app/.secrets/firebase-adminsdk.json"
FIREBASE_TARGET="${STORAGE_DIR}/firebase-adminsdk.json"

echo "Initializing storage directory: ${STORAGE_DIR}"

mkdir -p "${STORAGE_DIR}"

if [ -f "${FIREBASE_SOURCE}" ] && [ ! -f "${FIREBASE_TARGET}" ]; then
    echo "Copying Firebase credentials..."
    cp "${FIREBASE_SOURCE}" "${FIREBASE_TARGET}"
fi

echo "Storage directory contents:"
ls -lah "${STORAGE_DIR}"

echo "Starting application..."

exec "$@"