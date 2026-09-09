"""Scraper suite: `python -m kanade.scrapers`.

To add a scraper:
- Write `<name>.py` with a `scrape()` generator that yields update strings
- Add it to SCRAPERS
"""

import logging

from discord import SyncWebhook

from .. import config
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
    config.setup_logging()
    webhook = SyncWebhook.from_url(config.SCRAPER_WEBHOOK_URL)

    sections: list[str] = []
    for name, scrape in SCRAPERS.items():
        updates: list[str] = []
        try:
            for update in scrape():
                updates.append(update)  # noqa: PERF402
        except Exception as exc:
            logger.exception("%s failed", name)
            error = repr(exc)
        else:
            error = None

        logger.info("%s: %d update(s), %s", name, len(updates), error or "ok")

        body = "\n".join(f"- {u}" for u in updates)
        if error:
            body += ("\n\n" if updates else "") + error
        heading = f"{'❌' if error else '✅'} **{name}**"
        sections.append(f"{heading}\n{body}" if body else heading)

    post(webhook, "\n\n".join(sections))


if __name__ == "__main__":
    main()
