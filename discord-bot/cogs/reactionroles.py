"""
Reaction roles cog.
Bind an emoji on a specific message to a role; reacting grants it,
removing the reaction takes it away.
"""
import discord
from discord import app_commands
from discord.ext import commands


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @commands.hybrid_command(description="Bind an emoji on a message to a role.")
    @app_commands.describe(message_id="ID of the message to watch (right-click -> Copy Message ID)",
                            emoji="Emoji members will react with", role="Role to grant on reaction")
    @commands.has_permissions(manage_roles=True)
    async def reactionrole(self, ctx: commands.Context, message_id: str, emoji: str, role: discord.Role):
        try:
            message = await ctx.channel.fetch_message(int(message_id))
        except (discord.NotFound, discord.HTTPException, ValueError):
            await ctx.reply("Couldn't find that message in this channel. Make sure the ID is correct "
                             "and the message is in the channel you're running this command in.")
            return
        if role >= ctx.guild.me.top_role:
            await ctx.reply("I can't assign that role — it's higher than or equal to my own top role.")
            return
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await ctx.reply("I couldn't react with that emoji — make sure it's a valid unicode or server emoji.")
            return
        await self.db.add_reaction_role(ctx.guild.id, message.id, str(emoji), role.id)
        await ctx.reply(f"✅ Reacting with {emoji} on that message now grants {role.mention}.")

    @commands.hybrid_command(description="Remove a reaction role binding.")
    @app_commands.describe(message_id="ID of the message", emoji="The emoji binding to remove")
    @commands.has_permissions(manage_roles=True)
    async def removereactionrole(self, ctx: commands.Context, message_id: str, emoji: str):
        try:
            mid = int(message_id)
        except ValueError:
            await ctx.reply("That doesn't look like a valid message ID.")
            return
        await self.db.remove_reaction_role(ctx.guild.id, mid, emoji)
        await ctx.reply("✅ Removed that reaction role binding.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.member is None or payload.member.bot:
            return
        role_id = await self.db.get_reaction_role(payload.guild_id, payload.message_id, str(payload.emoji))
        if not role_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(role_id)
        if role:
            try:
                await payload.member.add_roles(role, reason="Reaction role")
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return
        role_id = await self.db.get_reaction_role(payload.guild_id, payload.message_id, str(payload.emoji))
        if not role_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        role = guild.get_role(role_id)
        if member and role and not member.bot:
            try:
                await member.remove_roles(role, reason="Reaction role removed")
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))
