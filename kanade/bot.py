"""Bot entry point."""

import logging

import discord
from discord import app_commands

from . import config

logger = logging.getLogger(__name__)

client = discord.Client(intents=discord.Intents.default())
tree = app_commands.CommandTree(client)


@tree.command(description="ping")
async def ping(interaction: discord.Interaction) -> None:
    """Basic health check."""
    await interaction.response.send_message("pong")


@client.event
async def on_ready() -> None:
    """Sync slash commands and log that the bot is connected."""
    await tree.sync()
    logger.info("Logged in as %s", client.user)


def main() -> None:
    """Configure logging and run the bot."""
    config.setup_logging()
    client.run(config.DISCORD_BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
