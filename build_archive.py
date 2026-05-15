#!/usr/bin/env python3
"""Build a tabbed archive HTML from all daily brief HTML files.

Scans for longbridge_memo_*.html files, extracts each day's content,
and assembles them into a single archive file with tab navigation.

Usage:
    python3 build_archive.py                              # build from all existing daily files
    python3 build_archive.py --open                        # build + open in browser
"""
import os, sys, re, glob, json
from datetime import datetime

# Auto-detect project root: script's parent directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_FILE = os.path.join(BASE_DIR, 'longbridge_daily_brief_archive.html')
CACHE_FILE = os.path.join(BASE_DIR, '.archive_cache.json')

# ── Helpers ──

def extract_date_from_filename(f):
    """Extract YYYYMMDD from filename like longbridge_memo_20260511.html"""
    m = re.search(r'(\d{8})', os.path.basename(f))
    return m.group(1) if m else None

def extract_body_content(html_content):
    """Extract content between <body> and </body> tags."""
    m = re.search(r'<body>\s*(.*?)\s*</body>', html_content, re.DOTALL)
    return m.group(1).strip() if m else ''

def format_date_display(date_str):
    """Convert YYYYMMDD to display format like '2026/05/11'."""
    dt = datetime.strptime(date_str, '%Y%m%d')
    return dt.strftime('%Y/%m/%d')

def format_date_short(date_str):
    """Convert YYYYMMDD to short format like '05/11'."""
    dt = datetime.strptime(date_str, '%Y%m%d')
    return dt.strftime('%m/%d')

def weekday_chinese(date_str):
    """Get Chinese weekday name."""
    dt = datetime.strptime(date_str, '%Y%m%d')
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    return weekdays[dt.weekday()]

# ── Main ──

def build_archive():
    # Find all individual daily HTML files
    html_files = sorted(glob.glob(os.path.join(BASE_DIR, 'longbridge_memo_*.html')))

    # Exclude the archive file itself
    html_files = [f for f in html_files if 'archive' not in os.path.basename(f)]

    if not html_files:
        print('No daily brief HTML files found.')
        return

    # Extract date and content for each
    entries = []
    for f in html_files:
        date_str = extract_date_from_filename(f)
        if not date_str:
            continue
        with open(f, 'r') as fh:
            content = fh.read()
        body = extract_body_content(content)
        if not body:
            print(f'Warning: no body content in {f}, skipping')
            continue
        display_date = format_date_display(date_str)
        short_date = format_date_short(date_str)
        weekday = weekday_chinese(date_str)
        entries.append({
            'date': date_str,
            'display': display_date,
            'short': short_date,
            'weekday': weekday,
            'content': body,
            'filename': os.path.basename(f),
        })

    if not entries:
        print('No valid daily brief entries found.')
        return

    # Sort by date (newest first → leftmost tab is latest)
    entries.sort(key=lambda x: x['date'], reverse=True)

    # Save cache for future incremental updates
    cache = [{'date': e['date'], 'filename': e['filename']} for e in entries]
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

    # ── Build tab bar HTML ──
    tab_buttons = ''
    for i, e in enumerate(entries):
        active = ' active' if i == 0 else ''
        tab_buttons += (
            f'<button class="tab-btn{active}" data-tab="{e["date"]}" '
            f'title="{e["display"]} {e["weekday"]}">'
            f'{e["short"]}<span class="tab-weekday">{e["weekday"]}</span>'
            f'</button>\n'
        )

    # ── Build tab panels HTML ──
    panels_html = ''
    for i, e in enumerate(entries):
        active = ' active' if i == 0 else ''
        panels_html += (
            f'<div class="tab-panel{active}" id="tab-{e["date"]}">\n'
            f'{e["content"]}\n'
            f'</div>\n'
        )

    # ── Build complete archive HTML ──
    archive_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>长桥日报归档 · Longbridge Daily Brief Archive</title>
<style>
/* ── Reset ── */
*, *::before, *::after {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}

html {{
  background: #eef0f3;
}}

body {{
  font-family: 'Helvetica Neue', Helvetica, Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 10pt;
  line-height: 1.75;
  color: #2c3e50;
  background: #ffffff;
  min-height: 100vh;
}}

/* ── Archive Header ── */
.archive-header {{
  background: linear-gradient(135deg, #1B2A4A 0%, #2C5F8A 100%);
  color: white;
  padding: 20px 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}}

.archive-header h1 {{
  font-size: 16pt;
  font-weight: 700;
  letter-spacing: 0.05em;
}}

.archive-header .subtitle {{
  font-size: 9pt;
  color: rgba(255,255,255,0.75);
}}

.archive-header .report-count {{
  font-size: 9pt;
  background: rgba(255,255,255,0.15);
  padding: 4px 12px;
  border-radius: 12px;
}}

/* ── Tab Bar ── */
.tab-bar {{
  display: flex;
  background: #f0f4f8;
  border-bottom: 2px solid #d5dfe8;
  padding: 0 48px;
  position: sticky;
  top: 0;
  z-index: 100;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
}}

.tab-bar::-webkit-scrollbar {{
  height: 4px;
}}

.tab-bar::-webkit-scrollbar-thumb {{
  background: #b0bec5;
  border-radius: 2px;
}}

.tab-btn {{
  background: transparent;
  border: none;
  padding: 10px 16px;
  font-size: 9.5pt;
  font-family: inherit;
  color: #5D6D7E;
  cursor: pointer;
  white-space: nowrap;
  position: relative;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}}

.tab-btn:hover {{
  color: #1B2A4A;
  background: rgba(44,95,138,0.06);
}}

.tab-btn.active {{
  color: #1B2A4A;
  font-weight: 700;
  background: white;
}}

.tab-btn.active::after {{
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  right: 0;
  height: 3px;
  background: #2C5F8A;
  border-radius: 2px 2px 0 0;
}}

.tab-weekday {{
  font-size: 7.5pt;
  color: #95a5a6;
  font-weight: 400;
}}

.tab-btn.active .tab-weekday {{
  color: #5D6D7E;
}}

/* ── Tab Panels ── */
.tab-panel {{
  display: none;
  max-width: 920px;
  margin: 0 auto;
  padding: 30px 48px;
}}

.tab-panel.active {{
  display: block;
}}

/* ── Content Styles (same as individual daily brief) ── */

h1 {{
  font-size: 22pt;
  color: #1B2A4A;
  text-align: center;
  letter-spacing: 0.1em;
  margin-bottom: 2pt;
  font-weight: 700;
}}
h1 + h2 {{
  font-size: 13pt;
  color: #5D6D7E;
  text-align: center;
  font-weight: 400;
  margin-bottom: 18pt;
  letter-spacing: 0.05em;
}}
h1 + h2 + hr {{
  border: none;
  height: 2px;
  background: linear-gradient(to right, transparent, #1B2A4A, transparent);
  margin-bottom: 20pt;
}}

h2 {{
  font-size: 13pt;
  color: #2C5F8A;
  margin-top: 22pt;
  margin-bottom: 12pt;
  padding-bottom: 6pt;
  border-bottom: 2px solid #2C5F8A;
  letter-spacing: 0.05em;
}}

h3 {{
  font-size: 11pt;
  color: #1B2A4A;
  margin-top: 16pt;
  margin-bottom: 8pt;
}}

h4 {{
  font-size: 10.5pt;
  color: #2C5F8A;
  margin-top: 12pt;
  margin-bottom: 6pt;
}}

table {{
  width: 100%;
  border-collapse: collapse;
  margin: 10pt 0 14pt 0;
  font-size: 9pt;
}}
th {{
  background: #1B2A4A;
  color: white;
  padding: 6pt 8pt;
  text-align: left;
  font-weight: 600;
  font-size: 8.5pt;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}}
td {{
  padding: 5pt 8pt;
  border-bottom: 1px solid #e0e6ed;
}}
tr:nth-child(even) td {{
  background: #f4f7fb;
}}
tr:hover td {{
  background: #e8f0fe;
}}

blockquote {{
  background: #f0f4f8;
  border-left: 4px solid #2C5F8A;
  padding: 10pt 14pt;
  margin: 10pt 0;
  font-size: 9.5pt;
  color: #34495e;
  border-radius: 0 4pt 4pt 0;
}}

ul, ol {{
  margin: 6pt 0 8pt 20pt;
}}
li {{
  margin-bottom: 3pt;
}}

strong {{
  color: #1B2A4A;
}}

code {{
  font-family: 'SF Mono', 'Menlo', monospace;
  font-size: 8.5pt;
  background: #f0f4f8;
  padding: 1pt 4pt;
  border-radius: 3pt;
  color: #2C5F8A;
}}

hr {{
  border: none;
  height: 1px;
  background: #d5dfe8;
  margin: 16pt 0;
}}

/* ── Progress bars (sector heat) ── */
.progress-bar {{
  background: #e8ecef;
  border-radius: 8pt;
  height: 20pt;
  position: relative;
  margin: 8pt 0;
  overflow: hidden;
}}
.progress-fill {{
  height: 100%;
  background: linear-gradient(90deg, #2C5F8A, #1B2A4A);
  border-radius: 8pt;
}}
.progress-label {{
  position: absolute;
  left: 12pt;
  top: 50%;
  transform: translateY(-50%);
  font-size: 9pt;
  font-weight: 700;
  color: white;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}}

/* ── Score bars (catalyst) ── */
.score-bar {{
  background: #e8ecef;
  border-radius: 8pt;
  height: 18pt;
  position: relative;
  margin: 6pt 0;
  overflow: hidden;
}}
.score-fill {{
  height: 100%;
  background: linear-gradient(90deg, #2980b9, #1a5276);
  border-radius: 8pt;
}}
.score-label {{
  position: absolute;
  left: 12pt;
  top: 50%;
  transform: translateY(-50%);
  font-size: 9pt;
  font-weight: 700;
  color: white;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}}

/* ── Price status ── */
.price-status {{
  font-size: 11pt;
  font-weight: 600;
  padding: 4pt 0;
}}

/* ── Section divider in h2 ── */
h2 code {{
  background: transparent;
  color: #2C5F8A;
  font-size: 11pt;
  font-weight: 400;
}}

/* ── Disclaimers ── */
p:last-child {{
  margin-top: 20pt;
  font-size: 8pt;
  color: #95a5a6;
  text-align: center;
  border-top: 1px solid #d5dfe8;
  padding-top: 12pt;
}}

.danger {{ color: #e74c3c; font-weight: 600; }}
.success {{ color: #27ae60; font-weight: 600; }}
.warning {{ color: #f39c12; font-weight: 600; }}

.tag {{
  display: inline-block;
  background: #e8f0fe;
  color: #2C5F8A;
  padding: 1pt 6pt;
  border-radius: 3pt;
  font-size: 8pt;
  font-weight: 600;
}}

/* ── Responsive ── */
@media (max-width: 768px) {{
  .archive-header {{
    padding: 16px 20px;
  }}
  .tab-bar {{
    padding: 0 12px;
  }}
  .tab-btn {{
    padding: 8px 12px;
    font-size: 9pt;
  }}
  .tab-panel {{
    padding: 20px 20px;
  }}
}}
</style>
</head>
<body>

<!-- Archive Header -->
<div class="archive-header">
  <div>
    <h1>长桥日报归档</h1>
    <div class="subtitle">Longbridge Daily Brief Archive</div>
  </div>
  <div class="report-count">共 {len(entries)} 期</div>
</div>

<!-- Tab Bar -->
<div class="tab-bar">
{tab_buttons}
</div>

<!-- Tab Panels -->
{panels_html}

<!-- Tab Switching JavaScript -->
<script>
(function() {{
  const tabs = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.tab-panel');

  function switchTab(date) {{
    // Update buttons
    tabs.forEach(btn => {{
      btn.classList.toggle('active', btn.dataset.tab === date);
    }});
    // Update panels
    panels.forEach(panel => {{
      panel.classList.toggle('active', panel.id === 'tab-' + date);
    }});
    // Save preference
    try {{
      localStorage.setItem('daily_brief_last_tab', date);
    }} catch(e) {{}}
  }}

  // Click handler
  tabs.forEach(btn => {{
    btn.addEventListener('click', function() {{
      switchTab(this.dataset.tab);
    }});
  }});

  // Restore last viewed tab, or keep default (newest = first)
  try {{
    const lastTab = localStorage.getItem('daily_brief_last_tab');
    if (lastTab && document.getElementById('tab-' + lastTab)) {{
      switchTab(lastTab);
    }}
  }} catch(e) {{}}

  // Keyboard shortcuts
  document.addEventListener('keydown', function(e) {{
    const activeBtn = document.querySelector('.tab-btn.active');
    if (!activeBtn) return;
    const btns = Array.from(tabs);
    const idx = btns.indexOf(activeBtn);
    if (e.key === 'ArrowLeft' && idx > 0) {{
      switchTab(btns[idx - 1].dataset.tab);
      btns[idx - 1].scrollIntoView({{ behavior: 'smooth', block: 'nearest', inline: 'center' }});
    }}
    if (e.key === 'ArrowRight' && idx < btns.length - 1) {{
      switchTab(btns[idx + 1].dataset.tab);
      btns[idx + 1].scrollIntoView({{ behavior: 'smooth', block: 'nearest', inline: 'center' }});
    }}
  }});
}})();
</script>

</body>
</html>'''

    with open(ARCHIVE_FILE, 'w') as f:
        f.write(archive_html)

    print(f'Archive built: {ARCHIVE_FILE}')
    print(f'  Entries: {len(entries)}')
    for e in entries:
        print(f'    {e["display"]} {e["weekday"]}  ← {e["filename"]}')

    if '--open' in sys.argv:
        os.system(f'open "{ARCHIVE_FILE}"')


if __name__ == '__main__':
    build_archive()
