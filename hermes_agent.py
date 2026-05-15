#!/usr/bin/env python3
"""
Hermes Agent — 湖北宜化 (000422) 智能分析助手
Uses Claude claude-opus-4-7 with adaptive thinking + EastMoney real-time data.
"""

import os
import json
import httpx
import anthropic

# ── EastMoney API ──────────────────────────────────────────────────────────────
UT = "b2884a393a59ad64002292a3e90d46a5"
SECID = "0.000422"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.eastmoney.com/"}

QUOTE_URL = (
    "https://push2.eastmoney.com/api/qt/stock/get"
    f"?fields=f43,f44,f45,f47,f48,f50,f57,f58,f169,f170"
    f"&secid={SECID}&ut={UT}"
)
FFLOW_URL = (
    "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
    f"?lmt=0&klt=1&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56"
    f"&ut={UT}&secid={SECID}"
)

# ── Fixed position context ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
你是 Hermes，湖北宜化化工股份有限公司（深交所：000422）的专属股票分析智能体。

【持仓信息】
- 成本价：¥15.32 / 股
- 持股数量：5500 股
- 止损线：¥13.00

【基本面评分（满分 100）】
综合评分：56 / 100
- 基本面：65（主营化工，近两年营收稳定但利润波动较大）
- 估值：35（PE TTM ≈ 42.7×，相对行业偏高）
- 股东结构：80（宜化集团持股稳定，无重大减持）
- 地缘政治风险：60（原材料依赖进口，汇率敏感）
- 转型前景：55（新能源材料布局尚在早期）
- 资金流向：45（近期北向资金净流出）

【分析原则】
1. 结合实时行情与资金流数据进行研判。
2. 始终以持仓成本 ¥15.32 为参照，评估盈亏比。
3. 止损线 ¥13.00 不可轻易突破，触及须立即提示。
4. 回答用中文，简洁专业，数字精确到小数点后两位。
5. 若数据不足，明确说明并给出保守建议。
"""

# ── Tool definitions ───────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_realtime_quote",
        "description": (
            "获取湖北宜化（000422）实时行情，包括最新价、涨跌幅、成交量、成交额、换手率等。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_fund_flow",
        "description": (
            "获取湖北宜化（000422）今日分钟级资金流向数据，"
            "包括主力净流入、超大单、大单、中单、小单的净额（万元）。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ── Tool implementations ───────────────────────────────────────────────────────
def get_realtime_quote() -> dict:
    with httpx.Client(timeout=10) as client:
        r = client.get(QUOTE_URL, headers=HEADERS)
        r.raise_for_status()
    data = r.json().get("data", {})
    if not data:
        return {"error": "未能获取行情数据"}

    price = data.get("f43", 0) / 100
    high = data.get("f44", 0) / 100
    low = data.get("f45", 0) / 100
    volume = data.get("f47", 0)          # 手
    amount = data.get("f48", 0) / 10000  # 万元
    turnover = data.get("f50", 0) / 100  # %
    change_pct = data.get("f170", 0) / 1000  # %

    cost = 15.32
    shares = 5500
    pnl = (price - cost) * shares
    pnl_pct = (price - cost) / cost * 100

    return {
        "最新价": f"{price:.2f}",
        "涨跌幅": f"{change_pct:.2f}%",
        "最高": f"{high:.2f}",
        "最低": f"{low:.2f}",
        "成交量(手)": volume,
        "成交额(万元)": f"{amount:.2f}",
        "换手率": f"{turnover:.2f}%",
        "持仓盈亏(元)": f"{pnl:+.2f}",
        "持仓盈亏率": f"{pnl_pct:+.2f}%",
        "止损警告": "⚠️ 当前价已低于止损线 ¥13.00！" if price < 13.0 else "正常",
    }


def get_fund_flow() -> dict:
    with httpx.Client(timeout=10) as client:
        r = client.get(FFLOW_URL, headers=HEADERS)
        r.raise_for_status()
    klines = r.json().get("data", {}).get("klines", [])
    if not klines:
        return {"error": "未能获取资金流向数据"}

    # Last bar = most recent minute
    last = klines[-1].split(",")
    # f51=time, f52=main_net, f53=ultra_large, f54=large, f55=medium, f56=small (万元)
    def wan(val):
        try:
            return f"{float(val)/10000:.2f} 万元"
        except Exception:
            return val

    return {
        "时间": last[0] if len(last) > 0 else "N/A",
        "主力净流入": wan(last[1]) if len(last) > 1 else "N/A",
        "超大单净流入": wan(last[2]) if len(last) > 2 else "N/A",
        "大单净流入": wan(last[3]) if len(last) > 3 else "N/A",
        "中单净流入": wan(last[4]) if len(last) > 4 else "N/A",
        "小单净流入": wan(last[5]) if len(last) > 5 else "N/A",
        "数据条数": len(klines),
    }


def dispatch_tool(name: str, _inputs: dict) -> str:
    if name == "get_realtime_quote":
        result = get_realtime_quote()
    elif name == "get_fund_flow":
        result = get_fund_flow()
    else:
        result = {"error": f"未知工具: {name}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── Agent loop ─────────────────────────────────────────────────────────────────
def run_agent(user_message: str) -> None:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    messages = [{"role": "user", "content": user_message}]

    print("\n🤖 Hermes 正在分析...\n")

    while True:
        with client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=TOOLS,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        # Collect assistant turn
        messages.append({"role": "assistant", "content": response.content})

        # Print text blocks
        for block in response.content:
            if block.type == "text":
                print(block.text)

        # Check stop reason
        if response.stop_reason == "end_turn":
            break

        if response.stop_reason != "tool_use":
            print(f"[停止原因: {response.stop_reason}]")
            break

        # Execute tools
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  → 调用工具: {block.name}")
                result_text = dispatch_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    }
                )

        messages.append({"role": "user", "content": tool_results})


# ── Entry point ────────────────────────────────────────────────────────────────
AUTO_PROMPTS = [
    "请获取宜化当前实时行情和资金流向，给出今日操作建议（持有 / 减仓 / 止损）。",
    "综合基本面评分和实时数据，评估当前风险等级（低 / 中 / 高），并说明理由。",
]


def main():
    print("=" * 60)
    print("  Hermes Agent — 湖北宜化 (000422) 智能分析助手")
    print("=" * 60)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n⚠️  请设置环境变量 ANTHROPIC_API_KEY 后重试。")
        return

    import sys

    if len(sys.argv) > 1:
        # Custom question from command line
        query = " ".join(sys.argv[1:])
        run_agent(query)
    else:
        # Interactive mode
        print("\n输入问题后按回车，输入 'auto' 运行自动分析，输入 'quit' 退出。\n")
        while True:
            try:
                user_input = input("你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "退出"):
                print("再见！")
                break
            if user_input.lower() == "auto":
                for prompt in AUTO_PROMPTS:
                    print(f"\n📊 自动分析: {prompt}")
                    run_agent(prompt)
                    print("-" * 60)
            else:
                run_agent(user_input)


if __name__ == "__main__":
    main()
