from __future__ import annotations

import logging
import re
from datetime import datetime

import requests

from ..common import build_record, clean_text, fetch_html, parse_jp_date, soup_from_html

LOGGER = logging.getLogger(__name__)

SOURCES = [
    ("https://aims777.com/syuzai/aimstar_gyoku/", "\u30a8\u30a4\u30e0\u30b9\u30bf\u30fc\u7389"),
    ("https://aims777.com/syuzai/aimstar_chogyoku/", "\u30a8\u30a4\u30e0\u30b9\u30bf\u30fc\u8d85\u7389"),
    ("https://aims777.com/syuzai/aimstar_girl_gyoku/", "\u30a8\u30a4\u30e0\u30ba\u30ac\u30fc\u30eb\u7389"),
]

OSAKA_BLOCK_PATTERN = re.compile(
    r"(?P<date>\d{1,2}\u6708\d{1,2}\u65e5(?:\([\u6708\u706b\u6c34\u6728\u91d1\u571f\u65e5]\))?)\s*"
    r"(?P<pref>\u5927\u962a(?:\u5e9c)?)\s*"
    r"(?P<store>[^\n\u3010\u3011\[\]0-9]+?\u5e97)"
)
AREA_PATTERN = re.compile(
    r"\u5927\u962a\u5e9c(?P<area>[^0-9()\uFF08\uFF09\s]+?(?:\u5e02|\u533a|\u753a|\u6751))"
)


def _extract_area(text: str) -> str | None:
    match = AREA_PATTERN.search(text)
    if match:
        return clean_text(match.group("area"))
    return None


def scrape(session: requests.Session, reference: datetime, updated_at: str) -> list:
    records = []

    for url, event_name in SOURCES:
        html = fetch_html(session, url)
        soup = soup_from_html(html)
        page_text = soup.get_text("\n", strip=True)

        seen: set[tuple[str, str]] = set()
        for match in OSAKA_BLOCK_PATTERN.finditer(page_text):
            block_text = page_text[match.start() : match.start() + 500]
            event_date = parse_jp_date(match.group("date"), reference)
            store = clean_text(match.group("store"))
            area = _extract_area(block_text)
            if not event_date or not area:
                continue

            key = (event_date, store)
            if key in seen:
                continue
            seen.add(key)

            record = build_record(
                event_date=event_date,
                store=store,
                event=event_name,
                area=area,
                source_url=url,
                updated_at=updated_at,
            )
            if record:
                records.append(record)

    LOGGER.info("aims: collected %s events", len(records))
    return records
