"""org-structure "Company and Tenant Timezones Resolve Consistently,
Including Legacy Offset Values" (core/timezones.py)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core import timezones
from vmss_api.core.timezones import display_name, parse_timezone, resolve_timezone, sql_name


@pytest.mark.parametrize(
    ("value", "offset"),
    [
        ("GMT+05:30", timedelta(hours=5, minutes=30)),
        ("UTC-04:00", timedelta(hours=-4)),
        ("gmt+0530", timedelta(hours=5, minutes=30)),
        ("UTC+9", timedelta(hours=9)),
        ("GMT+00:00", timedelta(0)),
    ],
)
def test_legacy_offset_values_parse_to_fixed_offsets(value: str, offset: timedelta) -> None:
    tz = parse_timezone(value)
    assert tz is not None
    assert tz.utcoffset(datetime(2026, 1, 1)) == offset


@pytest.mark.parametrize("value", ["", "   ", None, "Mars/Olympus", "GMT+25:00", "UTC+05:75"])
def test_unparseable_values_return_none(value: str | None) -> None:
    assert parse_timezone(value) is None


def test_iana_name_is_honoured() -> None:
    assert display_name(resolve_timezone(("company", "Asia/Kolkata"))) == "Asia/Kolkata"


def test_fallback_logs_a_warning_naming_the_value(monkeypatch) -> None:
    warnings: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        timezones.logger, "warning", lambda event, **kw: warnings.append((event, kw))
    )

    tz = resolve_timezone(("company", "Mars/Olympus"), ("tenant", "Asia/Kolkata"))

    assert display_name(tz) == "Asia/Kolkata"
    assert warnings == [("invalid_timezone", {"source": "company", "timezone": "Mars/Olympus"})]


def test_everything_invalid_falls_back_to_utc() -> None:
    assert display_name(resolve_timezone(("company", "bogus"), ("tenant", None))) == "UTC"


@pytest.mark.parametrize(
    ("value", "expected_local"),
    [
        ("GMT+05:30", datetime(2026, 1, 1, 5, 30)),
        ("UTC-04:00", datetime(2025, 12, 31, 20, 0)),
        ("Asia/Kolkata", datetime(2026, 1, 1, 5, 30)),
    ],
)
async def test_sql_name_converts_in_the_right_direction(
    db_session: AsyncSession, value: str, expected_local: datetime
) -> None:
    """A bare `+05:30` is POSIX in Postgres (sign inverted) — `sql_name`
    must spell fixed offsets so Postgres agrees with Python."""
    tz = parse_timezone(value)
    assert tz is not None
    instant = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    local = (await db_session.execute(select(func.timezone(sql_name(tz), instant)))).scalar_one()
    assert local == expected_local
    assert instant.astimezone(tz).replace(tzinfo=None) == expected_local
