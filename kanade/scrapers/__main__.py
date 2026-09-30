"""Scraper suite: `python -m kanade.scrapers`.

To add a scraper:
- Write `<name>.py` with a `scrape()` generator that yields update strings
- Add it to SCRAPERS
"""

import logging

from discord import SyncWebhook

from .. import config, storage
from . import hello

logger = logging.getLogger(__name__)

SCRAPERS = {
    "Hello, World!": hello.scrape,
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


def main() -> None:
    """Run scrapers under the write lock and report results to the webhook."""
    config.setup_logging()
    webhook = SyncWebhook.from_url(config.SCRAPER_WEBHOOK_URL)

    try:
        with storage.lock():
            sections = _run_scrapers()
    except storage.LockHeldError as err:
        logger.error("could not acquire %s: %s", storage.LOCK_KEY, err)
        post(webhook, f"Failed to acquire lock, skipped: {err}")
        return
    except Exception as err:
        # Should not happen, but just in case it does.
        logger.exception("scraper run crashed")
        post(webhook, f"Scraper run crashed: {err!r}")
        raise

    post(webhook, "\n\n".join(sections))


def _run_scrapers() -> list[str]:
    sections: list[str] = []
    for name, scrape in SCRAPERS.items():
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
