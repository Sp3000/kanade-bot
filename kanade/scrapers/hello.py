"""Example scraper."""

from collections.abc import Iterator


def scrape() -> Iterator[str]:
    """Example scraper."""
    yield "Test scraper ran."
