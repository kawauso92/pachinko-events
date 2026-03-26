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
        soup = soup_from_html(html)

        for item in soup.select("a.c-schedule__item"):
            date_tag = item.select_one(".c-schedule__date")
            area_tag = item.select_one(".c-schedule__area")
            store_tag = item.select_one(".c-schedule__title")
            if not date_tag or not area_tag or not store_tag:
                continue

            prefecture = clean_text(area_tag.get_text(" ", strip=True))
            if prefecture != OSAKA_TEXT:
                continue

            event_date = parse_jp_date(clean_text(date_tag.get_text("", strip=True)), reference)
            store = clean_text(store_tag.get_text(" ", strip=True))
            if not event_date or not store:
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

    LOGGER.info("aims: collected %s events", len(records))
    return records
