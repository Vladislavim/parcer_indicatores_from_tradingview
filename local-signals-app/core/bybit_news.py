from __future__ import annotations

import copy
import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests


ANNOUNCEMENTS_URL = "https://announcements.bybit.com/en/?category=delistings"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)
SYMBOL_RE = re.compile(r"\b([A-Z0-9]{2,20})USDT\b")
DELIST_AT_RE = re.compile(
    r"\b(?:at|on)\s+([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}(?:,\s+\d{1,2}:\d{2}(?:AM|PM)\s+UTC)?)"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None

    for fmt in ("%b %d, %Y, %I:%M%p UTC", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


@dataclass
class DelistingEvent:
    symbol: str
    title: str
    description: str
    url: str
    published_at: datetime
    delist_at: Optional[datetime]
    market_type: str
    object_id: str

    @property
    def hours_since_publish(self) -> float:
        return (_utc_now() - self.published_at).total_seconds() / 3600.0

    @property
    def hours_to_delist(self) -> float:
        if not self.delist_at:
            return 9999.0
        return (self.delist_at - _utc_now()).total_seconds() / 3600.0


@dataclass
class DelistingBias:
    active: bool
    symbol: str
    title: str = ""
    url: str = ""
    reason: str = ""
    score: int = 0
    hours_since_publish: float = 0.0
    hours_to_delist: float = 9999.0
    hard_block: bool = False
    flatten_now: bool = False


class BybitAnnouncementFeed:
    def __init__(self, ttl_sec: int = 300, pages: int = 2):
        self.ttl_sec = max(60, int(ttl_sec))
        self.pages = max(1, int(pages))
        self._lock = threading.Lock()
        self._cached_events: list[DelistingEvent] = []
        self._cached_at_ts: float = 0.0

    def get_delisting_events(self) -> list[DelistingEvent]:
        now_ts = _utc_now().timestamp()
        with self._lock:
            if self._cached_events and (now_ts - self._cached_at_ts) < self.ttl_sec:
                return copy.deepcopy(self._cached_events)

        events = self._load_events()
        with self._lock:
            self._cached_events = copy.deepcopy(events)
            self._cached_at_ts = now_ts
        return events

    def get_symbol_bias(self, symbol: str) -> Optional[DelistingBias]:
        key = str(symbol or "").upper().strip()
        if not key:
            return None

        events = [
            event for event in self.get_delisting_events()
            if event.symbol == key
        ]
        if not events:
            return None

        event = sorted(events, key=lambda item: item.published_at, reverse=True)[0]
        hours_since_publish = event.hours_since_publish
        hours_to_delist = event.hours_to_delist

        if hours_to_delist <= 0:
            return DelistingBias(
                active=False,
                symbol=key,
                title=event.title,
                url=event.url,
                reason="delisting window already passed",
                hours_since_publish=hours_since_publish,
                hours_to_delist=hours_to_delist,
                hard_block=True,
                flatten_now=True,
            )

        if hours_to_delist < 6:
            return DelistingBias(
                active=False,
                symbol=key,
                title=event.title,
                url=event.url,
                reason=f"delisting in {hours_to_delist:.1f}h, no new entries",
                hours_since_publish=hours_since_publish,
                hours_to_delist=hours_to_delist,
                hard_block=True,
                flatten_now=True,
            )

        if hours_since_publish > 96:
            return DelistingBias(
                active=False,
                symbol=key,
                title=event.title,
                url=event.url,
                reason="announcement is stale",
                hours_since_publish=hours_since_publish,
                hours_to_delist=hours_to_delist,
            )

        score = 3 if hours_since_publish <= 24 else 2 if hours_since_publish <= 72 else 1
        return DelistingBias(
            active=True,
            symbol=key,
            title=event.title,
            url=event.url,
            reason=f"official Bybit delisting notice, T-{hours_to_delist:.1f}h",
            score=score,
            hours_since_publish=hours_since_publish,
            hours_to_delist=hours_to_delist,
            hard_block=False,
            flatten_now=False,
        )

    def _load_events(self) -> list[DelistingEvent]:
        out: list[DelistingEvent] = []
        seen: set[str] = set()

        for page in range(1, self.pages + 1):
            url = ANNOUNCEMENTS_URL if page == 1 else f"{ANNOUNCEMENTS_URL}&page={page}"
            try:
                response = requests.get(url, headers=REQUEST_HEADERS, timeout=20)
                response.raise_for_status()
                payload = self._parse_next_data(response.text)
                items = (
                    payload.get("props", {})
                    .get("pageProps", {})
                    .get("articleInitEntity", {})
                    .get("list", [])
                )
            except Exception:
                continue

            for item in items:
                event = self._item_to_event(item)
                if not event:
                    continue
                if event.object_id in seen:
                    continue
                seen.add(event.object_id)
                out.append(event)

        return sorted(out, key=lambda item: item.published_at, reverse=True)

    @staticmethod
    def _parse_next_data(text: str) -> dict[str, Any]:
        match = NEXT_DATA_RE.search(str(text or ""))
        if not match:
            raise ValueError("Bybit announcements payload not found")
        return json.loads(match.group(1))

    def _item_to_event(self, item: dict[str, Any]) -> Optional[DelistingEvent]:
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        if not title:
            return None

        market_type = "perpetual" if "perpetual contract" in title.lower() else "spot"
        symbols = self._extract_symbols(title, description)
        if not symbols:
            return None

        published_raw = item.get("publish_time") or item.get("date_timestamp")
        published_at = datetime.fromtimestamp(int(published_raw), tz=timezone.utc)
        delist_at = self._extract_delist_at(title, description)
        article_url = str(item.get("url") or "").strip()
        if article_url.startswith("/"):
            article_url = f"https://announcements.bybit.com/en{article_url}"

        return DelistingEvent(
            symbol=symbols[0],
            title=title,
            description=description,
            url=article_url,
            published_at=published_at,
            delist_at=delist_at,
            market_type=market_type,
            object_id=str(item.get("objectID") or article_url or title),
        )

    @staticmethod
    def _extract_symbols(title: str, description: str) -> list[str]:
        haystack = f"{title} {description}".upper()
        symbols: list[str] = []
        for match in SYMBOL_RE.findall(haystack):
            token = str(match).strip().upper()
            if token and token not in symbols:
                symbols.append(token)
        return symbols

    @staticmethod
    def _extract_delist_at(title: str, description: str) -> Optional[datetime]:
        haystack = f"{description} {title}"
        match = DELIST_AT_RE.search(haystack)
        if not match:
            return None
        return _parse_dt(match.group(1))
