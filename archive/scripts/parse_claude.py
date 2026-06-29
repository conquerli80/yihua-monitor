"""解析 Claude 官方导出的 conversations.json。

导出方式：Claude 设置 → 导出数据 → 收到含 conversations.json 的归档。
格式：对话数组，每个对话有 chat_messages，sender 为 human/assistant。
"""
from __future__ import annotations

import json
from pathlib import Path

from common import Conversation, Message, stable_id, iso

_ROLE = {"human": "user", "assistant": "assistant"}


def _msg_text(m: dict) -> str:
    # 新版用 content 数组，旧版用 text 字段
    if m.get("content"):
        parts = []
        for blk in m["content"]:
            if isinstance(blk, dict):
                if blk.get("type") == "text":
                    parts.append(blk.get("text", ""))
                else:
                    parts.append(f"[{blk.get('type', 'block')}]")
            elif isinstance(blk, str):
                parts.append(blk)
        if any(parts):
            return "\n".join(parts)
    return m.get("text", "") or ""


def parse_file(path: Path) -> list[Conversation]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("conversations", [data])
    conversations: list[Conversation] = []

    for conv in data:
        msgs: list[Message] = []
        for m in conv.get("chat_messages", []) or []:
            role = _ROLE.get(m.get("sender", ""), m.get("sender", "unknown"))
            text = _msg_text(m)
            if not text.strip():
                continue
            msgs.append(Message(role=role, content=text, timestamp=iso(m.get("created_at"))))
        if not msgs:
            continue

        raw_id = conv.get("uuid") or conv.get("id") or conv.get("name", "")
        conversations.append(
            Conversation(
                id=stable_id("claude", str(raw_id)),
                source="claude",
                title=conv.get("name") or "(无标题)",
                created_at=iso(conv.get("created_at")),
                updated_at=iso(conv.get("updated_at")),
                messages=msgs,
                source_ref=path.name,
            )
        )
    return conversations
