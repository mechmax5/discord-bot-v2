"""
Economy & Leveling cog.
Commands: balance, daily, work, give, shop, buy, inventory, leaderboard, rank
Passive: XP gain from chatting, with level-up announcements.
"""
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import Database

SHOP_ITEMS = {
    "Fishing Rod": {"price": 250, "desc": "For catching virtual fish. Purely cosmetic."},
    "VIP Badge": {"price": 1000, "desc": "Shows off in your inventory."},
    "Lucky Charm": {"price": 500, "desc": "Doesn't actually do anything. Feels lucky though."},
    "Mystery Box": {"price": 300, "desc": "Could contain anything. (It's just a box.)"},
}

# in-memory per-user XP cooldown, {(guild_id, user_id): last_ts}
_xp_cooldowns: dict[tuple[int, int], float] = {}


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self) -> Database:
        return self.bot.db

    # ---------- passive XP ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        key = (message.guild.id, message.author.id)
        now = time.time()
        last = _xp_cooldowns.get(key, 0)
        if now - last < config.XP_MESSAGE_COOLDOWN_SECONDS:
            return
        _xp_cooldowns[key] = now

        gained = random.randint(config.XP_MIN, config.XP_MAX)
        _, new_level, leveled_up = await self.db.add_xp(message.guild.id, message.author.id, gained)
        if leveled_up:
            embed = discord.Embed(
                description=f"🎉 {message.author.mention} leveled up to **level {new_level}**!",
                color=discord.Color.gold(),
            )
            await message.channel.send(embed=embed)

    # ---------- commands ----------
    @commands.hybrid_command(description="Check your (or someone else's) coin balance.")
    @app_commands.describe(member="Whose balance to check")
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        user = await self.db.get_user(ctx.guild.id, member.id)
        embed = discord.Embed(
            title=f"{member.display_name}'s Balance",
            description=f"💰 **{user['balance']}** coins",
            color=discord.Color.green(),
        )
        await ctx.reply(embed=embed)

    @commands.hybrid_command(description="Check your level and XP progress.")
    @app_commands.describe(member="Whose rank to check")
    async def rank(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        user = await self.db.get_user(ctx.guild.id, member.id)
        next_level_xp = Database.xp_for_level(user["level"] + 1)
        cur_level_xp = Database.xp_for_level(user["level"])
        progress = user["xp"] - cur_level_xp
        needed = next_level_xp - cur_level_xp
        embed = discord.Embed(
            title=f"{member.display_name}'s Rank",
            description=(
                f"📊 Level **{user['level']}**\n"
                f"XP: {progress}/{needed} toward next level\n"
                f"Total XP: {user['xp']}"
            ),
            color=discord.Color.blurple(),
        )
        await ctx.reply(embed=embed)

    @commands.hybrid_command(description="Claim your daily coin reward.")
    async def daily(self, ctx: commands.Context):
        user = await self.db.get_user(ctx.guild.id, ctx.author.id)
        now = int(time.time())
        elapsed = now - user["last_daily"]
        if elapsed < config.DAILY_COOLDOWN_SECONDS:
            remaining = config.DAILY_COOLDOWN_SECONDS - elapsed
            hours, minutes = divmod(remaining // 60, 60)
            await ctx.reply(f"You already claimed your daily reward. Try again in {hours}h {minutes}m.")
            return
        amount = random.randint(config.DAILY_MIN, config.DAILY_MAX)
        await self.db.update_balance(ctx.guild.id, ctx.author.id, amount)
        await self.db.set_last_daily(ctx.guild.id, ctx.author.id, now)
        await ctx.reply(f"💸 You claimed your daily reward of **{amount}** coins!")

    @commands.hybrid_command(description="Work a random odd job for coins.")
    async def work(self, ctx: commands.Context):
        user = await self.db.get_user(ctx.guild.id, ctx.author.id)
        now = int(time.time())
        elapsed = now - user["last_work"]
        if elapsed < config.WORK_COOLDOWN_SECONDS:
            remaining = config.WORK_COOLDOWN_SECONDS - elapsed
            minutes = remaining // 60
            await ctx.reply(f"You're tired. Rest for {minutes} more minute(s) before working again.")
            return
        jobs = [
            "delivered pizzas", "walked some dogs", "fixed a leaky faucet",
            "mowed a lawn", "coded a small script", "busked on the street corner",
        ]
        amount = random.randint(config.WORK_MIN, config.WORK_MAX)
        job = random.choice(jobs)
        await self.db.update_balance(ctx.guild.id, ctx.author.id, amount)
        await self.db.set_last_work(ctx.guild.id, ctx.author.id, now)
        await ctx.reply(f"🛠️ You {job} and earned **{amount}** coins!")

    @commands.hybrid_command(description="Give coins to another member.")
    @app_commands.describe(member="Who to give coins to", amount="How many coins")
    async def give(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0:
            await ctx.reply("Amount must be positive.")
            return
        if member.bot or member.id == ctx.author.id:
            await ctx.reply("You can't give coins to that user.")
            return
        sender = await self.db.get_user(ctx.guild.id, ctx.author.id)
        if sender["balance"] < amount:
            await ctx.reply("You don't have enough coins.")
            return
        await self.db.update_balance(ctx.guild.id, ctx.author.id, -amount)
        await self.db.update_balance(ctx.guild.id, member.id, amount)
        await ctx.reply(f"✅ Sent **{amount}** coins to {member.mention}.")

    @commands.hybrid_command(name="shop", description="View items available for purchase.")
    async def shop(self, ctx: commands.Context):
        embed = discord.Embed(title="🛒 Shop", color=discord.Color.orange())
        for name, info in SHOP_ITEMS.items():
            embed.add_field(name=f"{name} — {info['price']} coins", value=info["desc"], inline=False)
        embed.set_footer(text=f"Use {config.PREFIX}buy <item> to purchase.")
        await ctx.reply(embed=embed)

    @commands.hybrid_command(description="Buy an item from the shop.")
    @app_commands.describe(item="Exact item name from the shop")
    async def buy(self, ctx: commands.Context, *, item: str):
        match = next((name for name in SHOP_ITEMS if name.lower() == item.lower()), None)
        if not match:
            await ctx.reply("That item doesn't exist. Check `/shop` for the list.")
            return
        price = SHOP_ITEMS[match]["price"]
        user = await self.db.get_user(ctx.guild.id, ctx.author.id)
        if user["balance"] < price:
            await ctx.reply("You don't have enough coins for that.")
            return
        await self.db.update_balance(ctx.guild.id, ctx.author.id, -price)
        await self.db.add_item(ctx.guild.id, ctx.author.id, match, 1)
        await ctx.reply(f"✅ You bought **{match}**!")

    @commands.hybrid_command(description="View your inventory.")
    async def inventory(self, ctx: commands.Context):
        items = await self.db.get_inventory(ctx.guild.id, ctx.author.id)
        if not items:
            await ctx.reply("Your inventory is empty.")
            return
        desc = "\n".join(f"• {name} x{qty}" for name, qty in items)
        embed = discord.Embed(title=f"{ctx.author.display_name}'s Inventory", description=desc,
                               color=discord.Color.purple())
        await ctx.reply(embed=embed)

    @commands.hybrid_command(description="View the server leaderboard.")
    @app_commands.describe(by="Rank by balance or level")
    @app_commands.choices(by=[
        app_commands.Choice(name="balance", value="balance"),
        app_commands.Choice(name="level", value="xp"),
    ])
    async def leaderboard(self, ctx: commands.Context, by: str = "balance"):
        rows = await self.db.leaderboard(ctx.guild.id, by=by)
        if not rows:
            await ctx.reply("No data yet.")
            return
        lines = []
        for i, (user_id, value) in enumerate(rows, start=1):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            label = "coins" if by == "balance" else "XP"
            lines.append(f"**{i}.** {name} — {value} {label}")
        embed = discord.Embed(title="🏆 Leaderboard", description="\n".join(lines),
                               color=discord.Color.gold())
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
