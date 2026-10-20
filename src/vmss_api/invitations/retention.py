"""Backup half of the invitation retention purge (`tasks.py`): serializes the
rows about to be deleted into one gzipped JSONL object in the storage tier and
proves it reads back with the expected record count — only then may the caller
delete anything. Backups hold visitor PII, so they never leave the storage
tier: no presigned URL is ever generated for them.
"""

import gzip
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from vmss_api.core import storage


class BackupVerificationError(RuntimeError):
    """The stored backup did not read back with the expected record count."""


def _encode(records: list[tuple[str, dict[str, Any]]]) -> bytes:
    lines = (
        json.dumps({"table": table, "row": row}, default=str, separators=(",", ":"))
        for table, row in records
    )
    return gzip.compress(("\n".join(lines) + "\n").encode("utf-8"))


def _count_records(payload: bytes) -> int:
    text = gzip.decompress(payload).decode("utf-8")
    return sum(1 for line in text.splitlines() if line)


async def write_verified_backup(
    tenant_id: uuid.UUID, records: list[tuple[str, dict[str, Any]]], *, run_date: datetime
) -> str:
    """Saves `records` and returns the storage key, raising
    `BackupVerificationError` (or whatever the storage backend raises) if the
    object can't be written or doesn't read back intact.
    """
    category = f"backups/invitations/{run_date.astimezone(UTC).date().isoformat()}"
    key = await storage.save(tenant_id, category, _encode(records), "application/gzip")
    stored = _count_records(await storage.load(key))
    if stored != len(records):
        raise BackupVerificationError(
            f"backup {key} holds {stored} records, expected {len(records)}"
        )
    return key
