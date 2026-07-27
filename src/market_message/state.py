import json
import secrets
import sqlite3
from pathlib import Path

from .models import SniperRule


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def was_message_sent(self, message_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM sent_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        return row is not None

    def mark_message_sent(self, message_id: str, chat_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sent_messages (message_id, chat_id)
                VALUES (?, ?)
                """,
                (message_id, chat_id),
            )

    def link_telegram_message(
        self,
        telegram_message_id: int,
        warframe_message_id: str,
        chat_id: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO telegram_message_links (
                    telegram_message_id,
                    warframe_message_id,
                    chat_id
                )
                VALUES (?, ?, ?)
                """,
                (telegram_message_id, warframe_message_id, chat_id),
            )

    def chat_id_for_telegram_message(self, telegram_message_id: int) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT chat_id
                FROM telegram_message_links
                WHERE telegram_message_id = ?
                """,
                (telegram_message_id,),
            ).fetchone()
        return None if row is None else str(row[0])

    def get_telegram_update_offset(self) -> int | None:
        value = self.get_metadata("telegram_update_offset")
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def set_telegram_update_offset(self, offset: int) -> None:
        self.set_metadata("telegram_update_offset", str(offset))

    def get_or_create_device_id(self) -> str:
        existing = self.get_metadata("device_id")
        if existing:
            return existing
        device_id = secrets.token_hex(12)
        self.set_metadata("device_id", device_id)
        return device_id

    def get_metadata(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = ?",
                (key,),
            ).fetchone()
        return None if row is None else str(row[0])

    def set_metadata(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO metadata (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def create_sniper_rule(self, rule: SniperRule) -> SniperRule:
        rule_dict = rule.to_dict()
        rule_data = json.dumps(rule_dict, ensure_ascii=False)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sniper_rules (name, item_type, is_active, data)
                VALUES (?, ?, ?, ?)
                """,
                (rule.name, rule.item_type, 1 if rule.is_active else 0, rule_data),
            )
            rule_id = cursor.lastrowid
            rule.id = rule_id
            rule_data_with_id = json.dumps(rule.to_dict(), ensure_ascii=False)
            conn.execute(
                "UPDATE sniper_rules SET data = ? WHERE id = ?",
                (rule_data_with_id, rule_id),
            )
        return rule

    def get_sniper_rules(self) -> list[SniperRule]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM sniper_rules ORDER BY id DESC"
            ).fetchall()
        rules = []
        for row in rows:
            try:
                data = json.loads(row[0])
                rules.append(SniperRule.from_dict(data))
            except Exception:
                continue
        return rules

    def get_sniper_rule(self, rule_id: int) -> SniperRule | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM sniper_rules WHERE id = ?",
                (rule_id,),
            ).fetchone()
        if not row:
            return None
        try:
            return SniperRule.from_dict(json.loads(row[0]))
        except Exception:
            return None

    def update_sniper_rule(self, rule: SniperRule) -> None:
        if rule.id is None:
            return
        rule_data = json.dumps(rule.to_dict(), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sniper_rules
                SET name = ?, item_type = ?, is_active = ?, data = ?
                WHERE id = ?
                """,
                (rule.name, rule.item_type, 1 if rule.is_active else 0, rule_data, rule.id),
            )

    def delete_sniper_rule(self, rule_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sniper_rules WHERE id = ?", (rule_id,))

    def get_seen_auction_price(self, auction_id: str) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_price FROM seen_auctions WHERE auction_id = ?",
                (auction_id,),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        try:
            return int(row[0])
        except (ValueError, TypeError):
            return None

    def was_auction_seen(self, auction_id: str, price: int | None = None) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_price FROM seen_auctions WHERE auction_id = ?",
                (auction_id,),
            ).fetchone()
        if row is None:
            return False
        if price is None:
            return True
        stored_price = row[0]
        if stored_price is None:
            return False
        try:
            return int(stored_price) == int(price)
        except (ValueError, TypeError):
            return False

    def mark_auction_seen(
        self,
        auction_id: str,
        rule_id: int | None = None,
        price: int | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO seen_auctions (auction_id, rule_id, last_price, seen_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(auction_id) DO UPDATE SET
                    rule_id = excluded.rule_id,
                    last_price = excluded.last_price,
                    seen_at = CURRENT_TIMESTAMP
                """,
                (auction_id, rule_id, price),
            )

    def cleanup_old_seen_auctions(self, days: int = 7) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM seen_auctions
                WHERE datetime(seen_at) < datetime('now', '-' || ? || ' days')
                """,
                (days,),
            )
            return cursor.rowcount

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sent_messages (
                    message_id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_message_links (
                    telegram_message_id INTEGER PRIMARY KEY,
                    warframe_message_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sniper_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    item_type TEXT NOT NULL DEFAULT 'riven',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_auctions (
                    auction_id TEXT PRIMARY KEY,
                    rule_id INTEGER,
                    last_price INTEGER,
                    seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Migration: Add last_price column if table exists without it
            cursor = conn.execute("PRAGMA table_info(seen_auctions)")
            cols = [row[1] for row in cursor.fetchall()]
            if "last_price" not in cols:
                conn.execute("ALTER TABLE seen_auctions ADD COLUMN last_price INTEGER")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

