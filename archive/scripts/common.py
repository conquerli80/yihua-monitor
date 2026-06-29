"""共享：配置加载、统一数据结构、路径与工具函数。"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # 友好提示
    raise SystemExit("缺少依赖：请先 pip install -r requirements.txt")

# ---------- 配置 ----------

ROOT = Path(__file__).resolve().parent.parent  # archive/


def load_config() -> dict:
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        raise SystemExit(
            "未找到 config.yaml：请先 `cp config.example.yaml config.yaml` 并按需修改。"
        )
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def data_paths(cfg: dict) -> dict[str, Path]:
    p = cfg["paths"]
    root = Path(os.path.expanduser(p["root"])).resolve()
    out = {"root": root}
    for key in ("inbox", "raw", "parsed", "index", "persona"):
        d = root / p[key]
        d.mkdir(parents=True, exist_ok=True)
        out[key] = d
    return out


# ---------- 统一数据结构 ----------

@dataclass
class Message:
    role: str          # user | assistant | system | tool
    content: str
    timestamp: str | None = None  # ISO8601

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Conversation:
    id: str            # 全局唯一（来源+原始id 的哈希）
    source: str        # openai | claude | codex_cli
    title: str
    created_at: str | None
    updated_at: str | None
    messages: list[Message] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_ref: str | None = None  # 原始文件/路径，便于回溯

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @property
    def user_text(self) -> str:
        """仅用户说的话，画像分析的核心原料。"""
        return "\n".join(m.content for m in self.messages if m.role == "user" and m.content.strip())


# ---------- 工具函数 ----------

def stable_id(source: str, raw_id: str) -> str:
    return hashlib.sha1(f"{source}:{raw_id}".encode("utf-8")).hexdigest()[:16]


def iso(ts: Any) -> str | None:
    """把各种时间戳（unix 秒/毫秒、字符串）统一成 ISO8601。"""
    if ts is None or ts == "":
        return None
    try:
        if isinstance(ts, (int, float)):
            # 毫秒级判断
            if ts > 1e12:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        s = str(ts).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(s).astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def slugify(text: str, maxlen: int = 60) -> str:
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"[^\w一-鿿\-]", "", text)
    return (text[:maxlen] or "untitled").strip("-")


def parsed_path(parsed_dir: Path, conv: Conversation) -> Path:
    """parsed/<source>/<YYYY>/<MM>/<id>-<slug>.md"""
    dt = None
    for cand in (conv.created_at, conv.updated_at):
        if cand:
            try:
                dt = datetime.fromisoformat(cand)
                break
            except Exception:
                pass
    y = dt.strftime("%Y") if dt else "unknown"
    m = dt.strftime("%m") if dt else "00"
    d = parsed_dir / conv.source / y / m
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{conv.id}-{slugify(conv.title)}.md"


def write_markdown(path: Path, conv: Conversation) -> None:
    """每个对话写成带 YAML frontmatter 的 markdown。"""
    fm = {
        "id": conv.id,
        "source": conv.source,
        "title": conv.title,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "tags": conv.tags,
        "source_ref": conv.source_ref,
    }
    lines = ["---", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip(), "---", ""]
    lines.append(f"# {conv.title}\n")
    for msg in conv.messages:
        when = f" · {msg.timestamp}" if msg.timestamp else ""
        lines.append(f"## {msg.role}{when}\n")
        lines.append(msg.content.strip() + "\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def append_index(index_dir: Path, conv: Conversation, md_path: Path) -> None:
    """master.jsonl：一行一个对话的元数据，供检索/画像快速扫描。"""
    rec = {
        "id": conv.id,
        "source": conv.source,
        "title": conv.title,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "tags": conv.tags,
        "n_messages": len(conv.messages),
        "md_path": str(md_path),
    }
    with open(index_dir / "master.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_seen_ids(index_dir: Path) -> set[str]:
    """已归档对话的 id，用于增量去重。"""
    seen: set[str] = set()
    mp = index_dir / "master.jsonl"
    if mp.exists():
        with open(mp, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    seen.add(json.loads(line)["id"])
                except Exception:
                    continue
    return seen


def iter_conversation_records(index_dir: Path) -> Iterable[dict]:
    mp = index_dir / "master.jsonl"
    if not mp.exists():
        return
    with open(mp, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)
