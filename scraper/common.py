from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from .config import DEFAULT_TIMEOUT, OSAKA_PREFIX, REQUEST_DELAY_SECONDS, USER_AGENT

JST = ZoneInfo("Asia/Tokyo")
LOGGER = logging.getLogger(__name__)
ENTRY_DATE_PATTERN = re.compile(
    r"(?P<month>\d{1,2})\s*/\s*(?P<day>\d{1,2})\s*"
    r"\(\s*[\u6708\u706b\u6c34\u6728\u91d1\u571f\u65e5]\s*\)\s*"
    r"\u3016(?P<location>[^\u3017]+)\u3017\s*"
    r"(?P<entry>.+?)"
    r"(?=(?:\d{1,2}\s*/\s*\d{1,2}\s*\(\s*[\u6708\u706b\u6c34\u6728\u91d1\u571f\u65e5]\s*\)\s*\u3016)|"
    r"\u5730\u57df\u304b\u3089\u63a2\u3059|"
    r"\u90fd\u9053\u5e9c\u770c\u304b\u3089\u63a2\u3059|$)",
    re.DOTALL,
)
JP_DATE_PATTERN = re.compile(
    r"(?P<month>\d{1,2})\u6708(?P<day>\d{1,2})\u65e5(?:\([\u6708\u706b\u6c34\u6728\u91d1\u571f\u65e5]\))?"
)


@dataclass(frozen=True)
class EventRecord:
    date: str
    store: str
    event: str
    area: str
    source_url: str
    category: str
    updated_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            "date": self.date,
            "store": self.store,
            "event": self.event,
            "area": self.area,
            "source_url": self.source_url,
            "category": self.category,
            "updated_at": self.updated_at,
        }


def now_jst() -> datetime:
    return datetime.now(JST)


def iso_timestamp(dt: datetime | None = None) -> str:
    value = dt or now_jst()
    return value.replace(microsecond=0).isoformat()


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        }
    )
    return session


def polite_sleep() -> None:
    time.sleep(REQUEST_DELAY_SECONDS)


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    polite_sleep()
    return response.text


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "")
    return value.strip()


def extract_area(location_text: str) -> str | None:
    normalized = clean_text(location_text)
    if not normalized.startswith(OSAKA_PREFIX):
        return None

    area = normalized.removeprefix(OSAKA_PREFIX).strip(" \u3000")
    if not area:
        return None

    municipality_match = re.match(r"(.+?(?:\u5e02|\u753a|\u6751))", area)
    if municipality_match:
        municipality = municipality_match.group(1).strip()
        remainder = area[len(municipality) :].strip()
        if municipality.endswith("\u5e02"):
            ward_match = re.match(r"([^\s()\uFF08\uFF09]+\u533a)", remainder)
            if ward_match:
                return f"{municipality}{ward_match.group(1)}"
        return municipality

    ward_only_match = re.match(r"([^\s()\uFF08\uFF09]+\u533a)", area)
    if ward_only_match:
        return ward_only_match.group(1).strip()

    return area


def resolve_year(month: int, day: int, reference: datetime) -> date:
    candidate = date(reference.year, month, day)
    if candidate < reference.date() - timedelta(days=180):
        candidate = date(reference.year + 1, month, day)
    elif candidate > reference.date() + timedelta(days=180):
        candidate = date(reference.year - 1, month, day)
    return candidate


def parse_md_date(month: int, day: int, reference: datetime) -> str:
    return resolve_year(month, day, reference).isoformat()


def parse_jp_date(text: str, reference: datetime) -> str | None:
    match = JP_DATE_PATTERN.search(text)
    if not match:
        return None
    return parse_md_date(int(match.group("month")), int(match.group("day")), reference)


def normalize_store_name(raw: str, prefixes: Iterable[str] | None = None) -> str:
    value = clean_text(raw)
    for prefix in prefixes or ():
        if value.startswith(prefix):
            value = clean_text(value[len(prefix) :])
            break
    return value


def parse_entries_from_text(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    normalized_text = clean_text(text)
    for match in ENTRY_DATE_PATTERN.finditer(normalized_text):
        entries.append(
            {
                "month": match.group("month"),
                "day": match.group("day"),
                "location": clean_text(match.group("location")),
                "entry": clean_text(match.group("entry")),
            }
        )
    return entries


def build_record(
    *,
    event_date: str,
    store: str,
    event: str,
    area: str,
    source_url: str,
    updated_at: str,
) -> EventRecord | None:
    if not (event_date and store and event and area):
        return None

    return EventRecord(
        date=event_date,
        store=store,
        event=event,
        area=area,
        source_url=source_url,
        category="pachinko",
        updated_at=updated_at,
    )


def within_retention(event_date: str, reference: datetime, days: int) -> bool:
    target = date.fromisoformat(event_date)
    lower = reference.date()
    upper = reference.date() + timedelta(days=days)
    return lower <= target <= upper


def dedupe_records(records: Iterable[EventRecord]) -> list[EventRecord]:
    unique: dict[tuple[str, str, str, str], EventRecord] = {}
    for record in records:
        key = (record.date, record.store, record.event, record.source_url)
        unique[key] = record
    return sorted(unique.values(), key=lambda item: (item.date, item.area, item.store, item.event))


def write_json(path, records: Iterable[EventRecord]) -> None:
    serialized = [record.to_dict() for record in records]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(serialized, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
