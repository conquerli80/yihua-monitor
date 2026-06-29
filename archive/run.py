#!/usr/bin/env python3
"""yihua-archive 统一入口。

  python run.py ingest          # 采集 inbox + Codex 日志，归档为 markdown
  python run.py index           # 构建全文 + 向量索引
  python run.py persona         # 生成"另一个我"画像
  python run.py search "问题"   # 检索归档
  python run.py all             # ingest + index + persona 一条龙
  python run.py status          # 查看已归档统计
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import common  # noqa: E402


def cmd_status(cfg):
    paths = common.data_paths(cfg)
    counts: dict[str, int] = {}
    for rec in common.iter_conversation_records(paths["index"]):
        counts[rec["source"]] = counts.get(rec["source"], 0) + 1
    total = sum(counts.values())
    print(f"已归档对话：{total}")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")
    print(f"数据根目录：{paths['root']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    cfg = common.load_config()

    if cmd == "ingest":
        import ingest
        print(ingest.ingest(cfg))
    elif cmd == "index":
        import build_index
        print(build_index.build(cfg))
    elif cmd == "persona":
        import build_persona
        print(build_persona.build(cfg))
    elif cmd == "search":
        import search
        if len(sys.argv) < 3:
            raise SystemExit('用法：python run.py search "你的问题"')
        search.search(cfg, " ".join(sys.argv[2:]))
    elif cmd == "all":
        import ingest, build_index, build_persona
        print("[1/3] 采集…", ingest.ingest(cfg))
        print("[2/3] 索引…", build_index.build(cfg))
        print("[3/3] 画像…", build_persona.build(cfg))
    elif cmd == "status":
        cmd_status(cfg)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
