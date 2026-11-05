import re
import sqlite3

ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")


class Store:
    def __init__(self, path: str = "botwatch.db"):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS watches(chat_id INTEGER, address TEXT, label TEXT, UNIQUE(chat_id,address));
        CREATE TABLE IF NOT EXISTS seen(address TEXT, hash TEXT, PRIMARY KEY(address,hash));
        CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, token TEXT, symbol TEXT,
                                          direction TEXT, threshold REAL, active INTEGER DEFAULT 1);
        """)

    # watches
    def add_watch(self, chat_id: int, address: str, label: str = "") -> bool:
        cur = self.db.execute("INSERT OR IGNORE INTO watches VALUES(?,?,?)", (chat_id, address.lower(), label))
        self.db.commit()
        return cur.rowcount == 1

    def remove_watch(self, chat_id: int, address: str) -> bool:
        cur = self.db.execute("DELETE FROM watches WHERE chat_id=? AND address=?", (chat_id, address.lower()))
        self.db.commit()
        return cur.rowcount == 1

    def watches(self, chat_id: int | None = None) -> list[tuple[int, str, str]]:
        q, a = ("SELECT chat_id,address,label FROM watches", ()) if chat_id is None else \
               ("SELECT chat_id,address,label FROM watches WHERE chat_id=?", (chat_id,))
        return self.db.execute(q, a).fetchall()

    def watched_addresses(self) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT DISTINCT address FROM watches")]

    def chats_for(self, address: str) -> list[tuple[int, str]]:
        return self.db.execute("SELECT chat_id,label FROM watches WHERE address=?", (address.lower(),)).fetchall()

    # seen transactions (per address, shared by every chat watching it)
    def is_primed(self, address: str) -> bool:
        return self.db.execute("SELECT 1 FROM seen WHERE address=? LIMIT 1", (address.lower(),)).fetchone() is not None

    def mark_seen(self, address: str, hashes: list[str]):
        self.db.executemany("INSERT OR IGNORE INTO seen VALUES(?,?)", [(address.lower(), h) for h in hashes])
        self.db.commit()

    def unseen(self, address: str, hashes: list[str]) -> list[str]:
        seen = {r[0] for r in self.db.execute("SELECT hash FROM seen WHERE address=?", (address.lower(),))}
        return [h for h in hashes if h not in seen]

    # price alerts
    def add_alert(self, chat_id: int, token: str, symbol: str, direction: str, threshold: float) -> int:
        cur = self.db.execute("INSERT INTO alerts(chat_id,token,symbol,direction,threshold) VALUES(?,?,?,?,?)",
                              (chat_id, token.lower(), symbol, direction, threshold))
        self.db.commit()
        return cur.lastrowid

    def alerts(self, chat_id: int | None = None, active_only: bool = True) -> list[tuple]:
        q = "SELECT id,chat_id,token,symbol,direction,threshold FROM alerts WHERE 1=1"
        a: list = []
        if active_only:
            q += " AND active=1"
        if chat_id is not None:
            q += " AND chat_id=?"
            a.append(chat_id)
        return self.db.execute(q, a).fetchall()

    def deactivate_alert(self, alert_id: int, chat_id: int | None = None) -> bool:
        q, a = "UPDATE alerts SET active=0 WHERE id=? AND active=1", [alert_id]
        if chat_id is not None:
            q += " AND chat_id=?"
            a.append(chat_id)
        cur = self.db.execute(q, a)
        self.db.commit()
        return cur.rowcount == 1
