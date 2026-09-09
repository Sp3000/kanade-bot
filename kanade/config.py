import logging
import os

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SCRAPER_WEBHOOK_URL = os.getenv("SCRAPER_WEBHOOK_URL")

IS_STAGING = os.getenv("DISCORD_BOT_ENVIRONMENT") == "staging"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG if IS_STAGING else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
