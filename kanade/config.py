"""Config settings."""

import logging
import os


def _require_env(name: str) -> str:
    """Return the named env var, or raise if not set."""
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Environment variable {name} is not set")
    return value


DISCORD_BOT_TOKEN = _require_env("DISCORD_BOT_TOKEN")
SCRAPER_WEBHOOK_URL = _require_env("SCRAPER_WEBHOOK_URL")

KANADE_S3_BUCKET = _require_env("KANADE_S3_BUCKET")
KANADE_S3_REGION = os.getenv("KANADE_S3_REGION", "ap-southeast-2")
KANADE_S3_ACCESS_KEY_ID = _require_env("KANADE_S3_ACCESS_KEY_ID")
KANADE_S3_SECRET_ACCESS_KEY = _require_env("KANADE_S3_SECRET_ACCESS_KEY")

IS_STAGING = os.getenv("DISCORD_BOT_ENVIRONMENT") == "staging"


def setup_logging() -> None:
    """Configure the root logger's level and format."""
    logging.basicConfig(
        level=logging.DEBUG if IS_STAGING else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
