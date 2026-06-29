"""画像生成（"另一个我"的核心）：

汇总你在所有对话里【自己说过的话】作为原料，让模型提炼出：
  - persona/PERSONA.md   ：可直接当系统提示，让任意 LLM "像你一样"说话
  - persona/profile.json ：结构化的偏好/高频话题/决策风格

用法：python scripts/build_persona.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import common
import llm

# 采样上限，避免一次喂太多 token（按需调大）
MAX_USER_CHARS = 60000


def _read_md_user_turns(md_path: str) -> str:
    p = Path(md_path)
    if not p.exists():
        return ""
    raw = p.read_text(encoding="utf-8")
    turns, capture = [], False
    for line in raw.splitlines():
        if line.startswith("## user"):
            capture = True
            continue
        if line.startswith("## "):
            capture = False
        elif capture:
            turns.append(line)
    return "\n".join(turns).strip()


def gather_user_corpus(cfg: dict) -> str:
    paths = common.data_paths(cfg)
    chunks: list[str] = []
    total = 0
    # 最新的对话更能代表当下的你 → 倒序采样
    recs = sorted(
        common.iter_conversation_records(paths["index"]),
        key=lambda r: r.get("updated_at") or r.get("created_at") or "",
        reverse=True,
    )
    for rec in recs:
        text = _read_md_user_turns(rec["md_path"])
        if not text:
            continue
        chunks.append(f"# 对话：{rec['title']}（{rec['source']}）\n{text}")
        total += len(text)
        if total >= MAX_USER_CHARS:
            break
    return "\n\n".join(chunks)


PROMPT = """你是一位人格画像分析师。下面是某个人（以下称"本人"）在与各类 AI 助手对话时\
【自己输入】的大量文字。请仔细分析，输出对其语言风格、思维方式、关注领域、价值取向、\
决策习惯的精炼刻画，目标是让另一个 AI 读完后能够"扮演本人"、用本人的口吻与判断方式回应。

要求：
1. 先输出一段 markdown 的人格画像（标题为 # 人格画像），包含：语言风格与口头禅、常用表达、\
关注的主题领域、思维与决策特点、价值观与偏好、典型禁忌（不喜欢什么）。
2. 然后输出一个用 ```json 包裹的 JSON，字段：
   tone(语气), catchphrases(口头禅数组), top_topics(高频话题数组),
   decision_style(决策风格), values(价值观数组), dislikes(数组), languages(使用的语言数组).
3. 只依据材料，不要编造；用中文输出。

=== 本人的发言材料 ===
{corpus}
=== 材料结束 ===
"""


def build(cfg: dict) -> dict:
    paths = common.data_paths(cfg)
    corpus = gather_user_corpus(cfg)
    if not corpus.strip():
        raise SystemExit("没有可分析的用户发言，请先 ingest 归档对话。")

    result = llm.chat(PROMPT.format(corpus=corpus), cfg["llm"])

    # 拆出 markdown 与 json
    persona_md = result
    profile = {}
    m = re.search(r"```json\s*(\{.*?\})\s*```", result, re.DOTALL)
    if m:
        persona_md = result[: m.start()].strip()
        try:
            profile = json.loads(m.group(1))
        except json.JSONDecodeError:
            profile = {"_raw": m.group(1)}

    (paths["persona"] / "PERSONA.md").write_text(persona_md, encoding="utf-8")
    (paths["persona"] / "profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"persona_chars": len(persona_md), "corpus_chars": len(corpus), "profile_keys": list(profile)}


if __name__ == "__main__":
    cfg = common.load_config()
    print("画像生成完成：", json.dumps(build(cfg), ensure_ascii=False))
    print(f"→ 见 {common.data_paths(cfg)['persona']}")
