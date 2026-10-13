# -*- coding: utf-8 -*-
"""
Jarvis - kalici hafiza deposu (SQLite, yalnizca standart kutuphane).

Kullanicinin "hatirla: ..." dedigi bilgileri saklar ve sohbet sirasinda
ilgili olanlari sisteme enjekte eder. Internetteki gelismis Jarvis
projelerindeki uzun sureli hafizanin hafif, bagimliliksiz bir surumudur.
"""

import os
import re
import sqlite3
import threading
import time

_LOCK = threading.Lock()
_STOP = {
    "ve", "ile", "bir", "bu", "su", "o", "da", "de", "mi", "mu", "için",
    "icin", "mi", "ne", "ki", "the", "a", "an", "is", "of", "to",
}


def _tokens(text):
    text = (text or "").lower()
    words = re.findall(r"[0-9a-zçğıöşü]+", text)
    return [w for w in words if len(w) > 1 and w not in _STOP]


class MemoryStore:
    def __init__(self, path):
        self.path = path
        self._init_db()

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init_db(self):
        with _LOCK:
            c = self._conn()
            c.execute(
                "CREATE TABLE IF NOT EXISTS memories ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "content TEXT NOT NULL,"
                "tags TEXT DEFAULT '',"
                "created REAL NOT NULL)"
            )
            c.commit()
            c.close()

    def add(self, content, tags=""):
        content = (content or "").strip()
        if not content:
            return None
        with _LOCK:
            c = self._conn()
            cur = c.execute(
                "INSERT INTO memories (content, tags, created) VALUES (?, ?, ?)",
                (content, tags or "", time.time()),
            )
            c.commit()
            mid = cur.lastrowid
            c.close()
        return mid

    def all(self, limit=500):
        with _LOCK:
            c = self._conn()
            rows = c.execute(
                "SELECT id, content, tags, created FROM memories "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            c.close()
        return rows

    def count(self):
        with _LOCK:
            c = self._conn()
            n = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            c.close()
        return n

    def search(self, query, limit=8):
        q = set(_tokens(query))
        if not q:
            return []
        scored = []
        for mid, content, tags, created in self.all(1000):
            toks = set(_tokens(content)) | set(_tokens(tags))
            score = len(q & toks)
            if score:
                scored.append((score, created, (mid, content, tags, created)))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return [r for _, _, r in scored[:limit]]

    def forget(self, mid):
        with _LOCK:
            c = self._conn()
            c.execute("DELETE FROM memories WHERE id = ?", (mid,))
            c.commit()
            c.close()

    def clear(self):
        with _LOCK:
            c = self._conn()
            c.execute("DELETE FROM memories")
            c.commit()
            c.close()

    def context_for(self, query, limit=6):
        """Sohbete eklenecek 'hatirlananlar' metni."""
        hits = self.search(query, limit)
        if not hits:
            return ""
        lines = [h[1] for h in hits]
        return "Kullanici hakkinda hatirladiklarin:\n- " + "\n- ".join(lines)
