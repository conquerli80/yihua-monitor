"""解析 Codex CLI（电脑命令行版）本地会话日志：~/.codex/sessions/*.jsonl。

无需手动导出——直接读本地日志。每个 .jsonl 是一个会话，逐行 JSON 事件。
不同 Codex 版本字段略有差异，这里做容错式提取：找出带 role/content 的消息项。
"""
from __future__ import annotations

import json
from pathlib import Path

from common import Conversation, Message, stable_id, iso


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for blk in content:
            if isinstance(blk, dict):
                parts.append(blk.get("text") or blk.get("content") or f"[{blk.get('type', 'block')}]")
            else:
                parts.append(str(blk))
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        return content.get("text", "") or json.dumps(content, ensure_ascii=False)
    return ""


def _extract_message(obj: dict) -> tuple[str, str, str | None] | None:
    """从一行事件里尽量提取 (role, text, ts)。"""
    # 常见包裹：{"type": "...", "payload": {...}} 或直接是消息
    payload = obj.get("payload", obj)
    if not isinstance(payload, dict):
        return None
    role = payload.get("role") or obj.get("role")
    content = payload.get("content", payload.get("text"))
    if role and content is not None:
        text = _content_to_text(content)
        if text.strip():
            ts = iso(obj.get("timestamp") or payload.get("timestamp"))
            return role, text, ts
    return None


def parse_file(path: Path) -> list[Conversation]:
    msgs: list[Message] = []
    title = None
    first_ts = last_ts = None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            # 抓会话元信息（首行常含 cwd/instructions/timestamp）
            if title is None:
                title = obj.get("instructions") or obj.get("cwd") or obj.get("id")
            got = _extract_message(obj)
            if got:
                role, text, ts = got
                role = {"human": "user"}.get(role, role)
                msgs.append(Message(role=role, content=text, timestamp=ts))
                first_ts = first_ts or ts
                last_ts = ts or last_ts

    if not msgs:
        return []

    title = (title or path.stem)
    title = str(title)[:80]
    return [
        Conversation(
            id=stable_id("codex_cli", path.name),
            source="codex_cli",
            title=title,
            created_at=first_ts,
            updated_at=last_ts,
            messages=msgs,
            source_ref=str(path),
        )
    ]
