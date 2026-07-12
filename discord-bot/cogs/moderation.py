"""
Moderation cog.
Commands: kick, ban, unban, timeout, warn, warnings, clearwarnings,
          purge, slowmode, lock, unlock, setmodlog
Passive: auto-mod filter for bad words, invite links, and mass mentions.
"""
import re
import time
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import Database

INVITE_RE = re.compile(r"(discord\.gg|discordapp\.com/invite|discord\.com/invite)/\S+", re.IGNORECASE)


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self) -> Database:
        return self.bot.db

    async def _log(self, guild: discord.Guild, embed: discord.Embed):
        channel_id = await self.db.get_mod_log_channel(guild.id)
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)

    # ---------- auto-mod ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.author.guild_permissions.manage_messages:
            return  # don't auto-mod moderators

        content_lower = message.content.lower()
        violation = None

        if any(word in content_lower for word in config.BAD_WORDS):
            violation = "prohibited language"
        elif INVITE_RE.search(message.content):
            violation = "posting an unauthorized invite link"
        elif len(message.mentions) > config.MAX_MENTIONS_PER_MESSAGE:
            violation = "mass mentioning"

        if violation:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            await self.db.add_warning(message.guild.id, message.author.id, self.bot.user.id,
                                       f"Auto-mod: {violation}")
            try:
                await message.channel.send(
                    f"{message.author.mention}, your message was removed for {violation}.",
                    delete_after=8,
                )
            except discord.HTTPException:
                pass
            embed = discord.Embed(
                title="Auto-mod Action",
                description=f"Deleted a message from {message.author.mention} for **{violation}**.",
                color=discord.Color.red(),
            )
            await self._log(message.guild, embed)

    # ---------- commands ----------
    @commands.hybrid_command(description="Kick a member from the server.")
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        await member.kick(reason=reason)
        await ctx.reply(f"👢 Kicked {member.mention}. Reason: {reason}")
        embed = discord.Embed(title="Member Kicked",
                               description=f"{member.mention} kicked by {ctx.author.mention}\nReason: {reason}",
                               color=discord.Color.orange())
        await self._log(ctx.guild, embed)

    @commands.hybrid_command(description="Ban a member from the server.")
    @app_commands.describe(member="Member to ban", reason="Reason for the ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        await member.ban(reason=reason)
        await ctx.reply(f"🔨 Banned {member.mention}. Reason: {reason}")
        embed = discord.Embed(title="Member Banned",
                               description=f"{member.mention} banned by {ctx.author.mention}\nReason: {reason}",
                               color=discord.Color.dark_red())
        await self._log(ctx.guild, embed)

    @commands.hybrid_command(description="Unban a user by ID.")
    @app_commands.describe(user_id="The user ID to unban")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await ctx.guild.unban(user)
            await ctx.reply(f"✅ Unbanned {user.mention}.")
        except (discord.NotFound, ValueError):
            await ctx.reply("Couldn't find a banned user with that ID.")

    @commands.hybrid_command(description="Timeout a member for a number of minutes.")
    @app_commands.describe(member="Member to time out", minutes="Duration in minutes", reason="Reason")
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx: commands.Context, member: discord.Member, minutes: int,
                       *, reason: str = "No reason provided"):
        duration = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await ctx.reply(f"🔇 Timed out {member.mention} for {minutes} minute(s). Reason: {reason}")
        embed = discord.Embed(
            title="Member Timed Out",
            description=f"{member.mention} timed out by {ctx.author.mention} for {minutes}m\nReason: {reason}",
            color=discord.Color.yellow(),
        )
        await self._log(ctx.guild, embed)

    @commands.hybrid_command(description="Warn a member.")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        await self.db.add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        await ctx.reply(f"⚠️ Warned {member.mention}. Reason: {reason}")
        embed = discord.Embed(
            title="Member Warned",
            description=f"{member.mention} warned by {ctx.author.mention}\nReason: {reason}",
            color=discord.Color.yellow(),
        )
        await self._log(ctx.guild, embed)

    @commands.hybrid_command(description="View a member's warnings.")
    @app_commands.describe(member="Member to check")
    async def warnings(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        rows = await self.db.get_warnings(ctx.guild.id, member.id)
        if not rows:
            await ctx.reply(f"{member.display_name} has no warnings.")
            return
        lines = []
        for warn_id, mod_id, reason, ts in rows:
            mod = ctx.guild.get_member(mod_id)
            mod_name = mod.display_name if mod else "Auto-mod"
            lines.append(f"**#{warn_id}** by {mod_name} — {reason} (<t:{ts}:R>)")
        embed = discord.Embed(title=f"{member.display_name}'s Warnings",
                               description="\n".join(lines), color=discord.Color.red())
        await ctx.reply(embed=embed)

    @commands.hybrid_command(description="Clear all warnings for a member.")
    @app_commands.describe(member="Member whose warnings to clear")
    @commands.has_permissions(moderate_members=True)
    async def clearwarnings(self, ctx: commands.Context, member: discord.Member):
        await self.db.clear_warnings(ctx.guild.id, member.id)
        await ctx.reply(f"🧹 Cleared all warnings for {member.mention}.")

    @commands.hybrid_command(description="Bulk delete messages in this channel.")
    @app_commands.describe(amount="Number of messages to delete (max 100)")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int):
        amount = max(1, min(amount, 100))
        deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command invocation
        msg = await ctx.send(f"🧹 Deleted {len(deleted) - 1} message(s).")
        await msg.delete(delay=4)

    @commands.hybrid_command(description="Set slowmode for this channel.")
    @app_commands.describe(seconds="Seconds between messages (0 to disable)")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int):
        await ctx.channel.edit(slowmode_delay=max(0, min(seconds, 21600)))
        await ctx.reply(f"🐌 Slowmode set to {seconds} second(s).")

    @commands.hybrid_command(description="Lock this channel (prevent @everyone from sending messages).")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.reply("🔒 Channel locked.")

    @commands.hybrid_command(description="Unlock this channel.")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        await ctx.reply("🔓 Channel unlocked.")

    @commands.hybrid_command(description="Set the channel used for moderation logs.")
    @app_commands.describe(channel="Channel to send mod logs to")
    @commands.has_permissions(manage_guild=True)
    async def setmodlog(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.db.set_mod_log_channel(ctx.guild.id, channel.id)
        await ctx.reply(f"📋 Mod log channel set to {channel.mention}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
