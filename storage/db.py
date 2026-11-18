import json
import sqlite3
from pathlib import Path

import numpy as np

from core.config import ROOT
from core.types import RawDoc

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_doc (
    uid TEXT PRIMARY KEY,
    group_key TEXT NOT NULL,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    url TEXT,
    context_title TEXT,
    text TEXT NOT NULL,
    likes INTEGER DEFAULT 0,
    created_at TEXT,
    author_hash TEXT,
    parent_id TEXT,
    trainable INTEGER DEFAULT 1,
    collected_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
);
CREATE INDEX IF NOT EXISTS idx_doc_group ON raw_doc(group_key, created_at);

CREATE TABLE IF NOT EXISTS emb_cache (
    model TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    vec BLOB NOT NULL,
    PRIMARY KEY (model, text_hash)
);

CREATE TABLE IF NOT EXISTS yt_video (
    video_id TEXT PRIMARY KEY,
    group_key TEXT,
    title TEXT,
    published_at TEXT,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS yt_quota (
    day TEXT PRIMARY KEY,
    used INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS score_snapshot (
    group_key TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    days INTEGER,
    summary TEXT NOT NULL,          -- JSON
    PRIMARY KEY (group_key, computed_at)
);
"""


class DB:
    def __init__(self, path: Path | str | None = None):
        path = Path(path or ROOT / "data" / "idol.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # ---------- 원문 ----------
    def upsert_docs(self, docs: list[RawDoc]) -> int:
        rows = [(d.uid, d.group_key, d.source, d.kind, d.doc_id, d.url, d.context_title, d.text, d.likes,
                 d.created_at, d.author_hash, d.parent_id, int(d.trainable)) for d in docs]
        self.conn.executemany(
            """INSERT INTO raw_doc (uid, group_key, source, kind, doc_id, url, context_title, text, likes,
                                    created_at, author_hash, parent_id, trainable)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(uid) DO UPDATE SET likes=excluded.likes, text=excluded.text,
                    context_title=excluded.context_title,
                    collected_at=strftime('%Y-%m-%dT%H:%M:%S','now')""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def load_docs(self, group_key: str, since_iso: str = "", sources: list[str] | None = None,
                  trainable_only: bool = False) -> list[RawDoc]:
        q = "SELECT * FROM raw_doc WHERE group_key=? AND (created_at >= ? OR created_at = '' OR created_at IS NULL)"
        args: list = [group_key, since_iso]
        if sources:
            q += f" AND source IN ({','.join('?' * len(sources))})"
            args += sources
        if trainable_only:
            q += " AND trainable=1"
        q += " ORDER BY uid"
        return [
            RawDoc(source=r["source"], doc_id=r["doc_id"], kind=r["kind"], text=r["text"],
                   group_key=r["group_key"], url=r["url"] or "", context_title=r["context_title"] or "",
                   likes=r["likes"] or 0, created_at=r["created_at"] or "", author_hash=r["author_hash"] or "",
                   parent_id=r["parent_id"] or "", trainable=bool(r["trainable"]))
            for r in self.conn.execute(q, args)
        ]

    def count_docs(self, group_key: str) -> dict:
        return {r[0]: r[1] for r in self.conn.execute(
            "SELECT source, COUNT(*) FROM raw_doc WHERE group_key=? GROUP BY source", (group_key,))}

    # ---------- 임베딩 캐시 ----------
    def get_embeddings(self, model: str, hashes: list[str]) -> dict[str, np.ndarray]:
        out = {}
        for i in range(0, len(hashes), 900):
            chunk = hashes[i:i + 900]
            q = f"SELECT text_hash, vec FROM emb_cache WHERE model=? AND text_hash IN ({','.join('?' * len(chunk))})"
            for h, v in self.conn.execute(q, [model, *chunk]):
                out[h] = np.frombuffer(v, dtype=np.float32)
        return out

    def put_embeddings(self, model: str, items: dict[str, np.ndarray]) -> None:
        self.conn.executemany(
            "INSERT OR REPLACE INTO emb_cache (model, text_hash, vec) VALUES (?,?,?)",
            [(model, h, np.asarray(v, dtype=np.float32).tobytes()) for h, v in items.items()],
        )
        self.conn.commit()

    # ---------- 유튜브 ----------
    def yt_recently_fetched(self, video_id: str, after_iso: str) -> bool:
        r = self.conn.execute("SELECT fetched_at FROM yt_video WHERE video_id=?", (video_id,)).fetchone()
        return bool(r and r[0] and r[0] >= after_iso)

    def yt_mark_fetched(self, video_id: str, group_key: str, title: str, published_at: str, fetched_at: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO yt_video VALUES (?,?,?,?,?)",
            (video_id, group_key, title, published_at, fetched_at))
        self.conn.commit()

    def yt_quota_used(self, day: str) -> int:
        r = self.conn.execute("SELECT used FROM yt_quota WHERE day=?", (day,)).fetchone()
        return r[0] if r else 0

    def yt_quota_add(self, day: str, units: int) -> None:
        self.conn.execute(
            "INSERT INTO yt_quota (day, used) VALUES (?, ?) ON CONFLICT(day) DO UPDATE SET used = used + ?",
            (day, units, units))
        self.conn.commit()

    # ---------- 점수 스냅샷 ----------
    def save_snapshot(self, group_key: str, computed_at: str, days: int, summary: dict) -> None:
        self.conn.execute("INSERT OR REPLACE INTO score_snapshot VALUES (?,?,?,?)",
                          (group_key, computed_at, days, json.dumps(summary, ensure_ascii=False)))
        self.conn.commit()

    def latest_snapshots_except(self, group_key: str) -> list[dict]:
        """다른 그룹들의 최신 스냅샷 (그룹 간 관심도 비교 기준)."""
        q = """SELECT s.group_key, s.summary FROM score_snapshot s
               JOIN (SELECT group_key, MAX(computed_at) m FROM score_snapshot GROUP BY group_key) t
               ON s.group_key=t.group_key AND s.computed_at=t.m WHERE s.group_key != ?"""
        return [json.loads(r[1]) | {"group_key": r[0]} for r in self.conn.execute(q, (group_key,))]
