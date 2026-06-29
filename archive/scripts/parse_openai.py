"""解析 OpenAI（ChatGPT 网页/手机、Codex）官方导出的 conversations.json。

导出方式：ChatGPT 设置 → 数据管理 → 导出数据 → 邮箱收到 zip → 解压得到 conversations.json
该文件是一个对话数组，每个对话用 mapping(节点树) 存消息。
"""
from __future__ import annotations

import json
from pathlib import Path

from common import Conversation, Message, stable_id, iso


def _extract_text(content: dict | None) -> str:
    if not content:
        return ""
    ctype = content.get("content_type")
    if ctype == "text":
        return "\n".join(content.get("parts", []) or [])
    if ctype in ("multimodal_text", "user_editable_context"):
        parts = []
        for p in content.get("parts", []) or []:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                parts.append(p.get("text", "") or f"[{p.get('content_type', 'asset')}]")
        return "\n".join(parts)
    if ctype == "code":
        return "```\n" + (content.get("text", "") or "") + "\n```"
    # 其它类型尽量保留可读文本
    if "parts" in content:
        return "\n".join(str(p) for p in content["parts"])
    return content.get("text", "") or ""


def parse_file(path: Path) -> list[Conversation]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):  # 某些导出包成 {"conversations": [...]}
        data = data.get("conversations", [])
    conversations: list[Conversation] = []

    for conv in data:
        mapping = conv.get("mapping", {}) or {}
        msgs: list[Message] = []
        for node in mapping.values():
            m = node.get("message")
            if not m:
                continue
            role = (m.get("author") or {}).get("role", "unknown")
            if role == "system":
                continue  # 跳过系统/隐藏节点
            text = _extract_text(m.get("content"))
            if not text.strip():
                continue
            msgs.append(Message(role=role, content=text, timestamp=iso(m.get("create_time"))))

        # 按时间排序（无时间的保持原顺序，置后）
        msgs.sort(key=lambda x: x.timestamp or "")
        if not msgs:
            continue

        raw_id = conv.get("conversation_id") or conv.get("id") or conv.get("title", "")
        conversations.append(
            Conversation(
                id=stable_id("openai", str(raw_id)),
                source="openai",
                title=conv.get("title") or "(无标题)",
                created_at=iso(conv.get("create_time")),
                updated_at=iso(conv.get("update_time")),
                messages=msgs,
                source_ref=path.name,
            )
        )
    return conversations
