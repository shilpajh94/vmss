"""Moved to `core/masking.py` so `auth`/`platform` can mask identifiers
without importing a feature package; re-exported for existing imports."""

from vmss_api.core.masking import mask_identifier

__all__ = ["mask_identifier"]
