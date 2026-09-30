"""Scraper suite: `python -m kanade.scrapers`.

To add a scraper:
- Write `<name>.py` with a `scrape()` generator that yields update strings
- Add it to SCRAPERS
"""

import argparse
import logging
from collections.abc import Callable, Iterator

from discord import SyncWebhook

from .. import config, storage
from . import sdvx_song_data

logger = logging.getLogger(__name__)

Scraper = Callable[[], Iterator[str]]

SCRAPERS: dict[str, Scraper] = {
    "SDVX Song Data": sdvx_song_data.scrape,
}

MAX_MESSAGE_LENGTH = 2000


def post(webhook: SyncWebhook, text: str) -> None:
    """Send text, splitting on newlines to stay under Discord's char limit."""
    while len(text) > MAX_MESSAGE_LENGTH:
        cut = text.rfind("\n", 0, MAX_MESSAGE_LENGTH)
        cut = cut if cut != -1 else MAX_MESSAGE_LENGTH
        webhook.send(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        webhook.send(text)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--local",
        action="store_true",
        help="Store data in the current directory instead of S3.",
    )
    parser.add_argument(
        "--only",
        choices=sorted(SCRAPERS),
        action="append",
        metavar="NAME",
        help="Only run this scraper (repeatable). Defaults to all scrapers.",
    )
    return parser.parse_args()


def main() -> None:
    """Run scrapers under the write lock and report results to the webhook."""
    config.setup_logging()
    args = _parse_args()

    report: Callable[[str], None]
    if args.local:
        storage.use_local_storage()
        report = print
    else:
        webhook = SyncWebhook.from_url(config.SCRAPER_WEBHOOK_URL)

        def report(text: str) -> None:
            post(webhook, text)

    scrapers = {name: SCRAPERS[name] for name in (args.only or SCRAPERS)}

    try:
        with storage.lock():
            sections = _run_scrapers(scrapers)
    except storage.LockHeldError as err:
        logger.error("could not acquire %s: %s", storage.LOCK_KEY, err)
        report(f"Failed to acquire lock, skipped: {err}")
        return
    except Exception as err:
        # Should not happen, but just in case it does.
        logger.exception("scraper run crashed")
        report(f"Scraper run crashed: {err!r}")
        raise

    report("\n\n".join(sections))


def _run_scrapers(scrapers: dict[str, Scraper]) -> list[str]:
    sections: list[str] = []
    for name, scrape in scrapers.items():
        updates: list[str] = []
        error: str | None
        try:
            for update in scrape():
                updates.append(update)  # noqa: PERF402
        except Exception as err:
            logger.exception("%s failed", name)
            error = repr(err)
        else:
            error = None

        logger.info("%s: %d update(s), %s", name, len(updates), error or "ok")

        body = "\n".join(f"- {u}" for u in updates)
        if error:
            body += ("\n\n" if updates else "") + error
        heading = f"{'❌' if error else '✅'} **{name}**"
        sections.append(f"{heading}\n{body}" if body else heading)
    return sections


if __name__ == "__main__":
    main()
