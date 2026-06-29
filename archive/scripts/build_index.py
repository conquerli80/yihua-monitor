"""构建检索索引：SQLite 全文(FTS5) + 嵌入向量。增量处理，已索引的跳过。

用法：python scripts/build_index.py
"""
from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path

import common
import llm


def _chunks(text: str, size: int = 1500, overlap: int = 200):
    text = text.strip()
    i = 0
    while i < len(text):
        yield text[i : i + size]
        i += size - overlap


def _read_md_body(md_path: str) -> str:
    p = Path(md_path)
    if not p.exists():
        return ""
    raw = p.read_text(encoding="utf-8")
    # 去掉 YAML frontmatter
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        return parts[2] if len(parts) == 3 else raw
    return raw


def _connect(index_dir: Path) -> sqlite3.Connection:
    db = sqlite3.connect(index_dir / "archive.db")
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(conv_id, title, source, body)")
    db.execute(
        "CREATE TABLE IF NOT EXISTS vectors (conv_id TEXT, chunk_id INTEGER, dim INTEGER, vec BLOB, text TEXT)"
    )
    db.execute("CREATE TABLE IF NOT EXISTS indexed (conv_id TEXT PRIMARY KEY)")
    return db


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def build(cfg: dict, with_vectors: bool = True) -> dict:
    paths = common.data_paths(cfg)
    db = _connect(paths["index"])
    done = {r[0] for r in db.execute("SELECT conv_id FROM indexed")}
    embed_model = cfg["llm"]["embed_model"]
    stats = {"new_convs": 0, "chunks": 0}

    pending_chunks: list[tuple[str, int, str]] = []  # (conv_id, chunk_id, text)

    for rec in common.iter_conversation_records(paths["index"]):
        if rec["id"] in done:
            continue
        body = _read_md_body(rec["md_path"])
        db.execute(
            "INSERT INTO fts (conv_id, title, source, body) VALUES (?,?,?,?)",
            (rec["id"], rec["title"], rec["source"], body),
        )
        if with_vectors:
            for ci, ch in enumerate(_chunks(body)):
                pending_chunks.append((rec["id"], ci, ch))
        db.execute("INSERT OR REPLACE INTO indexed (conv_id) VALUES (?)", (rec["id"],))
        stats["new_convs"] += 1

    if with_vectors and pending_chunks:
        vecs = llm.embed([c[2] for c in pending_chunks], embed_model)
        for (cid, ci, text), v in zip(pending_chunks, vecs):
            db.execute(
                "INSERT INTO vectors (conv_id, chunk_id, dim, vec, text) VALUES (?,?,?,?,?)",
                (cid, ci, len(v), _pack(v), text),
            )
        stats["chunks"] = len(pending_chunks)

    db.commit()
    db.close()
    return stats


if __name__ == "__main__":
    cfg = common.load_config()
    print("索引完成：", json.dumps(build(cfg), ensure_ascii=False))
