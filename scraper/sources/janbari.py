from __future__ import annotations

import logging
from datetime import datetime

import requests

from ..common import build_record, clean_text, fetch_html, parse_jp_date, soup_from_html

LOGGER = logging.getLogger(__name__)

SCHEDULE_URL = "https://jb-portal.com/schedule/?report_id=5"
OSAKA_TEXT = "\u5927\u962a"
EVENT_NAME = "\u3058\u3083\u3093\u3070\u308a\u6f5c\u5165\u6765\u5e97\u53d6\u6750"


def scrape(session: requests.Session, reference: datetime, updated_at: str) -> list:
    html = fetch_html(session, SCHEDULE_URL)
    lines = [clean_text(line) for line in soup_from_html(html).get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]

    records = []
    index = 0
    while index < len(lines):
        event_date = parse_jp_date(lines[index], reference)
        if not event_date:
            index += 1
            continue

        if index + 3 >= len(lines):
            break

        prefecture = lines[index + 1]
        store = lines[index + 2]
        event_text = lines[index + 3]

        if prefecture == OSAKA_TEXT and event_text == EVENT_NAME:
            record = build_record(
                event_date=event_date,
                store=store,
                event=EVENT_NAME,
                area=OSAKA_TEXT,
                source_url=SCHEDULE_URL,
                updated_at=updated_at,
            )
            if record:
                records.append(record)

        index += 4

    LOGGER.info("janbari: collected %s events", len(records))
    return records
