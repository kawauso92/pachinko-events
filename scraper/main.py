from __future__ import annotations

import logging
from datetime import datetime

from .common import dedupe_records, iso_timestamp, make_session, now_jst, within_retention, write_json
from .config import OUTPUT_PATH, RETENTION_DAYS
from .sources import aims, janbari, slopachi, slotkansai

LOGGER = logging.getLogger(__name__)

SCRAPERS = [
    ("slopachi", slopachi.scrape),
    ("aims", aims.scrape),
    ("janbari", janbari.scrape),
    ("slotkansai", slotkansai.scrape),
]


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def collect_events(reference: datetime) -> list:
    updated_at = iso_timestamp(reference)
    collected = []

    with make_session() as session:
        for name, scraper in SCRAPERS:
            try:
                events = scraper(session, reference, updated_at)
                collected.extend(events)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("source failed and was skipped: %s (%s)", name, exc)

    retained = [event for event in collected if within_retention(event.date, reference, RETENTION_DAYS)]
    return dedupe_records(retained)


def main() -> None:
    configure_logging()
    reference = now_jst()
    events = collect_events(reference)
    write_json(OUTPUT_PATH, events)
    LOGGER.info("wrote %s events to %s", len(events), OUTPUT_PATH)


if __name__ == "__main__":
    main()
