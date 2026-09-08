from discord import SyncWebhook

from .. import config


def main() -> None:
    webhook = SyncWebhook.from_url(config.SCRAPER_WEBHOOK_URL)
    webhook.send("Test scraper ran.")


if __name__ == "__main__":
    main()
