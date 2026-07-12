"""
Utility cog.
Commands: userinfo, serverinfo, avatar, ping, poll, remind, suggest
Background task delivers due reminders.
"""
import re
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config

DURATION_RE = re.compile(r"(\d+)\s*([smhd])", re.IGNORECASE)
UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(text: str) -> int:
    """Parses strings like '10m', '2h30m', '1d' into total seconds."""
    total = 0
    for amount, unit in DURATION_RE.findall(text):
        total += int(amount) * UNIT_SECONDS[unit.lower()]
    return total


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @property
    def db(self):
        return self.bot.db

    @tasks.loop(seconds=15)
    async def reminder_loop(self):
        due = await self.db.get_due_reminders(int(time.time()))
        for reminder_id, user_id, channel_id, message in due:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(f"<@{user_id}> ⏰ Reminder: {message}")
                except discord.HTTPException:
                    pass
            await self.db.delete_reminder(reminder_id)

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(description="Get info about a user.")
    @app_commands.describe(member="Member to look up")
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=str(member), color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, "R"))
        embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, "R"))
        roles = ", ".join(r.mention for r in member.roles if r != ctx.guild.default_role) or "None"
        embed.add_field(name=f"Roles ({len(member.roles) - 1})", value=roles, inline=False)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(description="Get info about this server.")
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild
        embed = discord.Embed(title=guild.name, color=discord.Color.blurple())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "R"))
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown")
        embed.add_field(name="Roles", value=len(guild.roles))
        embed.add_field(name="Text Channels", value=len(guild.text_channels))
        embed.add_field(name="Voice Channels", value=len(guild.voice_channels))
        await ctx.reply(embed=embed)

    @commands.hybrid_command(description="Show a user's avatar.")
    @app_commands.describe(member="Member to look up")
    async def avatar(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=f"{member.display_name}'s avatar", color=discord.Color.blurple())
        embed.set_image(url=member.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(description="Check the bot's latency.")
    async def ping(self, ctx: commands.Context):
        await ctx.reply(f"🏓 Pong! {round(self.bot.latency * 1000)}ms")

    @commands.hybrid_command(description="Create a quick yes/no poll.")
    @app_commands.describe(question="The poll question")
    async def poll(self, ctx: commands.Context, *, question: str):
        embed = discord.Embed(title="📊 Poll", description=question, color=discord.Color.blurple())
        embed.set_footer(text=f"Poll by {ctx.author.display_name}")
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed)
            message = await ctx.interaction.original_response()
        else:
            message = await ctx.send(embed=embed)
        await message.add_reaction("👍")
        await message.add_reaction("👎")

    @commands.hybrid_command(description="Set a reminder (e.g. 10m, 2h, 1d).")
    @app_commands.describe(duration="e.g. 10m, 2h, 1d, 1h30m", message="What to remind you about")
    async def remind(self, ctx: commands.Context, duration: str, *, message: str):
        seconds = parse_duration(duration)
        if seconds <= 0:
            await ctx.reply("Give a valid duration like `10m`, `2h`, `1d`, or `1h30m`.")
            return
        remind_at = int(time.time()) + seconds
        await self.db.add_reminder(ctx.author.id, ctx.channel.id, ctx.guild.id if ctx.guild else 0,
                                    remind_at, message)
        await ctx.reply(f"⏰ Got it — I'll remind you in {duration}: {message}")

    @commands.hybrid_command(description="Send a suggestion for the server.")
    @app_commands.describe(suggestion="Your suggestion")
    async def suggest(self, ctx: commands.Context, *, suggestion: str):
        channel = ctx.channel
        if config.SUGGESTIONS_CHANNEL_ID:
            configured = ctx.guild.get_channel(config.SUGGESTIONS_CHANNEL_ID)
            if configured:
                channel = configured
        embed = discord.Embed(description=suggestion, color=discord.Color.green())
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        msg = await channel.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        await ctx.reply(f"✅ Suggestion submitted in {channel.mention}!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
