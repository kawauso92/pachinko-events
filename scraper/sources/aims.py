from __future__ import annotations

import logging
from datetime import datetime

import requests

from ..common import build_record, clean_text, fetch_html, parse_jp_date, soup_from_html

LOGGER = logging.getLogger(__name__)

SOURCES = [
    ("https://aims777.com/syuzai/aimstar_gyoku/", "\u30a8\u30a4\u30e0\u30b9\u30bf\u30fc\u7389"),
    ("https://aims777.com/syuzai/aimstar_chogyoku/", "\u30a8\u30a4\u30e0\u30b9\u30bf\u30fc\u8d85\u7389"),
]

OSAKA_TEXT = "\u5927\u962a"


def scrape(session: requests.Session, reference: datetime, updated_at: str) -> list:
    records = []

    for url, event_name in SOURCES:
        html = fetch_html(session, url)
        lines = [clean_text(line) for line in soup_from_html(html).get_text("\n", strip=True).splitlines()]
        lines = [line for line in lines if line]

        index = 0
        while index < len(lines):
            event_date = parse_jp_date(lines[index], reference)
            if not event_date:
                index += 1
                continue

            if index + 2 >= len(lines):
                break

            prefecture = lines[index + 1]
            store = lines[index + 2]
            if prefecture != OSAKA_TEXT:
                index += 1
                continue

            record = build_record(
                event_date=event_date,
                store=store,
                event=event_name,
                area=OSAKA_TEXT,
                source_url=url,
                updated_at=updated_at,
            )
            if record:
                records.append(record)

            index += 3

    LOGGER.info("aims: collected %s events", len(records))
    return records
