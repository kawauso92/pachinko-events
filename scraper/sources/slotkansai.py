from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests

from ..common import build_record, clean_text, fetch_html, parse_jp_date, soup_from_html

LOGGER = logging.getLogger(__name__)

CATEGORY_URL = "https://slotkansai.com/?cat=2"
OSAKA_TEXT = "\u5927\u962a"
KEYWORDS = [
    "\u3058\u3083\u3093\u3058\u3083\u3093",
    "\u308c\u3093\u3058\u308d\u3046",
    "\u30a8\u30a4\u30e0\u30b9\u30bf\u30fc\u7389",
    "\u30a8\u30a4\u30e0\u30b9\u30bf\u30fc\u8d85\u7389",
    "\u3058\u3083\u3093\u3070\u308a",
    "\u8d85\u7389\u306e\u30ea\u30a2\u30eb",
    "\u3059\u308d\u3071\u3061",
]
TITLE_DATE_PATTERN = re.compile(r"(\d{1,2})\u6708(\d{1,2})\u65e5")


def _is_article_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != "slotkansai.com":
        return False
    if not parsed.path:
        return False
    if parsed.path == "/" and not parsed.query.startswith("p="):
        return False
    if parsed.query and "cat=2" in parsed.query:
        return False
    if parsed.path.startswith(("/category/", "/tag/", "/author/", "/wp-", "/page/")):
        return False
    return True


def _collect_article_urls(soup) -> list[str]:
    urls = []
    seen = set()

    for selector in ("ul.article-list p.title a[href]", "ul.article-list a.link[href]"):
        for anchor in soup.select(selector):
            href = anchor.get("href")
            if not href:
                continue

            absolute = urljoin(CATEGORY_URL, href)
            if not _is_article_url(absolute) or absolute in seen:
                continue

            seen.add(absolute)
            urls.append(absolute)
            if len(urls) == 10:
                return urls

    return urls


def _extract_event_text(value: str) -> str | None:
    text = clean_text(value)
    for keyword in KEYWORDS:
        if keyword in text:
            return text
    return None


def _extract_date_from_title(article_soup, reference: datetime) -> str | None:
    title = ""
    for selector in ("h1.entry-title", "h1", "title"):
        tag = article_soup.select_one(selector)
        if tag:
            title = clean_text(tag.get_text(" ", strip=True))
            if title:
                break

    match = TITLE_DATE_PATTERN.search(title)
    if not match:
        return None

    return parse_jp_date(f"{match.group(1)}\u6708{match.group(2)}\u65e5", reference)


def _header_indexes(table) -> tuple[int | None, int | None]:
    header_row = table.select_one("tr")
    if not header_row:
        return None, None

    header_cells = header_row.find_all(["th", "td"])
    headers = [clean_text(cell.get_text(" ", strip=True)) for cell in header_cells]

    store_index = None
    event_index = None
    for index, header in enumerate(headers):
        if header == "\u30db\u30fc\u30eb\u540d":
            store_index = index
        if header == "\u7279\u5b9a\u65e5/\u53d6\u6750/\u6765\u5e97":
            event_index = index

    return store_index, event_index


def scrape(session: requests.Session, reference: datetime, updated_at: str) -> list:
    html = fetch_html(session, CATEGORY_URL)
    soup = soup_from_html(html)

    records = []
    for article_url in _collect_article_urls(soup):
        try:
            article_html = fetch_html(session, article_url)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("slotkansai article skipped: %s (%s)", article_url, exc)
            continue

        article_soup = soup_from_html(article_html)
        event_date = _extract_date_from_title(article_soup, reference)
        if not event_date:
            continue

        for table in article_soup.select("table"):
            store_index, event_index = _header_indexes(table)
            if store_index is None or event_index is None:
                continue

            for row in table.select("tr")[1:]:
                cells = row.find_all(["td", "th"])
                values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
                if len(values) <= max(store_index, event_index):
                    continue

                store = values[store_index]
                event_text = _extract_event_text(values[event_index])
                if not store or not event_text:
                    continue

                record = build_record(
                    event_date=event_date,
                    store=store,
                    event=event_text,
                    area=OSAKA_TEXT,
                    source_url=article_url,
                    updated_at=updated_at,
                )
                if record:
                    records.append(record)

    LOGGER.info("slotkansai: collected %s events", len(records))
    return records
