# Longbridge Daily Memo / 长桥日报

Automated daily investment briefing system that generates structured market reports with portfolio analysis, trade review, holdings intelligence, sector heat maps, watchlist catalyst scans, and macro liquidity monitoring.

自动生成结构化每日投资简报，涵盖仓位分析、交易复盘、持仓情报、板块热力、催化扫描和宏观流动性监控六大模块。

## Features

| Module | Description |
|--------|-------------|
| **Market Dashboard** | Multi-market temperature (US/HK/CN), VIX, treasury yields, index performance |
| **Portfolio & Position Analysis** | Holdings breakdown, P&L tracking, risk assessment |
| **Trade Review** | Execution quality evaluation with professional trader perspective |
| **Holdings Intelligence** | News + community sentiment per position, dual strategy advice (trader vs long-term) |
| **Sector Heat Map** | Community trending sectors with topic aggregation |
| **Watchlist Catalyst Scan** | 7-dimension catalyst scoring (earnings, price action, capital flow, events) |
| **Macro Liquidity Monitor** | CPI/FOMC/tariff impact analysis, position-level sensitivity |

## Output Formats

- **Markdown** — `longbridge_memo_YYYYMMDD.md` (primary source)
- **HTML** — `longbridge_memo_YYYYMMDD.html` (styled card layout)
- **PDF** — `longbridge_memo_YYYYMMDD.pdf` (print/share)
- **Archive** — `longbridge_daily_brief_archive.html` (multi-day tab switching)

## Requirements

- Python 3.8+
- [Longbridge CLI](https://open.longbridge.com) (authenticated)
- weasyprint (for PDF): `brew install weasyprint` or `pip install weasyprint`
- On Apple Silicon, set `DYLD_LIBRARY_PATH=/opt/homebrew/lib` if weasyprint can't find system libs

## Quick Start

```bash
# 1. Generate a daily report via Claude with the longbridge-daily-brief skill
# 2. The skill automatically generates Markdown + HTML + PDF
# 3. Open the archive:
open longbridge_daily_brief_archive.html
```

### Manual PDF generation

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 generate_pdf.py longbridge_memo_20260515.md
```

### Automated push (optional)

```bash
# Configure Gmail credentials in .env, then:
python3 daily_brief_auto.py
```

## Project Structure

```
longbridge/
├── .claude/skills/longbridge-daily-brief/
│   └── SKILL.md              # Skill workflow definition (6 chapter template)
├── generate_pdf.py            # Markdown → HTML → PDF pipeline
├── build_archive.py           # Multi-day archive builder
├── daily_brief_auto.py        # Gmail auto-push script
├── html_to_pdf_chrome.sh      # Chrome headless PDF fallback
├── .env.example               # Environment config template
└── .gitignore
```

## Data Sources

All data is fetched in real-time via [Longbridge Securities](https://open.longbridge.com) OpenAPI:
- Portfolio, orders, assets
- Real-time quotes, intraday K-line
- News, regulatory filings, community topics
- Analyst estimates, financial statements
- Market temperature index (0–100)

## Disclaimer

本报告由 longbridge-daily-brief 自动生成，数据来源：Longbridge Securities。
以上内容仅供参考，不构成投资建议。投资有风险，操作需谨慎。
