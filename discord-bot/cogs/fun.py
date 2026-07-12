"""
Fun & Games cog.
Commands: 8ball, coinflip, roll, rps, trivia, meme, joke
Pulls from free public APIs for trivia/memes/jokes — no API keys required.
"""
import asyncio
import html
import random

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

EIGHT_BALL_RESPONSES = [
    "Yes.", "No.", "Absolutely.", "Ask again later.", "Definitely not.",
    "It is certain.", "Very doubtful.", "Signs point to yes.", "Cannot predict now.",
    "Without a doubt.", "My sources say no.", "Outlook good.",
]


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    @commands.hybrid_command(name="8ball", description="Ask the magic 8-ball a yes/no question.")
    @app_commands.describe(question="Your question")
    async def eight_ball(self, ctx: commands.Context, *, question: str):
        await ctx.reply(f"🎱 **{question}**\n{random.choice(EIGHT_BALL_RESPONSES)}")

    @commands.hybrid_command(description="Flip a coin.")
    async def coinflip(self, ctx: commands.Context):
        await ctx.reply(f"🪙 {random.choice(['Heads', 'Tails'])}!")

    @commands.hybrid_command(description="Roll a dice.")
    @app_commands.describe(sides="Number of sides on the dice (default 6)")
    async def roll(self, ctx: commands.Context, sides: int = 6):
        sides = max(2, min(sides, 1000))
        await ctx.reply(f"🎲 You rolled a **{random.randint(1, sides)}** (d{sides}).")

    @commands.hybrid_command(description="Play rock-paper-scissors against the bot.")
    @app_commands.describe(choice="rock, paper, or scissors")
    @app_commands.choices(choice=[
        app_commands.Choice(name="rock", value="rock"),
        app_commands.Choice(name="paper", value="paper"),
        app_commands.Choice(name="scissors", value="scissors"),
    ])
    async def rps(self, ctx: commands.Context, choice: str):
        bot_choice = random.choice(["rock", "paper", "scissors"])
        beats = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
        if choice == bot_choice:
            result = "It's a tie!"
        elif beats[choice] == bot_choice:
            result = "You win! 🎉"
        else:
            result = "I win! 🤖"
        await ctx.reply(f"You chose **{choice}**, I chose **{bot_choice}**. {result}")

    @commands.hybrid_command(description="Get a random trivia question.")
    async def trivia(self, ctx: commands.Context):
        try:
            async with self.session.get("https://opentdb.com/api.php?amount=1&type=multiple") as resp:
                data = await resp.json()
        except Exception:
            await ctx.reply("Trivia service is unavailable right now, try again later.")
            return
        if not data.get("results"):
            await ctx.reply("Couldn't fetch a trivia question, try again.")
            return
        q = data["results"][0]
        question = html.unescape(q["question"])
        correct = html.unescape(q["correct_answer"])
        answers = [html.unescape(a) for a in q["incorrect_answers"]] + [correct]
        random.shuffle(answers)
        lettered = "\n".join(f"{chr(65 + i)}. {a}" for i, a in enumerate(answers))
        correct_letter = chr(65 + answers.index(correct))

        embed = discord.Embed(title="🧠 Trivia", description=f"{question}\n\n{lettered}",
                               color=discord.Color.teal())
        embed.set_footer(text=f"Category: {q['category']} | Difficulty: {q['difficulty']} | "
                               f"Answer reveals in 15s")
        await ctx.reply(embed=embed)
        await asyncio.sleep(15)
        await ctx.channel.send(f"⏰ The correct answer was **{correct_letter}. {correct}**")

    @commands.hybrid_command(description="Get a random meme.")
    async def meme(self, ctx: commands.Context):
        try:
            async with self.session.get("https://meme-api.com/gimme") as resp:
                data = await resp.json()
        except Exception:
            await ctx.reply("Meme service is unavailable right now, try again later.")
            return
        embed = discord.Embed(title=data.get("title", "Meme"), color=discord.Color.random())
        embed.set_image(url=data.get("url"))
        embed.set_footer(text=f"👍 {data.get('ups', 0)} | r/{data.get('subreddit', 'memes')}")
        await ctx.reply(embed=embed)

    @commands.hybrid_command(description="Get a random joke.")
    async def joke(self, ctx: commands.Context):
        try:
            async with self.session.get("https://official-joke-api.appspot.com/random_joke") as resp:
                data = await resp.json()
        except Exception:
            await ctx.reply("Joke service is unavailable right now, try again later.")
            return
        await ctx.reply(f"{data['setup']}\n||{data['punchline']}||")


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
