"""
Central configuration for the bot.
Loads settings from a .env file (see .env.example).
"""
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX", "!")
OWNER_ID = int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID") else None

# Economy tuning
DAILY_MIN, DAILY_MAX = 200, 500
WORK_MIN, WORK_MAX = 50, 200
WORK_COOLDOWN_SECONDS = 60 * 60          # 1 hour
DAILY_COOLDOWN_SECONDS = 60 * 60 * 24    # 24 hours

# Leveling tuning
XP_MIN, XP_MAX = 15, 25
XP_MESSAGE_COOLDOWN_SECONDS = 60

# Moderation tuning
MAX_MENTIONS_PER_MESSAGE = 5
BAD_WORDS = {
    # Small example filter list — extend as needed.
    "badword1", "badword2", "badword3",
}

# Tickets
TICKET_CATEGORY_NAME = os.getenv("TICKET_CATEGORY_NAME", "Tickets")
SUPPORT_ROLE_ID = int(os.getenv("SUPPORT_ROLE_ID", "0")) if os.getenv("SUPPORT_ROLE_ID") else None

# Utility
SUGGESTIONS_CHANNEL_ID = int(os.getenv("SUGGESTIONS_CHANNEL_ID", "0")) if os.getenv("SUGGESTIONS_CHANNEL_ID") else None

# Spotify (optional — enables Spotify link support in /play).
# Create a free app at https://developer.spotify.com/dashboard to get these.
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID") or None
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET") or None

DB_PATH = os.getenv("DB_PATH", "bot.db")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is not set. Copy .env.example to .env and add your bot token."
    )
