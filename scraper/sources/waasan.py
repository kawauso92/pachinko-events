from __future__ import annotations

import logging
import re
from datetime import datetime

import requests

from ..common import build_record, clean_text, fetch_html, parse_jp_date, soup_from_html

LOGGER = logging.getLogger(__name__)

SOURCE_URL = "https://tama-dojo.com/"
OSAKA_TEXT = "\u5927\u962a"
EVENT_NAME_BY_TYPE = {
    "\u7389\u9053\u5834": "\u308f\u30fc\u3055\u3093\u7389\u9053\u5834",
    "\u9053\u5834\u7834\u308a": "\u308f\u30fc\u3055\u3093\u9053\u5834\u7834\u308a",
    "\u5165\u9580": "\u308f\u30fc\u3055\u3093\u5165\u9580",
}
BULLET_PREFIX_PATTERN = re.compile(r"^[\u30fb\s]+")


def _normalize_line(value: str) -> str:
    return clean_text(BULLET_PREFIX_PATTERN.sub("", value or ""))


def scrape(session: requests.Session, reference: datetime, updated_at: str) -> list:
    html = fetch_html(session, SOURCE_URL)
    lines = [_normalize_line(line) for line in soup_from_html(html).get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]

    records = []
    current_date = None

    for index, line in enumerate(lines):
        parsed_date = parse_jp_date(line, reference)
        if parsed_date:
            current_date = parsed_date
            continue

        if line != OSAKA_TEXT or not current_date:
            continue

        if index + 2 >= len(lines):
            continue

        event_type = lines[index + 1]
        store = lines[index + 2]
        event_name = EVENT_NAME_BY_TYPE.get(event_type)
        if not event_name or not store or store in EVENT_NAME_BY_TYPE:
            continue

        record = build_record(
            event_date=current_date,
            store=store,
            event=event_name,
            area=OSAKA_TEXT,
            source_url=SOURCE_URL,
            updated_at=updated_at,
        )
        if record:
            records.append(record)

    LOGGER.info("waasan: collected %s events", len(records))
    return records
