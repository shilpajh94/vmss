"""One rule for turning a stored timezone string into a clock
(org-structure "Company and Tenant Timezones Resolve Consistently").

`Company.default_timezone` and `Tenant.timezone` are free text with no DB
`CHECK`. The web used to save labels like `GMT+05:30`, which `ZoneInfo`
rejects, so every such tenant silently ran on UTC. Those legacy offset
values now resolve to the equivalent fixed offset; only a value that is
neither an IANA name nor an offset falls through to the next candidate.
"""

import re
from datetime import timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from vmss_api.core.logging import logger

_OFFSET_PATTERN = re.compile(r"^(?:GMT|UTC)\s*([+-])(\d{1,2})(?::?(\d{2}))?$", re.IGNORECASE)
_UTC = ZoneInfo("UTC")


def parse_timezone(name: str | None) -> tzinfo | None:
    """An IANA zone, a fixed offset for a `GMT±HH:MM`/`UTC±HH:MM` value, or
    `None` when `name` is blank or neither."""
    if not name or not name.strip():
        return None
    value = name.strip()
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        pass
    match = _OFFSET_PATTERN.match(value)
    if match is None:
        return None
    sign, hours, minutes = match.group(1), int(match.group(2)), int(match.group(3) or 0)
    if hours > 14 or minutes >= 60:
        return None
    offset = timedelta(hours=hours, minutes=minutes)
    if offset == timedelta(0):
        return _UTC
    return timezone(-offset if sign == "-" else offset)


def resolve_timezone(*candidates: tuple[str, str | None]) -> tzinfo:
    """The first `(source, name)` candidate that parses, else UTC. An
    unparseable non-blank value is logged at WARNING (a recoverable anomaly,
    logging-observability.md §3) and skipped."""
    for source, name in candidates:
        tz = parse_timezone(name)
        if tz is not None:
            return tz
        if name and name.strip():
            logger.warning("invalid_timezone", source=source, timezone=name)
    return _UTC


def _offset_parts(tz: timezone) -> tuple[str, int, int]:
    offset = tz.utcoffset(None)
    total_minutes = int(offset.total_seconds() // 60)
    sign = "-" if total_minutes < 0 else "+"
    hours, minutes = divmod(abs(total_minutes), 60)
    return sign, hours, minutes


def display_name(tz: tzinfo) -> str:
    """The IANA key, or an ISO offset (`+05:30`) for a fixed offset — the
    form API clients and export headers show, and that `Intl` accepts."""
    if isinstance(tz, ZoneInfo):
        return tz.key
    if isinstance(tz, timezone):
        sign, hours, minutes = _offset_parts(tz)
        return f"{sign}{hours:02d}:{minutes:02d}"
    return "UTC"


def sql_name(tz: tzinfo) -> str:
    """A zone string Postgres' `timezone(zone, ts)` reads correctly. A bare
    `+05:30` would be taken as POSIX (sign inverted, i.e. UTC−05:30), so a
    fixed offset is spelt as an explicit POSIX spec instead."""
    if isinstance(tz, ZoneInfo):
        return tz.key
    if isinstance(tz, timezone):
        sign, hours, minutes = _offset_parts(tz)
        posix_sign = "-" if sign == "+" else "+"
        return f"<{sign}{hours:02d}{minutes:02d}>{posix_sign}{hours:02d}:{minutes:02d}"
    return "UTC"
