#!/usr/bin/env python3
"""
Longbridge Daily Brief — 全自动日报生成 & 邮件推送脚本

流程:
  1. 收集基础数据 (portfolio, watchlist, orders, market-temp, calendar)
  2. 收集持仓社区情报 (news & topics search)
  3. 扫描自选股价格异动
  4. 调用 claude CLI 生成分析报告 markdown
  5. 生成美化 HTML + PDF + 归档
  6. 邮件推送 HTML 链接（可选，通过环境变量配置收件人和 Gmail 凭据）

依赖:
  - longbridge CLI (已登录)
  - claude CLI (已登录, 用于 NLG)
  - weasyprint (用于 PDF 生成)

环境变量:
  - GMAIL_USER (可选): 发件/收件邮箱地址
  - GMAIL_APP_PASSWORD (可选): Gmail应用专用密码

用法:
  ./daily_brief_auto.py                        # 生成昨日日报
  ./daily_brief_auto.py --date 2026-05-11      # 生成指定日期
  ./daily_brief_auto.py --no-email             # 生成但不发邮件
"""

import os, sys, json, subprocess, datetime, smtplib, re, textwrap, glob
from datetime import timezone, timedelta, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# ── 常量 ──
# Auto-detect project root: script's parent directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Email config via environment variables (optional)
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
SKILL_MD = os.path.join(BASE_DIR, ".claude/skills/longbridge-daily-brief/SKILL.md")
GENERATE_PDF = os.path.join(BASE_DIR, "generate_pdf.py")
ARCHIVE_FILE = os.path.join(BASE_DIR, "longbridge_daily_brief_archive.html")

LONGBRIDGE_CMD = "longbridge"
CLAUDE_CMD = "claude"

CST = timezone(timedelta(hours=8))  # 北京时间


# ════════════════════════════════════════════════════════════════
#  工具函数
# ════════════════════════════════════════════════════════════════

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def run_longbridge(args: list, timeout=60) -> dict | list | str | None:
    """执行 longbridge CLI 命令并解析 JSON 输出."""
    cmd = [LONGBRIDGE_CMD] + args
    log(f"  ▶ longbridge {' '.join(args[:4])}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            log(f"  ⚠️  longbridge 错误 (code={result.returncode}): {result.stderr[:200]}")
            return None
        stdout = result.stdout.strip()
        if not stdout:
            return None
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return stdout
    except subprocess.TimeoutExpired:
        log(f"  ⚠️  longbridge 超时 (>{timeout}s)")
        return None
    except FileNotFoundError:
        log(f"  ❌ 找不到 longbridge CLI")
        return None


def run_claude(prompt: str, timeout=180) -> str | None:
    """调用 claude CLI 非交互模式生成内容."""
    log(f"  ▶ 调用 claude CLI 生成报告 (prompt 约 {len(prompt)} 字符)...")
    try:
        result = subprocess.run(
            [CLAUDE_CMD, "-p", prompt,
             "--dangerously-skip-permissions",
             "--allowedTools", "Read,Bash"],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            log(f"  ⚠️  claude 错误 (code={result.returncode}): {result.stderr[:300]}")
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        log(f"  ⚠️  claude 超时 (>{timeout}s)")
        return None
    except FileNotFoundError:
        log(f"  ❌ 找不到 claude CLI")
        return None


def get_time_windows(report_date: date):
    """计算新闻/话题的时间窗口 (CST)."""
    report_dt = datetime.datetime.combine(report_date, datetime.time(), tzinfo=CST)
    # 新闻窗口: 日报日期 05:00 CST → 日报次日 05:00 CST (24h)
    news_start = report_dt.replace(hour=5, minute=0, second=0, microsecond=0)
    news_end = news_start + timedelta(days=1)
    # 话题窗口: 日报前日 05:00 CST → 日报次日 05:00 CST (48h)
    topic_start = news_start - timedelta(days=1)
    topic_end = news_end

    return {
        "report_date": report_date,
        "report_date_str": report_date.strftime("%Y-%m-%d"),
        "report_date_cn": f"{report_date.year}年{report_date.month}月{report_date.day}日",
        "news_start_iso": news_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "news_end_iso": news_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "topic_start_iso": topic_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "topic_end_iso": topic_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "news_start_cst": news_start.strftime("%Y-%m-%d %H:%M CST"),
        "news_end_cst": news_end.strftime("%Y-%m-%d %H:%M CST"),
        "topic_start_cst": topic_start.strftime("%Y-%m-%d %H:%M CST"),
        "topic_end_cst": topic_end.strftime("%Y-%m-%d %H:%M CST"),
    }


def filter_by_time(items: list, start_iso: str, end_iso: str, time_key="time") -> list:
    """按 ISO 时间戳过滤."""
    if not items:
        return []
    filtered = []
    for item in items:
        t = item.get(time_key, "")
        if start_iso <= t < end_iso:
            filtered.append(item)
    return filtered


def batch_symbols(symbols: list, batch_size=50):
    """将符号列表分批."""
    for i in range(0, len(symbols), batch_size):
        yield symbols[i:i + batch_size]


# ════════════════════════════════════════════════════════════════
#  数据采集
# ════════════════════════════════════════════════════════════════

def gather_data(report_date: date):
    """采集所有数据并返回字典."""
    tw = get_time_windows(report_date)
    today = date.today()
    data = {"time_windows": tw}

    # ── Phase 1: 基础数据 ──
    log("📡 Phase 1: 采集基础数据...")

    data["market_temp"] = run_longbridge(["market-temp", "US", "--format", "json"])

    data["portfolio"] = run_longbridge(["portfolio", "--format", "json"])

    data["orders"] = run_longbridge([
        "order", "--history",
        "--start", report_date.strftime("%Y-%m-%d"),
        "--end", today.strftime("%Y-%m-%d"),
        "--format", "json"
    ])

    data["watchlist"] = run_longbridge(["watchlist", "--format", "json"])

    # 财报日历 (未来 30 天)
    data["earnings_calendar"] = run_longbridge([
        "finance-calendar", "report",
        "--filter", "watchlist",
        "--market", "US",
        "--start", today.strftime("%Y-%m-%d"),
        "--end", (today + timedelta(days=30)).strftime("%Y-%m-%d"),
        "--format", "json"
    ])

    # 宏观数据 (未来 14 天)
    data["macro_calendar"] = run_longbridge([
        "finance-calendar", "macrodata",
        "--market", "US", "--star", "3",
        "--start", today.strftime("%Y-%m-%d"),
        "--end", (today + timedelta(days=14)).strftime("%Y-%m-%d"),
        "--format", "json"
    ])

    # ── 获取持仓标的列表 ──
    holdings = []
    if isinstance(data["portfolio"], dict):
        # 尝试 portfolio.positions
        positions = data["portfolio"].get("positions", data["portfolio"].get("holdings", []))
        for p in positions:
            holdings.append({
                "symbol": p.get("symbol", p.get("code", "")),
                "name": p.get("name", p.get("symbol_name", "")),
                "market_value": p.get("market_value", p.get("market_val", 0)),
                "cost_price": p.get("cost_price", p.get("cost", 0)),
                "current_price": p.get("current_price", p.get("price", 0)),
                "quantity": p.get("quantity", p.get("qty", 0)),
                "pnl": p.get("pnl", p.get("profit_loss", 0)),
                "pnl_percent": p.get("pnl_percent", p.get("profit_loss_pct", 0)),
                "weight": p.get("weight", p.get("weight_pct", p.get("percentage", 0))),
            })
    elif isinstance(data["portfolio"], list):
        for p in data["portfolio"]:
            holdings.append({
                "symbol": p.get("symbol", p.get("code", "")),
                "name": p.get("name", p.get("symbol_name", "")),
                "market_value": p.get("market_value", p.get("market_val", 0)),
                "cost_price": p.get("cost_price", p.get("cost", 0)),
                "current_price": p.get("current_price", p.get("price", 0)),
                "quantity": p.get("quantity", p.get("qty", 0)),
                "pnl": p.get("pnl", p.get("profit_loss", 0)),
                "pnl_percent": p.get("pnl_percent", p.get("profit_loss_pct", 0)),
                "weight": p.get("weight", p.get("weight_pct", p.get("percentage", 0))),
            })
    data["holdings"] = holdings
    holding_symbols = [h["symbol"] for h in holdings if h["symbol"]]

    # ── 获取持仓报价 (含日成交数据) ──
    if holding_symbols:
        data["holding_quotes"] = run_longbridge(
            ["quote"] + holding_symbols + ["--format", "json"]
        )
    else:
        data["holding_quotes"] = []

    # ── 全部自选股 ──
    watchlist_symbols = []
    if isinstance(data["watchlist"], dict):
        items = data["watchlist"].get("items", data["watchlist"].get("symbols", []))
    elif isinstance(data["watchlist"], list):
        items = data["watchlist"]
    else:
        items = []

    for w in items:
        sym = w.get("symbol", w.get("code", ""))
        if sym:
            watchlist_symbols.append(sym)
    data["watchlist_symbols"] = watchlist_symbols
    log(f"  📋 自选股: {len(watchlist_symbols)} 只, 持仓: {len(holding_symbols)} 只")

    # ── 自选股报价 (分批, 找异动) ──
    data["watchlist_quotes"] = []
    for batch in batch_symbols(watchlist_symbols, 50):
        q = run_longbridge(["quote"] + batch + ["--format", "json"])
        if q:
            if isinstance(q, list):
                data["watchlist_quotes"].extend(q)
            else:
                data["watchlist_quotes"].append(q)

    # ── Phase 3: 持仓社区情报 ──
    log("📰 Phase 3: 采集持仓社区情报...")
    data["holding_news"] = {}
    data["holding_topics"] = {}
    for h in holdings:
        sym = h["symbol"]
        if not sym:
            continue
        log(f"  🔍 {sym}...")
        news = run_longbridge(["news", "search", sym, "--count", "20", "--format", "json"])
        if isinstance(news, list):
            data["holding_news"][sym] = filter_by_time(
                news, tw["news_start_iso"], tw["news_end_iso"]
            )[:5]
        else:
            data["holding_news"][sym] = []

        topics = run_longbridge(["topic", "search", sym, "--count", "20", "--format", "json"])
        if isinstance(topics, list):
            data["holding_topics"][sym] = filter_by_time(
                topics, tw["topic_start_iso"], tw["topic_end_iso"]
            )[:5]
        else:
            data["holding_topics"][sym] = []

    # ── Phase 4: 板块扫描 ──
    log("🔥 Phase 4: 板块热度扫描...")
    sector_keywords = ["AI", "半导体", "芯片", "原油", "能源", "光学", "光通信"]
    data["sector_news"] = {}
    data["sector_topics"] = {}
    for kw in sector_keywords:
        news = run_longbridge(["news", "search", kw, "--count", "20", "--format", "json"])
        if isinstance(news, list):
            data["sector_news"][kw] = filter_by_time(
                news, tw["news_start_iso"], tw["news_end_iso"]
            )[:10]
        else:
            data["sector_news"][kw] = []

        topics = run_longbridge(["topic", "search", kw, "--count", "20", "--format", "json"])
        if isinstance(topics, list):
            data["sector_topics"][kw] = filter_by_time(
                topics, tw["topic_start_iso"], tw["topic_end_iso"]
            )[:10]
        else:
            data["sector_topics"][kw] = []

    # ── Phase 5: 催化检查 (前 3 异动) ──
    log("⭐ Phase 5: 筛选催化机会...")
    # 找异动标的: change_percent > 3% 或 < -3%
    movers = []
    for q in data["watchlist_quotes"]:
        if not isinstance(q, dict):
            continue
        sym = q.get("symbol", q.get("code", ""))
        if sym in holding_symbols:
            continue
        chg_pct = q.get("change_percent", q.get("change_percentage", 0))
        if chg_pct is None:
            chg_pct = 0
        try:
            chg_pct = float(chg_pct)
        except (ValueError, TypeError):
            continue
        if abs(chg_pct) >= 3:
            movers.append({
                "symbol": sym,
                "name": q.get("name", q.get("symbol_name", "")),
                "last": q.get("last", q.get("price", 0)),
                "change_percent": chg_pct,
                "volume": q.get("volume", 0),
                "turnover": q.get("turnover", q.get("amount", 0)),
            })

    # 按 |change_percent| 降序排列
    movers.sort(key=lambda x: abs(x.get("change_percent", 0)), reverse=True)
    # 取前 10 检查催化
    candidates = movers[:10]
    data["catalyst_candidates"] = []
    for c in candidates:
        sym = c["symbol"]
        news = run_longbridge(["news", "search", sym, "--count", "20", "--format", "json"])
        filtered_news = []
        if isinstance(news, list):
            filtered_news = filter_by_time(news, tw["news_start_iso"], tw["news_end_iso"])[:5]
        c["news"] = filtered_news
        data["catalyst_candidates"].append(c)

    log(f"  📊 异动标的: {len(movers)} 只, 候选: {len(candidates)} 只")

    return data


# ════════════════════════════════════════════════════════════════
#  报告生成 (调用 claude CLI)
# ════════════════════════════════════════════════════════════════

def generate_report(data: dict) -> str | None:
    """使用 claude CLI 生成完整的日报 markdown."""
    tw = data["time_windows"]
    report_date_str = tw["report_date_cn"]

    # 读取 SKILL.md 作为指令
    skill_content = ""
    try:
        with open(SKILL_MD, "r") as f:
            skill_content = f.read()
    except FileNotFoundError:
        log("⚠️  SKILL.md 未找到, 使用默认指令")
        skill_content = "请生成一份专业的长桥日报。"

    # 构建数据摘要
    data_summary = {
        "report_date": tw["report_date_str"],
        "portfolio_summary": {
            "total_assets": None,
            "holdings_count": len(data.get("holdings", [])),
            "holdings": [{
                "symbol": h["symbol"],
                "name": h["name"],
                "weight": h["weight"],
                "cost_price": h["cost_price"],
                "current_price": h["current_price"],
                "pnl_percent": h["pnl_percent"],
            } for h in data.get("holdings", [])],
        },
        "orders": data.get("orders", []),
        "market_temp": data.get("market_temp", {}),
        "earnings_calendar": data.get("earnings_calendar", []),
        "macro_calendar": data.get("macro_calendar", []),
        "holding_quotes": data.get("holding_quotes", []),
        "holding_news_counts": {
            sym: len(news) for sym, news in data.get("holding_news", {}).items()
        },
        "holding_topics_counts": {
            sym: len(topics) for sym, topics in data.get("holding_topics", {}).items()
        },
        "holding_news_samples": {
            sym: [
                {"title": n.get("title", "")[:100], "time": n.get("time", "")}
                for n in news[:5]
            ]
            for sym, news in data.get("holding_news", {}).items()
        },
        "holding_topics_samples": {
            sym: [
                {"title": t.get("title", "")[:100], "time": t.get("time", "")}
                for t in topics[:5]
            ]
            for sym, topics in data.get("holding_topics", {}).items()
        },
        "sector_news_counts": {
            kw: len(news) for kw, news in data.get("sector_news", {}).items()
        },
        "sector_topics_counts": {
            kw: len(topics) for kw, topics in data.get("sector_topics", {}).items()
        },
        "catalyst_candidates": [
            {
                "symbol": c["symbol"],
                "name": c.get("name", ""),
                "last": c.get("last", 0),
                "change_percent": c.get("change_percent", 0),
                "volume": c.get("volume", 0),
                "turnover": c.get("turnover", 0),
                "news_count": len(c.get("news", [])),
                "news_samples": [
                    {"title": n.get("title", "")[:100], "time": n.get("time", "")}
                    for n in c.get("news", [])[:3]
                ],
            }
            for c in data.get("catalyst_candidates", [])
        ],
        "watchlist_count": len(data.get("watchlist_symbols", [])),
        "time_windows": {
            "news": f"{tw['news_start_cst']} ~ {tw['news_end_cst']}",
            "topics": f"{tw['topic_start_cst']} ~ {tw['topic_end_cst']}",
        },
    }

    # 构建 prompt
    prompt = f"""你是长桥日报生成器。现在需要生成 {report_date_str} 的日报。

请严格按照以下流程和格式生成完整的 markdown 报告:

## 工作流程
1. 根据下方数据生成 Market Dashboard
2. 生成 Portfolio & Position Analysis (含 Daily Performance 和 Risk Assessment)
3. 如有交易记录则生成 Trade Review
4. 生成 Holdings Intelligence (含新闻、社区、操作策略建议)
5. 生成 Sector Heat Map
6. 生成 Watchlist Catalyst Scan (含催化评分、操作策略建议)
7. 生成 Upcoming Earnings Radar

## 重要模板规则
- 表格前必须有空行
- 使用原生 emoji (🏆🥈🥉🟢🟡✅⚠️👥📰💬🔥⭐)
- h1 → h2 → h3 层级结构
- 使用 <details><summary> 标签实现操作策略建议的可折叠效果
- 每个持仓和催化标的都需要「交易员视角」和「中长期投资者视角」两个展开模块
- 每个建议需要从正反两面检视: ✅ 收益预期 / ⚠️ 风险考量
- 代码块进度条格式: ```\\n热度: ██████████ 100%  |  N+ 话题  |  N+ 互动量\\n```
- 代码块催化评分: ```\\n催化评分:  ██████████ X.X / 5.0\\n收盘数据:  $XXX  ▲ +X.XX%  |  成交量 XXX 股  |  成交额 $XX亿\\n```

## 输出文件路径
输出 markdown 直接写入 stdout, 不要添加额外说明文字。

## 数据
```json
{json.dumps(data_summary, indent=2, ensure_ascii=False, default=str)}
```

请现在直接开始生成完整的 markdown 报告。"""

    output = run_claude(prompt, timeout=300)
    if output is None:
        return None

    # 清理输出 — 移除可能的 思维链 或 说明文字
    # claude 可能输出 思维链 在  ...  标签中
    # 也可能会加 markdown 代码块包装
    cleaned = output.strip()
    # 如果被包裹在 ```markdown ... ``` 中
    m = re.search(r'^```(?:markdown)?\s*\n(.*?)\n```\s*$', cleaned, re.DOTALL)
    if m:
        cleaned = m.group(1).strip()

    # 确保以 # 开头 (说明是报告正文)
    if not cleaned.startswith("#"):
        log("⚠️  报告生成似乎不完整, 但仍然保存")
    else:
        log(f"✅ 报告生成完成 ({len(cleaned)} 字符)")

    return cleaned


# ════════════════════════════════════════════════════════════════
#  邮件发送
# ════════════════════════════════════════════════════════════════

def send_email(html_file: str, pdf_file: str, report_date_str: str):
    """通过 Gmail SMTP 发送日报."""
    if not GMAIL_PASSWORD:
        log("⚠️  未设置 GMAIL_APP_PASSWORD, 跳过邮件发送")
        log(f"  请设置: export GMAIL_APP_PASSWORD='your_app_password'")
        log(f"  HTML: {html_file}")
        log(f"  PDF: {pdf_file}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = GMAIL_USER
        msg["To"] = GMAIL_USER
        msg["Subject"] = f"📊 长桥日报 · {report_date_str}"

        # 纯文本版本
        text = f"""长桥日报 · {report_date_str}

日报已生成, 请查看附件。

HTML: {html_file}
PDF: {pdf_file}

本报告由 longbridge-daily-brief 自动生成 · 数据来源: Longbridge Securities
以上内容仅供参考，不构成投资建议。投资有风险，操作需谨慎。"""

        # HTML 版本 (直接内嵌内容)
        try:
            with open(html_file, "r") as f:
                html_content = f.read()
        except FileNotFoundError:
            html_content = f"<p>HTML 文件未找到: {html_file}</p>"

        html_part = f"""<html>
<head><meta charset="utf-8"></head>
<body>
<p>📊 <b>长桥日报 · {report_date_str}</b></p>
<hr>
{html_content}
<hr>
<p style="color:#95a5a6;font-size:11px;text-align:center;">
本报告由 longbridge-daily-brief 自动生成 · 数据来源: Longbridge Securities<br>
以上内容仅供参考，不构成投资建议。投资有风险，操作需谨慎。
</p>
</body>
</html>"""

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html_part, "html")
        msg.attach(part1)
        msg.attach(part2)

        # 附加 PDF
        try:
            with open(pdf_file, "rb") as f:
                pdf_data = f.read()
            pdf_attachment = MIMEBase("application", "pdf")
            pdf_attachment.set_payload(pdf_data)
            encoders.encode_base64(pdf_attachment)
            pdf_attachment.add_header(
                "Content-Disposition",
                f"attachment; filename=longbridge_memo_{report_date_str.replace('/', '')}.pdf"
            )
            msg.attach(pdf_attachment)
        except FileNotFoundError:
            log("⚠️  PDF 文件未找到, 跳过附件")

        # 发送
        log(f"📧 发送邮件到 {GMAIL_USER}...")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)

        log("✅ 邮件发送成功")
        return True

    except smtplib.SMTPAuthenticationError:
        log("❌ Gmail SMTP 认证失败")
        log("  请使用 Gmail App Password (不是普通密码)")
        log("  设置: https://myaccount.google.com/apppasswords")
        log("  然后: export GMAIL_APP_PASSWORD='your_16_char_password'")
        return False
    except Exception as e:
        log(f"❌ 邮件发送失败: {e}")
        return False


# ════════════════════════════════════════════════════════════════
#  Main
# ════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="长桥日报自动生成")
    parser.add_argument("--date", help="指定日期 (YYYY-MM-DD), 默认为昨日")
    parser.add_argument("--no-email", action="store_true", help="不发送邮件")
    parser.add_argument("--data-only", action="store_true", help="仅采集数据并保存, 不生成报告")
    parser.add_argument("--resend", help="重新发送指定日期的日报邮件 (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.resend:
        # 重新发送
        report_date = datetime.datetime.strptime(args.resend, "%Y-%m-%d").date()
        report_date_str = f"{report_date.year}年{report_date.month}月{report_date.day}日"
        date_ymd = report_date.strftime("%Y%m%d")
        html_file = os.path.join(BASE_DIR, f"longbridge_memo_{date_ymd}.html")
        pdf_file = os.path.join(BASE_DIR, f"longbridge_memo_{date_ymd}.pdf")

        if not os.path.exists(html_file):
            log(f"❌ HTML 文件不存在: {html_file}")
            sys.exit(1)

        send_email(html_file, pdf_file, report_date_str)
        return

    # 确定报告日期
    if args.date:
        report_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        report_date = date.today() - timedelta(days=1)

    report_date_str = f"{report_date.year}年{report_date.month}月{report_date.day}日"
    date_ymd = report_date.strftime("%Y%m%d")
    md_file = os.path.join(BASE_DIR, f"longbridge_memo_{date_ymd}.md")
    html_file = os.path.join(BASE_DIR, f"longbridge_memo_{date_ymd}.html")
    pdf_file = os.path.join(BASE_DIR, f"longbridge_memo_{date_ymd}.pdf")

    log(f"🚀 长桥日报自动生成 — {report_date_str}")
    log(f"   时间窗口: 新闻 24h / 话题 48h")
    log("")

    # ── Step 1: 采集数据 ──
    log("=" * 50)
    log("📡 数据采集阶段")
    log("=" * 50)
    data = gather_data(report_date)

    # 保存原始数据到 JSON (调试用)
    data_file = os.path.join(BASE_DIR, f".raw_data_{date_ymd}.json")
    with open(data_file, "w") as f:
        json.dump({k: v for k, v in data.items()
                   if k not in ("holding_news", "holding_topics", "sector_news", "sector_topics")},
                  f, indent=2, ensure_ascii=False, default=str)
    log(f"  💾 原始数据已保存: {data_file}")

    if args.data_only:
        log("✅ 数据采集完成 (--data-only)")
        return

    # ── Step 2: 生成报告 ──
    log("")
    log("=" * 50)
    log("📝 报告生成阶段 (调用 claude CLI)")
    log("=" * 50)
    markdown = generate_report(data)

    if not markdown:
        log("❌ 报告生成失败")
        sys.exit(1)

    # ── Step 3: 保存 markdown ──
    with open(md_file, "w") as f:
        f.write(markdown)
    log(f"  💾 报告已保存: {md_file}")

    # ── Step 4: 生成 HTML + PDF ──
    log("")
    log("=" * 50)
    log("🎨 生成 HTML + PDF")
    log("=" * 50)
    env = os.environ.copy()
    env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"
    try:
        result = subprocess.run(
            ["python3", GENERATE_PDF, md_file],
            capture_output=True, text=True, timeout=120, env=env
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                log(f"  {line}")
        else:
            log(f"⚠️  PDF 生成错误: {result.stderr[:200]}")
    except Exception as e:
        log(f"⚠️  PDF 生成失败: {e}")

    # ── Step 5: 发送邮件 ──
    if not args.no_email:
        log("")
        log("=" * 50)
        log("📧 邮件发送")
        log("=" * 50)
        send_email(html_file, pdf_file, report_date_str)
    else:
        log("⏭️  跳过邮件发送 (--no-email)")

    log("")
    log("✅" + "=" * 48)
    log("✅ 长桥日报生成完成!")
    log("✅" + "=" * 48)
    log(f"  📄 Markdown: {md_file}")
    log(f"  🌐 HTML:     {html_file}")
    log(f"  📕 PDF:      {pdf_file}")
    log(f"  📚 归档:     {ARCHIVE_FILE}")


if __name__ == "__main__":
    main()
