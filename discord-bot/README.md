# Insane Discord Bot

A Python (`discord.py`) multipurpose bot with seven feature sets:

- 💰 **Economy & Leveling** — coins, daily/work rewards, shop, inventory, XP, levels, leaderboard
- 🛡️ **Moderation** — kick/ban/timeout/warn, auto-mod (bad words, invite links, mass mentions), purge, lock/unlock, mod-log channel
- 🎵 **Music** — play/queue/skip/pause/resume/stop, volume control, streams from YouTube **and Spotify links**
- 🎮 **Fun & Games** — 8ball, coinflip, dice, rock-paper-scissors, trivia, memes, jokes
- 🎫 **Tickets** — button-based support ticket system with private channels, persists across restarts
- 🏷️ **Reaction Roles** — react on a message to self-assign roles
- 🔧 **Utility** — userinfo, serverinfo, avatar, ping, polls, reminders, suggestions

All commands work as **both** slash commands (`/balance`) and prefix commands (`!balance`) thanks to `discord.py`'s hybrid commands.

## 1. Create the bot application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**.
2. Open the **Bot** tab → **Reset Token** → copy the token (you'll need it below).
3. Under **Privileged Gateway Intents**, enable:
   - `SERVER MEMBERS INTENT`
   - `MESSAGE CONTENT INTENT`
4. Under **OAuth2 → URL Generator**, select scopes `bot` and `applications.commands`, then permissions:
   `Kick Members, Ban Members, Moderate Members, Manage Messages, Manage Channels, Manage Guild, Manage Roles, Connect, Speak, Read Messages/View Channels, Send Messages, Add Reactions, Embed Links, Use External Emojis`.
   Use the generated URL to invite the bot to your server.
   > **Note:** for reaction roles and tickets to work, make sure the bot's role is positioned **above** any roles it needs to assign in Server Settings → Roles.

## 2. Install dependencies

You'll need **Python 3.10+** and **ffmpeg** installed on your system (required for music playback).

```bash
# ffmpeg (Debian/Ubuntu)
sudo apt install ffmpeg

# ffmpeg (macOS, via Homebrew)
brew install ffmpeg

# Python dependencies
pip install -r requirements.txt
```

## 3. Configure

```bash
cp .env.example .env
```

Edit `.env` and paste your bot token into `DISCORD_TOKEN`.

## 4. Run

```bash
python main.py
```

On first run the bot creates `bot.db` (SQLite) automatically and syncs slash commands — this can take up to an hour to appear globally, but is usually instant in the server you invited it to.

## Command Reference

### Economy & Leveling
| Command | Description |
|---|---|
| `/balance [member]` | Check coin balance |
| `/rank [member]` | Check level and XP progress |
| `/daily` | Claim daily coins (24h cooldown) |
| `/work` | Earn coins from a random job (1h cooldown) |
| `/give <member> <amount>` | Transfer coins to another member |
| `/shop` | View items for sale |
| `/buy <item>` | Purchase an item |
| `/inventory` | View your items |
| `/leaderboard [balance\|level]` | Server leaderboard |

### Moderation (most require relevant permissions)
| Command | Description |
|---|---|
| `/kick <member> [reason]` | Kick a member |
| `/ban <member> [reason]` | Ban a member |
| `/unban <user_id>` | Unban by ID |
| `/timeout <member> <minutes> [reason]` | Time out a member |
| `/warn <member> [reason]` | Warn a member |
| `/warnings [member]` | List a member's warnings |
| `/clearwarnings <member>` | Clear a member's warnings |
| `/purge <amount>` | Bulk delete messages (max 100) |
| `/slowmode <seconds>` | Set channel slowmode |
| `/lock` / `/unlock` | Lock/unlock the channel |
| `/setmodlog <channel>` | Set the mod-log channel |

Auto-mod runs passively: deletes messages containing filtered words, unauthorized invite links, or mass mentions, and logs the action.

### Music
| Command | Description |
|---|---|
| `/join` / `/leave` | Join/leave your voice channel |
| `/play <query>` | Play or queue a song (search term, YouTube URL, or Spotify track/album/playlist link) |
| `/skip` | Skip current song |
| `/pause` / `/resume` | Pause/resume playback |
| `/stop` | Stop and clear queue |
| `/queue` | Show the queue |
| `/volume <0-100>` | Set playback volume |

> Spotify links require `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET` in `.env` (see below). Without them, paste a YouTube link or just search by name instead.

### Fun & Games
| Command | Description |
|---|---|
| `/8ball <question>` | Ask the magic 8-ball |
| `/coinflip` | Flip a coin |
| `/roll [sides]` | Roll a dice (default d6) |
| `/rps <choice>` | Rock-paper-scissors vs the bot |
| `/trivia` | Random multiple-choice trivia question |
| `/meme` | Random meme |
| `/joke` | Random joke |

### Tickets
| Command | Description |
|---|---|
| `/ticketpanel` | Posts a panel with an "Open Ticket" button in the current channel (requires Manage Server) |

Clicking the button creates a private channel visible only to the member and (if configured) your support role, with a "Close Ticket" button inside. The panel and close buttons keep working even after the bot restarts.

### Reaction Roles
| Command | Description |
|---|---|
| `/reactionrole <message_id> <emoji> <role>` | React with `emoji` on the given message to grant `role` |
| `/removereactionrole <message_id> <emoji>` | Remove a binding |

Get a message ID by enabling Developer Mode (User Settings → Advanced) and right-clicking a message → Copy Message ID.

### Utility
| Command | Description |
|---|---|
| `/userinfo [member]` | Show account/join info and roles |
| `/serverinfo` | Show server stats |
| `/avatar [member]` | Show a user's avatar |
| `/ping` | Bot latency |
| `/poll <question>` | Post a 👍/👎 poll |
| `/remind <duration> <message>` | Set a reminder (e.g. `10m`, `2h`, `1d`, `1h30m`) |
| `/suggest <suggestion>` | Submit a suggestion (posts to `SUGGESTIONS_CHANNEL_ID` if set) |

## Customizing

- **Bad word filter / mention limits**: edit `BAD_WORDS` and `MAX_MENTIONS_PER_MESSAGE` in `config.py`.
- **Economy tuning** (reward ranges, cooldowns): edit the constants near the top of `config.py`.
- **Shop items**: edit `SHOP_ITEMS` in `cogs/economy.py`.
- **XP curve**: edit `Database.xp_for_level()` in `database.py`.
- **Ticket category / support role**: `TICKET_CATEGORY_NAME` and `SUPPORT_ROLE_ID` in `.env`.
- **Spotify support**: create a free app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) (no user login flow needed, just client credentials), then set `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET` in `.env`.

## Project Structure

```
discord-bot/
├── main.py               # Entry point, loads cogs, syncs slash commands, registers persistent views
├── config.py              # Environment variables + tunable constants
├── database.py             # Async SQLite layer (economy, warnings, tickets, reminders, reaction roles)
├── requirements.txt
├── .env.example
└── cogs/
    ├── economy.py          # Economy & leveling commands
    ├── moderation.py        # Moderation commands + auto-mod
    ├── music.py             # Music playback (YouTube + Spotify)
    ├── fun.py               # Fun & games commands
    ├── tickets.py            # Ticket system with persistent buttons
    ├── reactionroles.py      # Reaction role bindings
    └── utility.py            # Userinfo, polls, reminders, suggestions
```
