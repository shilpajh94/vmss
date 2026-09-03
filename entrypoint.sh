#!/bin/sh
set -e

STORAGE_DIR="/var/storage"
FIREBASE_SOURCE="/app/.secrets/firebase-adminsdk.json"
FIREBASE_TARGET="${STORAGE_DIR}/firebase-adminsdk.json"

mkdir -p "${STORAGE_DIR}"

if [ -f "${FIREBASE_SOURCE}" ] && [ ! -f "${FIREBASE_TARGET}" ]; then
    cp "${FIREBASE_SOURCE}" "${FIREBASE_TARGET}"
fi

echo "Storage directory:"
ls -lah "${STORAGE_DIR}"

exec "$@"