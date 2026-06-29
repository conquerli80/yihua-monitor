"""LLM 抽象层：嵌入向量用 OpenAI，画像对话可选 OpenAI / Anthropic。"""
from __future__ import annotations

import os


def embed(texts: list[str], model: str) -> list[list[float]]:
    """批量生成嵌入向量（仅 OpenAI 提供 embeddings）。"""
    from openai import OpenAI

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("缺少 OPENAI_API_KEY 环境变量（嵌入向量需要）。")
    client = OpenAI()
    out: list[list[float]] = []
    # 分批，避免单次请求过大
    for i in range(0, len(texts), 100):
        batch = [t[:8000] for t in texts[i : i + 100]]
        resp = client.embeddings.create(model=model, input=batch)
        out.extend(d.embedding for d in resp.data)
    return out


def chat(prompt: str, cfg_llm: dict) -> str:
    provider = cfg_llm.get("provider", "openai")
    model = cfg_llm.get("chat_model", "gpt-4o")

    if provider == "anthropic":
        from anthropic import Anthropic

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise SystemExit("缺少 ANTHROPIC_API_KEY 环境变量。")
        client = Anthropic()
        msg = client.messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    # 默认 OpenAI
    from openai import OpenAI

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("缺少 OPENAI_API_KEY 环境变量。")
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""
