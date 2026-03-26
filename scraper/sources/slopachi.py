from __future__ import annotations

import logging
import re
from datetime import datetime

import requests

from ..common import build_record, clean_text, extract_area, fetch_html, parse_md_date, soup_from_html

LOGGER = logging.getLogger(__name__)

SOURCES = [
    "https://777.slopachi-station.com/janjan_schedule/",
    "https://777.slopachi-station.com/renjiro_schedule/",
    "https://777.slopachi-station.com/raiten_syuzai002_schedule/",
    "https://777.slopachi-station.com/raiten_syuzai006_schedule/",
    "https://777.slopachi-station.com/keihin_nyuka_schedule/",
]

DATE_PATTERN = re.compile(r"(?P<month>\d{1,2})/(?P<day>\d{1,2})\s*\([\u6708\u706b\u6c34\u6728\u91d1\u571f\u65e5]\)")
AREA_PATTERN = re.compile(r"\u3010(?P<location>[^\u3011]+)\u3011")
ENTRY_SPLIT_PATTERN = re.compile(r"\u3000+")
HIRAGANA_SLOPACHI = "\u3059\u308d\u3071\u3061"


def _iter_text_nodes(soup):
    for value in soup.stripped_strings:
        text = clean_text(value)
        if text:
            yield text


def _parse_anchor_text(text: str) -> tuple[str | None, str | None]:
    parts = [clean_text(part) for part in ENTRY_SPLIT_PATTERN.split(text) if clean_text(part)]
    if len(parts) < 2:
        return None, None
    return parts[0], parts[-1]


def scrape(session: requests.Session, reference: datetime, updated_at: str) -> list:
    records = []

    for url in SOURCES:
        html = fetch_html(session, url)
        soup = soup_from_html(html)

        current_date = None
        current_area = None

        for node in soup.descendants:
            if getattr(node, "name", None) == "a":
                href = node.get("href")
                if not href or "/shop_data/" not in href:
                    continue

                anchor_text = clean_text(node.get_text(" ", strip=True))
                event_name, store = _parse_anchor_text(anchor_text)
                if not event_name or not store or not current_date or not current_area:
                    continue

                if url.endswith("/keihin_nyuka_schedule/") and HIRAGANA_SLOPACHI not in event_name:
                    continue

                record = build_record(
                    event_date=current_date,
                    store=store,
                    event=event_name,
                    area=current_area,
                    source_url=url,
                    updated_at=updated_at,
                )
                if record:
                    records.append(record)
                continue

            if getattr(node, "name", None) is not None:
                continue

            text = clean_text(str(node))
            if not text:
                continue

            date_match = DATE_PATTERN.search(text)
            if date_match:
                current_date = parse_md_date(
                    int(date_match.group("month")),
                    int(date_match.group("day")),
                    reference,
                )
                continue

            area_match = AREA_PATTERN.search(text)
            if area_match:
                current_area = extract_area(area_match.group("location"))

    LOGGER.info("slopachi: collected %s events", len(records))
    return records
