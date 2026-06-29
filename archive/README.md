# yihua-archive · 个人对话归档与"数字分身"

把你在 **ChatGPT / Codex（网页+手机+命令行）** 和 **Claude** 里产生的对话，备份到 Mac 本地，
沉淀成可检索的知识库，并提炼出一份"人格画像"，让任意 AI 能用你的口吻和判断方式回应——
也就是逐步复刻"另一个我"。

> ⚠️ 重要前提（务必先读）：
> **没有任何程序能自动、回溯地抓取你账号里的全部历史对话。**
> 这套工具的原料来自各家**官方数据导出**和 **Codex CLI 的本地日志**。
> 工作方式是：你定期导出 → 本工具归档/解析/索引 → 生成画像 → 把画像喂回给 AI。

## 它能做什么

| 能力 | 说明 |
|------|------|
| 归档备份 | 各家不同格式 → 统一为带元数据的 markdown，存本地，可推私有 Git |
| 去重增量 | 重复导出只新增、不重复 |
| 全文+语义检索 | "我之前怎么看某件事" 一搜即得 |
| 人格画像 | 生成 `PERSONA.md`（可当系统提示）+ `profile.json` |

## 目录结构

```
archive/
├── run.py                # 统一入口
├── config.example.yaml   # 配置模板 → 复制成 config.yaml
├── requirements.txt
└── scripts/              # 解析器 / 索引 / 检索 / 画像
数据根目录（默认 ~/yihua-archive，在仓库外）：
├── inbox/    你把导出的 zip/json 丢这里
├── raw/      原始备份（不可变）
├── parsed/   每个对话一个 .md（按 来源/年/月 归档）
├── index/    master.jsonl + archive.db（FTS+向量）
└── persona/  PERSONA.md + profile.json
```

## 安装

```bash
cd archive
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml      # 按需改路径/模型
export OPENAI_API_KEY=sk-...            # 索引/画像需要
# 若 config 里 provider: anthropic，再 export ANTHROPIC_API_KEY=...
```

## 怎么拿到对话数据

1. **ChatGPT / Codex（OpenAI）**：设置 → 数据管理 → 导出数据 → 邮箱收到 zip。
   把 zip（或解压出的 `conversations.json`）丢进 `~/yihua-archive/inbox/`。
2. **Claude**：设置 → 导出数据 → 同样丢进 `inbox/`。
3. **Codex CLI（命令行版）**：无需导出，工具会自动读 `~/.codex/sessions/*.jsonl`
   （路径在 config 的 `codex_cli.sessions_dir`）。

## 使用

```bash
python run.py ingest          # 采集 + 归档
python run.py index           # 建全文 + 向量索引
python run.py persona         # 生成"另一个我"画像
python run.py search "新能源估值我怎么看的"
python run.py all             # 上面三步一条龙
python run.py status          # 统计
```

生成的 `persona/PERSONA.md` 可直接复制进任何对话的"系统提示/自定义指令"，
或配合 `search` 检索到的相关历史一起喂给模型，就能让它"像你一样"作答。

## 备份到私有 GitHub（可选）

数据默认在仓库外。若要异地备份，在数据根目录单独建一个 **private** 仓库：

```bash
cd ~/yihua-archive
git init && git add -A && git commit -m "archive snapshot"
# 在 GitHub 建一个 private 仓库后：
git remote add origin git@github.com:<你>/yihua-archive-private.git
git push -u origin main
```

> 隐私提示：里面是你的私人对话，**仓库必须 private**；敏感内容建议加密后再备份。

## 自动化（可选）

`launchd/com.yihua.archive.plist` 是一个 macOS 定时任务模板，可每天自动跑一次 `run.py all`。
按文件内注释改好路径后：

```bash
cp launchd/com.yihua.archive.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.yihua.archive.plist
```

## 隐私与边界

- 所有原始数据留在你 Mac 本地；只有**索引向量**和**画像生成**会调用云端 API。
- 想完全本地化（数据不出 Mac），把 `llm.py` 换成本地嵌入/本地 LLM 即可，接口已抽象好。
