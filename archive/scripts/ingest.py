"""采集编排：扫描 inbox/ 与 Codex 本地日志 → 解析 → 备份原始 → 写 parsed → 更新索引。

用法（一般通过 run.py 调用）：
    python scripts/ingest.py
"""
from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import common
import parse_openai
import parse_claude
import parse_codex_cli


def _detect_export_source(path: Path) -> str | None:
    """根据 json 结构判断是 OpenAI 还是 Claude 导出。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    sample = data[0] if isinstance(data, list) and data else data
    if not isinstance(sample, dict):
        return None
    if "mapping" in sample:
        return "openai"
    if "chat_messages" in sample:
        return "claude"
    return None


def _collect_inbox_jsons(inbox: Path, raw: Path) -> list[Path]:
    """解压 inbox 里的 zip，收集所有待解析 json 到 raw/ 备份目录。"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    jsons: list[Path] = []

    for item in sorted(inbox.iterdir()):
        if item.name.startswith("."):
            continue
        dest_dir = raw / f"inbox-{stamp}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        if item.suffix == ".zip":
            with zipfile.ZipFile(item) as zf:
                zf.extractall(dest_dir)
            jsons += list(dest_dir.rglob("*.json"))
        elif item.suffix == ".json":
            target = dest_dir / item.name
            shutil.copy2(item, target)
            jsons.append(target)
        # 原始文件搬走，避免重复处理
        shutil.move(str(item), str(dest_dir / ("_original_" + item.name)))
    return jsons


def ingest(cfg: dict) -> dict:
    paths = common.data_paths(cfg)
    seen = common.load_seen_ids(paths["index"])
    stats = {"openai": 0, "claude": 0, "codex_cli": 0, "skipped_dup": 0}

    def handle(convs):
        for conv in convs:
            if conv.id in seen:
                stats["skipped_dup"] += 1
                continue
            md = common.parsed_path(paths["parsed"], conv)
            common.write_markdown(md, conv)
            common.append_index(paths["index"], conv, md)
            seen.add(conv.id)
            stats[conv.source] = stats.get(conv.source, 0) + 1

    # 1) inbox 里的 OpenAI / Claude 导出
    for jpath in _collect_inbox_jsons(paths["inbox"], paths["raw"]):
        src = _detect_export_source(jpath)
        if src == "openai":
            handle(parse_openai.parse_file(jpath))
        elif src == "claude":
            handle(parse_claude.parse_file(jpath))

    # 2) Codex CLI 本地日志（直接读，不经 inbox）
    sessions_dir = Path(cfg.get("codex_cli", {}).get("sessions_dir", "")).expanduser()
    if sessions_dir.is_dir():
        for jl in sorted(sessions_dir.rglob("*.jsonl")):
            handle(parse_codex_cli.parse_file(jl))

    return stats


if __name__ == "__main__":
    cfg = common.load_config()
    s = ingest(cfg)
    print("归档完成：")
    for k, v in s.items():
        print(f"  {k}: {v}")
