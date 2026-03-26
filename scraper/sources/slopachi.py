from __future__ import annotations

import logging
import re
from datetime import datetime

import requests

from ..common import (
    build_record,
    extract_area,
    fetch_html,
    normalize_store_name,
    parse_entries_from_text,
    parse_md_date,
    soup_from_html,
)

LOGGER = logging.getLogger(__name__)

SOURCES = [
    {
        "url": "https://777.slopachi-station.com/janjan_schedule/",
        "event": "\u3058\u3083\u3093\u3058\u3083\u3093",
        "store_prefixes": (
            "\u3058\u3083\u3093\u3058\u3083\u3093\u5b9f\u8df5\u6765\u5e97",
            "\u3058\u3083\u3093\u3058\u3083\u3093\u5b9f\u8df5\u6765\u5e97 (\u4e88\u5b9a)",
        ),
    },
    {
        "url": "https://777.slopachi-station.com/renjiro_schedule/",
        "event": "\u308c\u3093\u3058\u308d\u3046",
        "store_prefixes": (
            "\u308c\u3093\u3058\u308d\u3046\u5b9f\u8df5\u6765\u5e97",
            "\u308c\u3093\u3058\u308d\u3046\u5b9f\u8df5\u6765\u5e97 (\u4e88\u5b9a)",
        ),
    },
    {
        "url": "https://777.slopachi-station.com/raiten_syuzai002_schedule/",
        "event": "\u6765\u5e97\u53d6\u6750(\u9ed2)",
        "store_prefixes": ("\u30b9\u30ed\u30d1\u30c1\u30b9\u30c6\u30fc\u30b7\u30e7\u30f3\u6765\u5e97\u53d6\u6750",),
    },
    {
        "url": "https://777.slopachi-station.com/slopachi_girl_schedule/",
        "event": None,
        "store_prefixes": (),
    },
    {
        "url": "https://777.slopachi-station.com/keihin_nyuka_schedule/",
        "event": "\u3059\u308d\u3071\u3061\u666f\u54c1\u5165\u8377",
        "store_prefixes": (
            "\u30b9\u30ed\u30d1\u30c1\u666f\u54c1\u5165\u8377",
            "\u666f\u54c1\u5165\u8377",
        ),
    },
]

GIRL_EVENT_PATTERN = re.compile(
    r"(?:\u30b9\u30ed|\u3059\u308d)\u3071\u3061\u30ac\u30fc\u30eb\u6765\u5e97\s*(PS|P|S)",
    re.IGNORECASE,
)


def _extract_girl_event(entry: str) -> tuple[str | None, str]:
    match = GIRL_EVENT_PATTERN.search(entry)
    if not match:
        if "icon-slopachigirl-ps" in entry.lower():
            return "\u3059\u308d\u3071\u3061\u30ac\u30fc\u30eb\u6765\u5e97PS", entry
        return None, entry

    suffix = match.group(1).upper()
    if suffix not in {"P", "PS"}:
        return None, entry

    store = entry[match.end() :].strip()
    return f"\u3059\u308d\u3071\u3061\u30ac\u30fc\u30eb\u6765\u5e97{suffix}", store


def scrape(session: requests.Session, reference: datetime, updated_at: str) -> list:
    records = []

    for source in SOURCES:
        html = fetch_html(session, source["url"])
        page_text = soup_from_html(html).get_text("\n", strip=True)
        for item in parse_entries_from_text(page_text):
            area = extract_area(item["location"])
            if not area:
                continue

            event_date = parse_md_date(int(item["month"]), int(item["day"]), reference)
            entry = item["entry"]

            if source["url"].endswith("slopachi_girl_schedule/"):
                event_name, store = _extract_girl_event(entry)
                if not event_name:
                    continue
            else:
                event_name = source["event"]
                store = normalize_store_name(entry, source["store_prefixes"])

            record = build_record(
                event_date=event_date,
                store=store,
                event=event_name,
                area=area,
                source_url=source["url"],
                updated_at=updated_at,
            )
            if record:
                records.append(record)

    LOGGER.info("slopachi: collected %s events", len(records))
    return records
