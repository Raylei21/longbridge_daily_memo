#!/usr/bin/env python3
"""Convert enhanced memo markdown to styled HTML + PDF with blue/gray financial theme.

Usage:
    python3 generate_pdf.py <input.md>                    # output: input.html + input.pdf
    python3 generate_pdf.py <input.md> --output out.html  # custom HTML path
"""
import os, sys, re, markdown, subprocess
from weasyprint import HTML

# DYLD path for weasyprint on Apple Silicon: respect env var override, default to Homebrew
os.environ.setdefault('DYLD_LIBRARY_PATH', '/opt/homebrew/lib')

# ── Parse CLI args ──
if len(sys.argv) < 2:
    print("Usage: python3 generate_pdf.py <input.md> [--output <output.html>]")
    sys.exit(1)

INPUT_FILE = sys.argv[1]
OUTPUT_HTML = None
if '--output' in sys.argv:
    idx = sys.argv.index('--output')
    if idx + 1 < len(sys.argv):
        OUTPUT_HTML = sys.argv[idx + 1]

OUTPUT_PDF = OUTPUT_HTML.replace('.html', '.pdf') if OUTPUT_HTML else INPUT_FILE.replace('.md', '.pdf')

# ── Read markdown ──
with open(INPUT_FILE, 'r') as f:
    md_text = f.read()

# ── Pre-process: convert ASCII art progress bars to styled divs ──
def replace_progress_bars(md):
    """Replace ``` progress bars with styled HTML."""
    pattern = r'```\n热度: (█+)(░*) (\d+)%.*?\n```'
    def replacer(m):
        filled = len(m.group(1))
        total = filled + len(m.group(2)) if m.group(2) else filled
        pct = m.group(3)
        return f'<div class="progress-bar"><div class="progress-fill" style="width:{pct}%"></div><span class="progress-label">{pct}%</span></div>'
    return re.sub(pattern, replacer, md)

def replace_score_bars(md):
    """Replace ``` catalytic score bars with styled HTML."""
    pattern = r'```\n催化评分:\s+([█░]+)\s+([\d.]+)\s*/\s*([\d.]+).*?\n```'
    def replacer(m):
        return f'<div class="score-bar"><div class="score-fill" style="width:{float(m.group(2))/float(m.group(3))*100}%"></div><span class="score-label">{m.group(2)} / {m.group(3)}</span></div>'
    return re.sub(pattern, replacer, md)

def replace_price_status(md):
    """Replace price status code blocks."""
    pattern = r'```\n(?:盘前状态|收盘数据):\s+([\$\d\.,]+)\s+([▲▼])\s*([+-][\d.]+%).*?\n```'
    def replacer(m):
        arrow = '^' if m.group(2) == '▲' else 'v'
        color = '#27ae60' if m.group(2) == '▲' else '#e74c3c'
        return f'<div class="price-status" style="color:{color}">{arrow} {m.group(1)} <strong>{m.group(3)}</strong></div>'
    return re.sub(pattern, replacer, md)

# Apply structure replacements first (they match on original Unicode chars)
md_text = replace_progress_bars(md_text)
md_text = replace_score_bars(md_text)
md_text = replace_price_status(md_text)

# ── Convert markdown to HTML ──
html_body = markdown.markdown(md_text, extensions=['tables', 'fenced_code', 'codehilite'])

# ── HTML Template ──
html_template = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
@page {{
  size: A4;
  margin: 2cm 1.8cm 2.5cm 1.8cm;
  @bottom-center {{
    content: counter(page) " / " counter(pages);
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 9pt;
    color: #95a5a6;
  }}
}}

* {{
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
  max-width: 920px;
  margin: 0 auto;
  padding: 30px 48px;
  background: #ffffff;
  min-height: 100vh;
}}

/* ── Header ── */
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

/* ── Section headers (━━ style) ── */
h2 {{
  font-size: 13pt;
  color: #2C5F8A;
  margin-top: 22pt;
  margin-bottom: 12pt;
  padding-bottom: 6pt;
  border-bottom: 2px solid #2C5F8A;
  letter-spacing: 0.05em;
}}

/* ── Sub headers ── */
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

/* ── Tables ── */
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

/* ── Blockquotes (summary boxes) ── */
blockquote {{
  background: #f0f4f8;
  border-left: 4px solid #2C5F8A;
  padding: 10pt 14pt;
  margin: 10pt 0;
  font-size: 9.5pt;
  color: #34495e;
  border-radius: 0 4pt 4pt 0;
}}

/* ── Lists ── */
ul, ol {{
  margin: 6pt 0 8pt 20pt;
}}
li {{
  margin-bottom: 3pt;
}}

/* ── Strong / Bold ── */
strong {{
  color: #1B2A4A;
}}

/* ── Code blocks / inline ── */
code {{
  font-family: 'SF Mono', 'Menlo', monospace;
  font-size: 8.5pt;
  background: #f0f4f8;
  padding: 1pt 4pt;
  border-radius: 3pt;
  color: #2C5F8A;
}}

/* ── Horizontal rules ── */
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

/* ── Section divider (━━) in h2 ── */
h2 code {{
  background: transparent;
  color: #2C5F8A;
  font-size: 11pt;
  font-weight: 400;
}}

/* ── Footers / disclaimers ── */
p:last-child {{
  margin-top: 20pt;
  font-size: 8pt;
  color: #95a5a6;
  text-align: center;
  border-top: 1px solid #d5dfe8;
  padding-top: 12pt;
}}

/* ── Inline elements ── */
.danger {{ color: #e74c3c; font-weight: 600; }}
.success {{ color: #27ae60; font-weight: 600; }}
.warning {{ color: #f39c12; font-weight: 600; }}

/* ── KBD-style tags ── */
.tag {{
  display: inline-block;
  background: #e8f0fe;
  color: #2C5F8A;
  padding: 1pt 6pt;
  border-radius: 3pt;
  font-size: 8pt;
  font-weight: 600;
}}

/* Avoid page breaks inside cards */
h3, table, blockquote {{
  page-break-inside: avoid;
}}
</style>
</head>
<body>
{html_body}
</body>
</html>'''

# ── Write HTML & render PDF ──
html_file = OUTPUT_HTML if OUTPUT_HTML else INPUT_FILE.replace('.md', '.html')
with open(html_file, 'w') as f:
    f.write(html_template)

HTML(filename=html_file).write_pdf(OUTPUT_PDF)

print(f'PDF generated: {OUTPUT_PDF}')
print(f'HTML generated: {html_file}')

# ── Rebuild archive ──
archive_script = os.path.join(os.path.dirname(__file__), 'build_archive.py')
try:
    result = subprocess.run(['python3', archive_script], capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        for line in result.stdout.strip().split('\n'):
            print(f'  [archive] {line}')
    else:
        print(f'  [archive] Error: {result.stderr.strip()}')
except Exception as e:
    print(f'  [archive] Failed: {e}')
