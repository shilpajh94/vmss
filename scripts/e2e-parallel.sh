#!/usr/bin/env bash
# Runs the e2e suite split across several Playwright containers at once,
# against a production build served by `vite preview`.
#
#   scripts/e2e-parallel.sh [shards] [pytest args...]
#   scripts/e2e-parallel.sh 5 test_responsive_matrix.py
#
# The dev server compiles every module on request, so a few browsers loading
# pages at once queue behind it and time out; prebuilt static files don't.
# `vite preview` reuses the dev server's /api proxy. Tests are collected once
# and dealt round-robin into `shards` lists. Each container needs about
# 400 MB of memory; lower `shards` on a smaller machine. Per-shard logs go to
# a temporary directory (printed at the end), not e2e-results/, which
# pytest-playwright empties when each run starts. Like `npm run e2e`, never
# run it alongside the API's pytest (shared Redis rate limits).
set -euo pipefail

shards="${1:-5}"
shift || true
cd "$(dirname "$0")/.."
tokens="${E2E_TOKENS_DIR:-$PWD/../VMSS_API/var/qa}"
port="${E2E_PREVIEW_PORT:-4173}"
logs="$(mktemp -d "${TMPDIR:-/tmp}/vmss-e2e-parallel.XXXXXX")"

npm run build --silent >"$logs/build.log" 2>&1
npx vite preview --port "$port" --strictPort >"$logs/preview.log" 2>&1 &
preview_pid=$!
trap 'kill "$preview_pid" 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  curl -sf -o /dev/null "http://localhost:$port/" && break
  sleep 1
done

run() {
  docker run --rm --network host --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$PWD":/w -v "$tokens":/tokens:ro -v "$logs":/shards:ro -w /w/e2e vmss-e2e:local \
    python -m pytest --base-url "http://localhost:$port" "$@"
}

run -q --collect-only "$@" 2>/dev/null | grep '::' >"$logs/ids.txt" || true
total=$(wc -l <"$logs/ids.txt")
if [ "$total" -eq 0 ]; then
  echo "no tests collected" >&2
  exit 1
fi
awk -v n="$shards" -v dir="$logs" '{ print > (dir "/shard-" ((NR - 1) % n) ".txt") }' "$logs/ids.txt"
echo "running $total tests in $shards containers against the production build"

pids=()
for list in "$logs"/shard-*.txt; do
  name="$(basename "$list" .txt)"
  # Each shard keeps its own artifacts folder; a shared one would be
  # emptied by every container as it starts.
  run -q --tb=short --output "e2e-results/$name" "@/shards/$(basename "$list")" >"$logs/$name.log" 2>&1 &
  pids+=("$!")
done

status=0
for pid in "${pids[@]}"; do
  wait "$pid" || status=1
done
for log in "$logs"/shard-*.log; do
  echo "== $(basename "$log" .log): $(tail -n 1 "$log")"
  grep -E '^(FAILED|ERROR)' "$log" || true
done
echo "logs: $logs"
exit "$status"
