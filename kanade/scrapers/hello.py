"""Example scraper."""

from collections.abc import Iterator


def scrape() -> Iterator[str]:
    yield "Test scraper ran."
