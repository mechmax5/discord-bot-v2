"""
Music cog. Streams audio from YouTube search/URLs into a voice channel.
Also supports Spotify track/album/playlist links (resolved to YouTube
searches) when SPOTIFY_CLIENT_ID/SECRET are configured.
Requires: yt-dlp, PyNaCl, and the ffmpeg binary installed on the system.
"""
import asyncio
import collections
import re

import discord
import yt_dlp as youtube_dl
from discord import app_commands
from discord.ext import commands

import config

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except ImportError:
    spotipy = None

SPOTIFY_URL_RE = re.compile(r"open\.spotify\.com/(track|album|playlist)/([a-zA-Z0-9]+)")

YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = youtube_dl.YoutubeDL(YTDL_OPTS)


class Song:
    def __init__(self, data: dict, requester: discord.Member):
        self.title = data.get("title", "Unknown title")
        self.url = data["url"]
        self.webpage_url = data.get("webpage_url", "")
        self.duration = data.get("duration", 0)
        self.requester = requester


class GuildMusicState:
    def __init__(self):
        self.queue: collections.deque[Song] = collections.deque()
        self.voice_client: discord.VoiceClient | None = None
        self.current: Song | None = None
        self.volume: float = 0.5


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states: dict[int, GuildMusicState] = {}
        self.spotify = None
        if spotipy and config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET:
            auth = SpotifyClientCredentials(
                client_id=config.SPOTIFY_CLIENT_ID, client_secret=config.SPOTIFY_CLIENT_SECRET
            )
            self.spotify = spotipy.Spotify(auth_manager=auth)

    def _spotify_queries(self, url: str) -> list[str]:
        """Resolves a Spotify track/album/playlist URL into YouTube search strings."""
        if not self.spotify:
            return []
        match = SPOTIFY_URL_RE.search(url)
        if not match:
            return []
        kind, spotify_id = match.groups()
        queries = []
        try:
            if kind == "track":
                t = self.spotify.track(spotify_id)
                queries.append(f"{t['name']} {t['artists'][0]['name']}")
            elif kind == "album":
                for t in self.spotify.album_tracks(spotify_id)["items"]:
                    queries.append(f"{t['name']} {t['artists'][0]['name']}")
            elif kind == "playlist":
                for item in self.spotify.playlist_items(spotify_id)["items"]:
                    t = item.get("track")
                    if t:
                        queries.append(f"{t['name']} {t['artists'][0]['name']}")
        except Exception:
            return []
        return queries

    def _state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self.states:
            self.states[guild_id] = GuildMusicState()
        return self.states[guild_id]

    async def _extract(self, query: str) -> dict:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        if "entries" in data:
            data = data["entries"][0]
        return data

    def _play_next(self, guild: discord.Guild):
        state = self._state(guild.id)
        if not state.queue:
            state.current = None
            return
        song = state.queue.popleft()
        state.current = song
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(song.url, **FFMPEG_OPTS), volume=state.volume
        )

        def after_play(error):
            if error:
                print(f"Player error: {error}")
            self._play_next(guild)

        state.voice_client.play(source, after=after_play)

    @commands.hybrid_command(description="Join your current voice channel.")
    async def join(self, ctx: commands.Context):
        if not ctx.author.voice:
            await ctx.reply("You need to be in a voice channel first.")
            return
        channel = ctx.author.voice.channel
        state = self._state(ctx.guild.id)
        if state.voice_client and state.voice_client.is_connected():
            await state.voice_client.move_to(channel)
        else:
            state.voice_client = await channel.connect()
        await ctx.reply(f"🔊 Joined {channel.name}.")

    @commands.hybrid_command(description="Leave the voice channel.")
    async def leave(self, ctx: commands.Context):
        state = self._state(ctx.guild.id)
        if state.voice_client:
            await state.voice_client.disconnect()
            state.queue.clear()
            state.current = None
            state.voice_client = None
        await ctx.reply("👋 Left the voice channel.")

    @commands.hybrid_command(description="Play a song from YouTube or Spotify (search term or URL).")
    @app_commands.describe(query="Song name, YouTube URL, or Spotify track/album/playlist URL")
    async def play(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            await ctx.reply("You need to be in a voice channel first.")
            return
        state = self._state(ctx.guild.id)
        if not state.voice_client or not state.voice_client.is_connected():
            state.voice_client = await ctx.author.voice.channel.connect()

        await ctx.defer()

        if "open.spotify.com" in query:
            if not self.spotify:
                await ctx.reply(
                    "Spotify support isn't configured. Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET "
                    "to your .env, or paste a YouTube link/search term instead."
                )
                return
            loop = asyncio.get_event_loop()
            queries = await loop.run_in_executor(None, self._spotify_queries, query)
            if not queries:
                await ctx.reply("Couldn't read that Spotify link.")
                return
            added = 0
            for q in queries:
                try:
                    data = await self._extract(f"ytsearch1:{q}")
                except Exception:
                    continue
                state.queue.append(Song(data, ctx.author))
                added += 1
            if added == 0:
                await ctx.reply("Couldn't find any of those tracks on YouTube.")
                return
            if not (state.voice_client.is_playing() or state.voice_client.is_paused()):
                self._play_next(ctx.guild)
            await ctx.reply(f"➕ Queued **{added}** song(s) from Spotify.")
            return

        try:
            data = await self._extract(query)
        except Exception as e:
            await ctx.reply(f"Couldn't find that song: {e}")
            return

        song = Song(data, ctx.author)
        state.queue.append(song)

        if state.voice_client.is_playing() or state.voice_client.is_paused():
            await ctx.reply(f"➕ Queued **{song.title}**.")
        else:
            self._play_next(ctx.guild)
            await ctx.reply(f"▶️ Now playing **{song.title}**.")

    @commands.hybrid_command(description="Skip the current song.")
    async def skip(self, ctx: commands.Context):
        state = self._state(ctx.guild.id)
        if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
            state.voice_client.stop()  # triggers after_play -> next song
            await ctx.reply("⏭️ Skipped.")
        else:
            await ctx.reply("Nothing is playing.")

    @commands.hybrid_command(description="Pause playback.")
    async def pause(self, ctx: commands.Context):
        state = self._state(ctx.guild.id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            await ctx.reply("⏸️ Paused.")
        else:
            await ctx.reply("Nothing is playing.")

    @commands.hybrid_command(description="Resume playback.")
    async def resume(self, ctx: commands.Context):
        state = self._state(ctx.guild.id)
        if state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            await ctx.reply("▶️ Resumed.")
        else:
            await ctx.reply("Playback isn't paused.")

    @commands.hybrid_command(description="Stop playback and clear the queue.")
    async def stop(self, ctx: commands.Context):
        state = self._state(ctx.guild.id)
        state.queue.clear()
        if state.voice_client:
            state.voice_client.stop()
        await ctx.reply("⏹️ Stopped and cleared the queue.")

    @commands.hybrid_command(name="queue", description="Show the current song queue.")
    async def show_queue(self, ctx: commands.Context):
        state = self._state(ctx.guild.id)
        if not state.current and not state.queue:
            await ctx.reply("The queue is empty.")
            return
        lines = []
        if state.current:
            lines.append(f"**Now Playing:** {state.current.title} (requested by {state.current.requester.mention})")
        for i, song in enumerate(state.queue, start=1):
            lines.append(f"{i}. {song.title} (requested by {song.requester.mention})")
        embed = discord.Embed(title="🎵 Queue", description="\n".join(lines), color=discord.Color.blurple())
        await ctx.reply(embed=embed)

    @commands.hybrid_command(description="Set playback volume (0-100).")
    @app_commands.describe(level="Volume percentage, 0 to 100")
    async def volume(self, ctx: commands.Context, level: int):
        level = max(0, min(level, 100))
        state = self._state(ctx.guild.id)
        state.volume = level / 100
        if state.voice_client and state.voice_client.source:
            state.voice_client.source.volume = state.volume
        await ctx.reply(f"🔊 Volume set to {level}%.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
