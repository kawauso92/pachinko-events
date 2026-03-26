from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin

import requests

from ..common import build_record, clean_text, fetch_html, parse_jp_date, soup_from_html

LOGGER = logging.getLogger(__name__)

CATEGORY_URL = "https://slotkansai.com/?cat=2"
TITLE_DATE_PATTERN = re.compile(r"(\d{1,2})\u6708(\d{1,2})\u65e5")
AREA_PATTERN = re.compile(
    r"\u5927\u962a(?:\u5e9c)?(?P<area>[^0-9()\uFF08\uFF09\s]+?(?:\u5e02|\u533a|\u753a|\u6751))"
)
STORE_SPLIT_PATTERN = re.compile(r"[\u2713\u2605\u2606\u30fb,\u3001/]")


def _canonical_event(text: str) -> str | None:
    normalized = clean_text(text)
    if "\u3058\u3083\u3093\u3058\u3083\u3093" in normalized:
        return "\u3058\u3083\u3093\u3058\u3083\u3093"
    if "\u308c\u3093\u3058\u308d\u3046" in normalized:
        return "\u308c\u3093\u3058\u308d\u3046"
    if (
        "\u3059\u308d\u3071\u3061\u30ac\u30fc\u30eb\u6765\u5e97PS" in normalized
        or "\u30b9\u30ed\u3071\u3061\u30ac\u30fc\u30eb\u6765\u5e97PS" in normalized
    ):
        return "\u3059\u308d\u3071\u3061\u30ac\u30fc\u30eb\u6765\u5e97PS"
    if (
        "\u3059\u308d\u3071\u3061\u30ac\u30fc\u30eb\u6765\u5e97P" in normalized
        or "\u30b9\u30ed\u3071\u3061\u30ac\u30fc\u30eb\u6765\u5e97P" in normalized
    ):
        return "\u3059\u308d\u3071\u3061\u30ac\u30fc\u30eb\u6765\u5e97P"
    if (
        "\u3059\u308d\u3071\u3061\u666f\u54c1\u5165\u8377" in normalized
        or "\u30b9\u30ed\u30d1\u30c1\u666f\u54c1\u5165\u8377" in normalized
    ):
        return "\u3059\u308d\u3071\u3061\u666f\u54c1\u5165\u8377"
    if (
        "\u6765\u5e97\u53d6\u6750(\u9ed2)" in normalized
        or "raiten-black" in normalized
        or "\u3059\u308d\u3071\u3061\u53d6\u6750" in normalized
    ):
        return "\u3059\u308d\u3071\u3061\u53d6\u6750"
    if "\u30a8\u30a4\u30e0\u30b9\u30bf\u30fc\u8d85\u7389" in normalized:
        return "\u30a8\u30a4\u30e0\u30b9\u30bf\u30fc\u8d85\u7389"
    if "\u30a8\u30a4\u30e0\u30b9\u30bf\u30fc\u7389" in normalized:
        return "\u30a8\u30a4\u30e0\u30b9\u30bf\u30fc\u7389"
    if "\u30a8\u30a4\u30e0\u30ba\u30ac\u30fc\u30eb\u7389" in normalized:
        return "\u30a8\u30a4\u30e0\u30ba\u30ac\u30fc\u30eb\u7389"

    match = re.search(
        r"\u30b8\u30e3\u30f3\u30d0\u30ea[\uff08(]((?:\u8d85)?\u7389)[)\uff09]",
        normalized,
    )
    if match:
        return f"\u30b8\u30e3\u30f3\u30d0\u30ea\uff08{match.group(1)}\uff09"
    return None


def _parse_post_date(title: str, reference: datetime) -> str | None:
    match = TITLE_DATE_PATTERN.search(title)
    if not match:
        return None
    month, day = int(match.group(1)), int(match.group(2))
    return parse_jp_date(f"{month}\u6708{day}\u65e5", reference)


def _extract_candidates(text: str) -> list[str]:
    segments = [clean_text(part) for part in STORE_SPLIT_PATTERN.split(text)]
    return [segment for segment in segments if segment]


def _extract_store(line: str, event_name: str) -> str | None:
    if event_name not in line:
        return None

    before = clean_text(line.split(event_name, 1)[0])
    candidates = _extract_candidates(before)
    if not candidates:
        return None
    return candidates[-1]


def _extract_area(post_text: str) -> str | None:
    match = AREA_PATTERN.search(post_text)
    if match:
        return clean_text(match.group("area"))
    return None


def scrape(session: requests.Session, reference: datetime, updated_at: str) -> list:
    html = fetch_html(session, CATEGORY_URL)
    soup = soup_from_html(html)
    records = []

    article_links = []
    for anchor in soup.select("a"):
        href = anchor.get("href")
        text = clean_text(anchor.get_text(" ", strip=True))
        if href and "\u8a73\u3057\u304f\u898b\u308b" in text:
            article_links.append(urljoin(CATEGORY_URL, href))

    seen_links = set()
    for article_url in article_links:
        if article_url in seen_links:
            continue
        seen_links.add(article_url)

        try:
            article_html = fetch_html(session, article_url)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("slotkansai article skipped: %s (%s)", article_url, exc)
            continue

        article_soup = soup_from_html(article_html)
        title = clean_text(article_soup.title.get_text(" ", strip=True)) if article_soup.title else ""
        event_date = _parse_post_date(title, reference)
        if not event_date:
            continue

        article_text = article_soup.get_text("\n", strip=True)
        area = _extract_area(article_text)
        if not area:
            continue

        for raw_line in article_text.splitlines():
            line = clean_text(raw_line)
            if not line:
                continue

            event_name = _canonical_event(line)
            if not event_name:
                continue

            store = _extract_store(line, event_name)
            if not store:
                continue

            record = build_record(
                event_date=event_date,
                store=store,
                event=event_name,
                area=area,
                source_url=article_url,
                updated_at=updated_at,
            )
            if record:
                records.append(record)

    LOGGER.info("slotkansai: collected %s events", len(records))
    return records
