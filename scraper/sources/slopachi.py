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
    "https://777.slopachi-station.com/slopachi_girl_schedule/",
    "https://777.slopachi-station.com/keihin_nyuka_schedule/",
]
EVENT_NAME_BY_URL = {
    "https://777.slopachi-station.com/janjan_schedule/": "\u3058\u3083\u3093\u3058\u3083\u3093\u5b9f\u8df5\u6765\u5e97",
    "https://777.slopachi-station.com/renjiro_schedule/": "\u308c\u3093\u3058\u308d\u3046\u5b9f\u8df5\u6765\u5e97",
    "https://777.slopachi-station.com/raiten_syuzai002_schedule/": "\u30b9\u30ed\u30d1\u30c1\u30b9\u30c6\u30fc\u30b7\u30e7\u30f3\u6765\u5e97\u53d6\u6750(\u9ed2)",
    "https://777.slopachi-station.com/raiten_syuzai006_schedule/": "\u30b9\u30ed\u30d1\u30c1\u30b9\u30c6\u30fc\u30b7\u30e7\u30f3\u6765\u5e97\u53d6\u6750(\u30aa\u30ec\u30f3\u30b8)",
    "https://777.slopachi-station.com/keihin_nyuka_schedule/": "\u3059\u308d\u3071\u3061\u666f\u54c1\u5165\u8377",
}

DATE_PATTERN = re.compile(
    r"(?P<month>\d{1,2})/(?P<day>\d{1,2})\s*\(\s*[\u6708\u706b\u6c34\u6728\u91d1\u571f\u65e5]\s*\)"
)
AREA_PATTERN = re.compile(r"\u3010(?P<location>[^\u3011]+)\u3011")
ENTRY_SPLIT_PATTERN = re.compile(r"(?:\u00a0|\u3000|\s){2,}")
HIRAGANA_SLOPACHI = "\u3059\u308d\u3071\u3061"
SLOPACHI_GIRL_URL = "https://777.slopachi-station.com/slopachi_girl_schedule/"


def _parse_anchor_text(text: str) -> tuple[str | None, str | None]:
    normalized = text.replace("\u00a0", " ").replace("\u3000", " ")
    parts = [clean_text(part) for part in ENTRY_SPLIT_PATTERN.split(normalized) if clean_text(part)]
    if len(parts) < 2:
        return None, None
    return parts[0], parts[-1]


def scrape(session: requests.Session, reference: datetime, updated_at: str) -> list:
    records = []

    for url in SOURCES:
        html = fetch_html(session, url)
        soup = soup_from_html(html)
        for anchor in soup.select("a[href*='/shop_data/']"):
            row = anchor.find_parent("div", class_="resultRow")
            detail = row.select_one("div.resultRow-detail") if row else None
            if not detail:
                continue

            detail_text = detail.get_text(" ", strip=True)
            date_match = DATE_PATTERN.search(detail_text)
            area_match = AREA_PATTERN.search(detail_text)
            if not date_match or not area_match:
                continue

            event_date = parse_md_date(
                int(date_match.group("month")),
                int(date_match.group("day")),
                reference,
            )
            area = extract_area(area_match.group("location"))
            if not area:
                continue

            anchor_text = anchor.get_text("", strip=True)
            parsed_event_name, store = _parse_anchor_text(anchor_text)
            if not parsed_event_name or not store:
                continue

            if url.endswith("/keihin_nyuka_schedule/") and HIRAGANA_SLOPACHI not in parsed_event_name:
                continue

            if url == SLOPACHI_GIRL_URL:
                after_raiten = parsed_event_name.split("\u6765\u5e97")[-1].strip()
                if after_raiten not in {"P", "PS"}:
                    continue
                event_name = parsed_event_name
            else:
                event_name = EVENT_NAME_BY_URL.get(url, parsed_event_name)

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

    LOGGER.info("slopachi: collected %s events", len(records))
    return records
