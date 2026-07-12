"""
Ticket system cog.
Post a panel with /ticketpanel; members click "Open Ticket" to get a
private channel with staff. Views are persistent so buttons keep working
across bot restarts.
"""
import asyncio

import discord
from discord.ext import commands

import config


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.green, custom_id="ticket:open", emoji="🎫")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: "Tickets" = interaction.client.get_cog("Tickets")
        if cog:
            await cog.create_ticket(interaction)


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="ticket:close", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: "Tickets" = interaction.client.get_cog("Tickets")
        if cog:
            await cog.close_ticket_channel(interaction)


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    async def create_ticket(self, interaction: discord.Interaction):
        guild = interaction.guild
        existing_id = await self.db.get_open_ticket_for_user(guild.id, interaction.user.id)
        if existing_id:
            existing_channel = guild.get_channel(existing_id)
            if existing_channel:
                await interaction.response.send_message(
                    f"You already have an open ticket: {existing_channel.mention}", ephemeral=True
                )
                return

        await interaction.response.defer(ephemeral=True)

        category = discord.utils.get(guild.categories, name=config.TICKET_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(config.TICKET_CATEGORY_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                                            read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if config.SUPPORT_ROLE_ID:
            role = guild.get_role(config.SUPPORT_ROLE_ID)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel_name = f"ticket-{interaction.user.name}".lower().replace(" ", "-")[:90]
        channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
        await self.db.create_ticket(channel.id, guild.id, interaction.user.id)

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=f"{interaction.user.mention} opened this ticket.\n"
                        f"A team member will be with you shortly. Click below to close it when resolved.",
            color=discord.Color.blue(),
        )
        await channel.send(embed=embed, view=TicketCloseView())
        await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

    async def close_ticket_channel(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔒 Closing this ticket in 5 seconds...", ephemeral=False)
        await self.db.close_ticket(interaction.channel.id)
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @commands.hybrid_command(description="Post the ticket panel in this channel.")
    @commands.has_permissions(manage_guild=True)
    async def ticketpanel(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🎫 Support",
            description="Need help? Click the button below to open a private ticket with our team.",
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed, view=TicketPanelView())
        if ctx.interaction:
            await ctx.reply("Panel posted.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
