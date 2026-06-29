"""检索：语义（向量）+ 关键词（FTS）混合搜索归档。

用法：python scripts/search.py "我之前怎么看新能源估值"
"""
from __future__ import annotations

import sqlite3
import struct
import sys

import numpy as np

import common
import llm


def _unpack(blob: bytes, dim: int) -> np.ndarray:
    return np.array(struct.unpack(f"{dim}f", blob), dtype=np.float32)


def semantic_search(db: sqlite3.Connection, query_vec: np.ndarray, k: int) -> list[tuple[str, float, str]]:
    rows = db.execute("SELECT conv_id, dim, vec, text FROM vectors").fetchall()
    if not rows:
        return []
    q = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    scored = []
    for conv_id, dim, blob, text in rows:
        v = _unpack(blob, dim)
        sim = float(np.dot(q, v / (np.linalg.norm(v) + 1e-9)))
        scored.append((conv_id, sim, text))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


def keyword_search(db: sqlite3.Connection, query: str, k: int) -> list[tuple[str, str]]:
    try:
        rows = db.execute(
            "SELECT conv_id, title FROM fts WHERE fts MATCH ? LIMIT ?", (query, k)
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    return rows


def search(cfg: dict, query: str, k: int = 5) -> None:
    paths = common.data_paths(cfg)
    db = sqlite3.connect(paths["index"] / "archive.db")

    titles = dict(db.execute("SELECT conv_id, title FROM fts").fetchall())

    print(f"\n🔎 语义检索：{query}\n" + "-" * 50)
    qv = np.array(llm.embed([query], cfg["llm"]["embed_model"])[0], dtype=np.float32)
    for conv_id, sim, text in semantic_search(db, qv, k):
        snippet = text.replace("\n", " ")[:120]
        print(f"[{sim:.3f}] {titles.get(conv_id, conv_id)}\n      {snippet}…\n")

    print(f"🔤 关键词检索\n" + "-" * 50)
    for conv_id, title in keyword_search(db, query, k):
        print(f"  · {title}  ({conv_id})")
    db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('用法：python scripts/search.py "你的问题"')
    search(common.load_config(), " ".join(sys.argv[1:]))
