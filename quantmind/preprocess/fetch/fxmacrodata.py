"""FXMacroData fetch helpers for macroeconomic context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

DEFAULT_FXMACRODATA_BASE_URL = "https://api.fxmacrodata.com/v1"


@dataclass(frozen=True, slots=True)
class CalendarRelease:
    """One scheduled macroeconomic or central-bank release."""

    release: str
    name: str
    announcement_datetime_utc: str | None
    announcement_datetime_local: str | None
    release_date_confirmed: bool
    event_importance: str | None
    market_tier: int | None
    source: str | None
    source_url: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawCalendar:
    """Release-calendar payload for a single currency.

    ``releases`` holds the parsed rows; ``metadata`` preserves the FXMacroData
    envelope (currency, timezone, data quality) so the format layer can build
    knowledge items without a second request.
    """

    currency: str
    timezone: str | None
    url: str
    releases: tuple[CalendarRelease, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


async def fetch_fxmacrodata_calendar(
    currency: str = "usd",
    *,
    limit: int = 50,
    api_key: Optional[str] = None,
    base_url: str = DEFAULT_FXMACRODATA_BASE_URL,
    timeout: float = 30.0,
) -> RawCalendar:
    """Fetch official release-calendar rows from FXMacroData.

    Returns a frozen :class:`RawCalendar` in line with the fetch layer
    contract. No parsing beyond splitting rows from the response envelope --
    interpreting the rows is the format layer's job.
    """

    limit_count = max(1, min(int(limit), 100))
    currency_code = currency.lower()
    params: dict[str, str] = {"limit": str(limit_count)}

    url = f"{base_url.rstrip('/')}/calendar/{currency_code}"
    headers = {"User-Agent": "QuantMind/0.2 fxmacrodata-fetch"}
    if api_key:
        # Sent as a header so the key is never captured in request logs or
        # proxy access logs the way a query parameter would be.
        headers["X-API-Key"] = api_key

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()

    rows = payload.get("data")
    rows = rows[:limit_count] if isinstance(rows, list) else []
    releases = tuple(
        CalendarRelease(
            release=str(row.get("release", "")),
            name=str(row.get("name", "")),
            announcement_datetime_utc=row.get("announcement_datetime_utc"),
            announcement_datetime_local=row.get("announcement_datetime_local"),
            release_date_confirmed=bool(row.get("release_date_confirmed", False)),
            event_importance=row.get("event_importance"),
            market_tier=row.get("market_tier"),
            source=row.get("source"),
            source_url=row.get("source_url"),
            raw=row,
        )
        for row in rows
        if isinstance(row, dict)
    )
    metadata = {key: value for key, value in payload.items() if key != "data"}
    return RawCalendar(
        currency=str(payload.get("currency", currency_code)).upper(),
        timezone=payload.get("timezone"),
        url=url,
        releases=releases,
        metadata=metadata,
    )
