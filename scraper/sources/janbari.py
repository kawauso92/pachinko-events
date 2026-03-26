from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin

import requests

from ..common import build_record, clean_text, fetch_html, parse_jp_date, soup_from_html

LOGGER = logging.getLogger(__name__)

ARCHIVE_URL = "https://jb-portal.com/archive/janbari-sennyu/"
DETAIL_AREA_PATTERN = re.compile(
    r"\u5927\u962a(?:\u5e9c)?(?P<area>[^0-9()\uFF08\uFF09\s]+?(?:\u5e02|\u533a|\u753a|\u6751))"
)
TAMA_PATTERN = re.compile(
    r"\u30b8\u30e3\u30f3\u30d0\u30ea[\uff08(](?P<suffix>(?:\u8d85)?\u7389)[)\uff09]"
)


def _extract_entries(soup, reference: datetime) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    current_date = None

    for tag in soup.find_all(["h4", "a"]):
        text = clean_text(tag.get_text(" ", strip=True))
        if not text:
            continue

        parsed_date = parse_jp_date(text, reference)
        if tag.name == "h4" and parsed_date:
            current_date = parsed_date
            continue

        if tag.name != "a" or not current_date:
            continue

        if "\u5927\u962a" not in text or "\u30b8\u30e3\u30f3\u30d0\u30ea" not in text:
            continue

        href = tag.get("href")
        if not href:
            continue

        entries.append((current_date, text, urljoin(ARCHIVE_URL, href)))

    return entries


def _parse_detail_for_area_and_event(session: requests.Session, detail_url: str) -> tuple[str | None, str | None]:
    html = fetch_html(session, detail_url)
    page_text = clean_text(soup_from_html(html).get_text("\n", strip=True))

    area_match = DETAIL_AREA_PATTERN.search(page_text)
    event_match = TAMA_PATTERN.search(page_text)
    if not area_match or not event_match:
        return None, None

    suffix = event_match.group("suffix")
    return clean_text(area_match.group("area")), f"\u30b8\u30e3\u30f3\u30d0\u30ea\uff08{suffix}\uff09"


def _store_from_link_text(text: str) -> str:
    cleaned = re.sub(r"^\u5927\u962a\s+", "", text)
    cleaned = re.sub(r"\s+\u30b8\u30e3\u30f3\u30d0\u30ea.+$", "", cleaned)
    return clean_text(cleaned)


def scrape(session: requests.Session, reference: datetime, updated_at: str) -> list:
    html = fetch_html(session, ARCHIVE_URL)
    soup = soup_from_html(html)

    records = []
    for event_date, link_text, detail_url in _extract_entries(soup, reference):
        try:
            area, event_name = _parse_detail_for_area_and_event(session, detail_url)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("janbari detail skipped: %s (%s)", detail_url, exc)
            continue

        if not area or not event_name:
            continue

        record = build_record(
            event_date=event_date,
            store=_store_from_link_text(link_text),
            event=event_name,
            area=area,
            source_url=detail_url,
            updated_at=updated_at,
        )
        if record:
            records.append(record)

    LOGGER.info("janbari: collected %s events", len(records))
    return records
