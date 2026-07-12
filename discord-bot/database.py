"""
Lightweight async SQLite layer shared by every cog.
One connection is opened at startup and reused everywhere.
"""
import time
import aiosqlite
import config


class Database:
    def __init__(self, path: str = config.DB_PATH):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        await self._create_tables()
        return self

    async def _create_tables(self):
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS economy (
                guild_id INTEGER NOT NULL,
                user_id  INTEGER NOT NULL,
                balance  INTEGER NOT NULL DEFAULT 0,
                xp       INTEGER NOT NULL DEFAULT 0,
                level    INTEGER NOT NULL DEFAULT 0,
                last_daily INTEGER NOT NULL DEFAULT 0,
                last_work  INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS inventory (
                guild_id INTEGER NOT NULL,
                user_id  INTEGER NOT NULL,
                item     TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, item)
            );

            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                mod_log_channel INTEGER,
                automod_enabled INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS reaction_roles (
                guild_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                emoji TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, message_id, emoji)
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                remind_at INTEGER NOT NULL,
                message TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tickets (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                opener_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open'
            );
            """
        )
        await self.conn.commit()

    # ---------- economy / leveling ----------
    async def _ensure_user(self, guild_id: int, user_id: int):
        await self.conn.execute(
            "INSERT OR IGNORE INTO economy (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        await self.conn.commit()

    async def get_user(self, guild_id: int, user_id: int) -> dict:
        await self._ensure_user(guild_id, user_id)
        cur = await self.conn.execute(
            "SELECT balance, xp, level, last_daily, last_work FROM economy "
            "WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        )
        row = await cur.fetchone()
        return {
            "balance": row[0], "xp": row[1], "level": row[2],
            "last_daily": row[3], "last_work": row[4],
        }

    async def update_balance(self, guild_id: int, user_id: int, delta: int):
        await self._ensure_user(guild_id, user_id)
        await self.conn.execute(
            "UPDATE economy SET balance = balance + ? WHERE guild_id=? AND user_id=?",
            (delta, guild_id, user_id),
        )
        await self.conn.commit()

    async def set_last_daily(self, guild_id: int, user_id: int, ts: int):
        await self.conn.execute(
            "UPDATE economy SET last_daily=? WHERE guild_id=? AND user_id=?",
            (ts, guild_id, user_id),
        )
        await self.conn.commit()

    async def set_last_work(self, guild_id: int, user_id: int, ts: int):
        await self.conn.execute(
            "UPDATE economy SET last_work=? WHERE guild_id=? AND user_id=?",
            (ts, guild_id, user_id),
        )
        await self.conn.commit()

    async def add_xp(self, guild_id: int, user_id: int, amount: int) -> tuple[int, int, bool]:
        """Adds XP, returns (new_xp, new_level, leveled_up)."""
        await self._ensure_user(guild_id, user_id)
        user = await self.get_user(guild_id, user_id)
        new_xp = user["xp"] + amount
        old_level = user["level"]
        new_level = self._level_from_xp(new_xp)
        leveled_up = new_level > old_level
        await self.conn.execute(
            "UPDATE economy SET xp=?, level=? WHERE guild_id=? AND user_id=?",
            (new_xp, new_level, guild_id, user_id),
        )
        await self.conn.commit()
        return new_xp, new_level, leveled_up

    @staticmethod
    def _level_from_xp(xp: int) -> int:
        level = 0
        while xp >= Database.xp_for_level(level + 1):
            level += 1
        return level

    @staticmethod
    def xp_for_level(level: int) -> int:
        # Cumulative XP required to reach `level`.
        return 5 * (level ** 2) + 50 * level + 100 if level > 0 else 0

    async def leaderboard(self, guild_id: int, by: str = "balance", limit: int = 10):
        column = "balance" if by == "balance" else "xp"
        cur = await self.conn.execute(
            f"SELECT user_id, {column} FROM economy WHERE guild_id=? "
            f"ORDER BY {column} DESC LIMIT ?",
            (guild_id, limit),
        )
        return await cur.fetchall()

    # ---------- inventory / shop ----------
    async def add_item(self, guild_id: int, user_id: int, item: str, qty: int = 1):
        await self.conn.execute(
            "INSERT INTO inventory (guild_id, user_id, item, quantity) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(guild_id, user_id, item) DO UPDATE SET quantity = quantity + ?",
            (guild_id, user_id, item, qty, qty),
        )
        await self.conn.commit()

    async def get_inventory(self, guild_id: int, user_id: int):
        cur = await self.conn.execute(
            "SELECT item, quantity FROM inventory WHERE guild_id=? AND user_id=? AND quantity > 0",
            (guild_id, user_id),
        )
        return await cur.fetchall()

    # ---------- moderation ----------
    async def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str):
        await self.conn.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, moderator_id, reason, int(time.time())),
        )
        await self.conn.commit()

    async def get_warnings(self, guild_id: int, user_id: int):
        cur = await self.conn.execute(
            "SELECT id, moderator_id, reason, created_at FROM warnings "
            "WHERE guild_id=? AND user_id=? ORDER BY created_at DESC",
            (guild_id, user_id),
        )
        return await cur.fetchall()

    async def clear_warnings(self, guild_id: int, user_id: int):
        await self.conn.execute(
            "DELETE FROM warnings WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        )
        await self.conn.commit()

    async def set_mod_log_channel(self, guild_id: int, channel_id: int):
        await self.conn.execute(
            "INSERT INTO guild_config (guild_id, mod_log_channel) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET mod_log_channel=?",
            (guild_id, channel_id, channel_id),
        )
        await self.conn.commit()

    async def get_mod_log_channel(self, guild_id: int):
        cur = await self.conn.execute(
            "SELECT mod_log_channel FROM guild_config WHERE guild_id=?", (guild_id,)
        )
        row = await cur.fetchone()
        return row[0] if row and row[0] else None

    # ---------- reaction roles ----------
    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int):
        await self.conn.execute(
            "INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(guild_id, message_id, emoji) DO UPDATE SET role_id=?",
            (guild_id, message_id, emoji, role_id, role_id),
        )
        await self.conn.commit()

    async def get_reaction_role(self, guild_id: int, message_id: int, emoji: str):
        cur = await self.conn.execute(
            "SELECT role_id FROM reaction_roles WHERE guild_id=? AND message_id=? AND emoji=?",
            (guild_id, message_id, emoji),
        )
        row = await cur.fetchone()
        return row[0] if row else None

    async def remove_reaction_role(self, guild_id: int, message_id: int, emoji: str):
        await self.conn.execute(
            "DELETE FROM reaction_roles WHERE guild_id=? AND message_id=? AND emoji=?",
            (guild_id, message_id, emoji),
        )
        await self.conn.commit()

    # ---------- reminders ----------
    async def add_reminder(self, user_id: int, channel_id: int, guild_id: int, remind_at: int, message: str) -> int:
        cur = await self.conn.execute(
            "INSERT INTO reminders (user_id, channel_id, guild_id, remind_at, message) VALUES (?, ?, ?, ?, ?)",
            (user_id, channel_id, guild_id, remind_at, message),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_due_reminders(self, now_ts: int):
        cur = await self.conn.execute(
            "SELECT id, user_id, channel_id, message FROM reminders WHERE remind_at <= ?",
            (now_ts,),
        )
        return await cur.fetchall()

    async def delete_reminder(self, reminder_id: int):
        await self.conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
        await self.conn.commit()

    # ---------- tickets ----------
    async def create_ticket(self, channel_id: int, guild_id: int, opener_id: int):
        await self.conn.execute(
            "INSERT INTO tickets (channel_id, guild_id, opener_id, status) VALUES (?, ?, ?, 'open')",
            (channel_id, guild_id, opener_id),
        )
        await self.conn.commit()

    async def close_ticket(self, channel_id: int):
        await self.conn.execute(
            "UPDATE tickets SET status='closed' WHERE channel_id=?", (channel_id,)
        )
        await self.conn.commit()

    async def get_open_ticket_for_user(self, guild_id: int, opener_id: int):
        cur = await self.conn.execute(
            "SELECT channel_id FROM tickets WHERE guild_id=? AND opener_id=? AND status='open'",
            (guild_id, opener_id),
        )
        row = await cur.fetchone()
        return row[0] if row else None
