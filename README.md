# 长桥日报 (Longbridge Daily Memo)

自动生成每日投资简报的系统。涵盖仓位分析、交易复盘、持仓情报、社区板块热力、自选股催化机会扫描和宏观流动性监控六大模块。支持 Markdown / HTML / PDF 三种输出格式及多日报归档。

## 功能模块

| 模块 | 说明 |
|------|------|
| **Market Dashboard** | 多市场温度（美股/港股/A股）、VIX恐慌指数、国债收益率、主要指数表现 |
| **仓位与操作分析** | 持仓盈亏、集中度评估、风险评估、当日交易回顾 |
| **交易复盘** | 每笔交易的执行价格、仓位管理、时机选择三维度评价，含专业交易员视角 |
| **持仓公司社区情报** | 各持仓标的新闻动态 + 社区讨论，交易员 vs 中长期投资者双视角策略建议 |
| **社区热力板块扫描** | 聚合多关键词话题数据，识别当前社区讨论热度最高的板块 |
| **自选股催化机会扫描** | 从全部自选股中，综合催化事件、股价异动、资金流向、社区热度、确定性五维评分，筛选出最具潜力的3只标的 |
| **宏观流动性监控** | CPI/FOMC/关税等宏观数据跟踪，各持仓标的利率敏感性分析，现金管理建议 |

## 输出格式

- **Markdown** — `longbridge_memo_YYYYMMDD.md`（原始报告）
- **HTML** — `longbridge_memo_YYYYMMDD.html`（美化卡片式布局，适合浏览器阅读）
- **PDF** — `longbridge_memo_YYYYMMDD.pdf`（打印/分享）
- **归档** — `longbridge_daily_brief_archive.html`（多日报 tab 切换翻阅，自动维护）

## 环境要求

- Python 3.8+
- [Longbridge CLI](https://open.longbridge.com)（已登录授权）
- weasyprint（PDF 生成）：`brew install weasyprint` 或 `pip install weasyprint`
- Apple Silicon 用户如遇到 weasyprint 找不到系统库，设置 `DYLD_LIBRARY_PATH=/opt/homebrew/lib`

## 快速开始

本技能通过 Claude Code 运行，工作流程如下：

```bash
# 1. 在 Claude Code 中调用 longbridge-daily-brief 技能生成日报
# 2. 系统会自动获取行情/持仓/新闻/社区数据
# 3. 生成 Markdown 报告后自动调用 generate_pdf.py 生成 HTML 和 PDF
# 4. 归档文件自动更新

# 查看所有历史日报
open longbridge_daily_brief_archive.html
```

### 单独生成 PDF

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 generate_pdf.py longbridge_memo_20260515.md
```

### 自动邮件推送（可选）

在 `.env` 中配置 Gmail 凭证后：

```bash
python3 daily_brief_auto.py
```

## 项目结构

```
longbridge/
├── .claude/skills/longbridge-daily-brief/
│   └── SKILL.md              # 技能工作流模板（六大章节 + 数据采集 + 输出格式）
├── generate_pdf.py            # Markdown → HTML → PDF 生成管线
├── build_archive.py           # 多日报归档构建（tab 切换页面）
├── daily_brief_auto.py        # Gmail 自动推送脚本（可选）
├── html_to_pdf_chrome.sh      # Chrome 无头模式 PDF 备用方案
├── .env.example               # 环境变量配置模板
├── .gitignore                 # Git 忽略规则
└── README.md                  # 本文件
```

## 数据来源

所有数据通过 [长桥证券 OpenAPI](https://open.longbridge.com) 实时获取：

- 持仓组合、订单记录、资产概览
- 实时行情、日内 K 线
- 新闻资讯、监管文件、社区话题
- 分析师预期、财务报表
- 市场温度指数（0-100）

## 数据时间窗口

日报以 T-1 日为报告日期，数据采集按以下窗口过滤：

| 数据类型 | 时间窗口 |
|----------|----------|
| 持仓+盈亏 | 当前快照 |
| 交易记录 | T-1 日全天 |
| 新闻 | 严格 24h（T-1 05:00 CST ~ T 05:00 CST） |
| 话题 | 宽松 48h（T-2 05:00 CST ~ T 05:00 CST） |
| 报价/资金流向 | 当前交易数据 |

## 免责声明

本报告由 longbridge-daily-brief 自动生成，数据来源：Longbridge Securities。
以上内容仅供参考，不构成投资建议。投资有风险，操作需谨慎。
