"""
Entry point. Run with: python main.py
"""
import asyncio
import logging

import discord
from discord.ext import commands

import config
from database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True


class InsaneBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=config.PREFIX, intents=intents, help_command=commands.DefaultHelpCommand())
        self.db: Database | None = None

    async def setup_hook(self):
        self.db = await Database().connect()
        for ext in (
            "cogs.economy", "cogs.moderation", "cogs.music",
            "cogs.fun", "cogs.tickets", "cogs.reactionroles", "cogs.utility",
        ):
            await self.load_extension(ext)
            log.info("Loaded extension %s", ext)

        # Register persistent views so ticket buttons keep working after restarts.
        from cogs.tickets import TicketPanelView, TicketCloseView
        self.add_view(TicketPanelView())
        self.add_view(TicketCloseView())

        synced = await self.tree.sync()
        log.info("Synced %d slash command(s)", len(synced))

    async def on_ready(self):
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"{config.PREFIX}help")
        )


bot = InsaneBot()


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("You don't have permission to do that.")
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"Slow down! Try again in {error.retry_after:.1f}s.")
        return
    log.exception("Unhandled command error", exc_info=error)
    await ctx.reply(f"Something went wrong: `{error}`")


async def main():
    async with bot:
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
