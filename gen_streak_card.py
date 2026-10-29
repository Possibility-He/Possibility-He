#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_streak_card.py — 本地渲染 GitHub streak 卡（墨绿流金主题）

抓 https://github.com/users/<USER>/contributions 页面，解析 365+ 个
<td data-date data-level>，算出总贡献 / 当前连续 / 最长连续，输出一张
495x220 的静态 SVG（等价于 streak-stats 的卡片，但完全本地生成、样式可控）。

输出：assets/streak.svg
依赖：仅 Python 标准库。

用法：
    python gen_streak_card.py                # 用下面 USER 的默认值
    python gen_streak_card.py SomeoneElse    # 临时换用户名
"""

import os
import re
import sys
import urllib.request
from datetime import date

USER = "Possibility-He"

# 墨绿流金主题（与 profile 的 badge 配色一致）
BG = "#0d1117"
GREEN = "#2f8f5f"      # 卡片描边
RING = "#1f7a4d"       # 当前连续天数的虚线圆环
GOLD = "#d4a24e"       # 强调文字
TEXT = "#c9d1d9"
DIM = "#8b949e"        # 次要文字

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def fetch_html(url: str, retries: int = 3) -> str:
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8")
        except Exception as e:                      # noqa: BLE001
            last_err = e
            sys.stderr.write(f"fetch attempt {i + 1} failed: {e}\n")
    raise RuntimeError(f"failed to fetch {url}: {last_err}")


def parse_contrib(html: str):
    """返回 (rows, real_total)，rows = [(date, level0_4), ...] 按日期升序。"""
    matches = re.findall(
        r'<td[^>]*data-date="([^"]+)"[^>]*data-level="([^"]+)"[^>]*>', html)
    rows = []
    for d, lvl in matches:
        try:
            rows.append((date.fromisoformat(d), int(lvl)))
        except ValueError:
            continue
    rows.sort()

    # 标题里的真实总数（"347 contributions in the last year"）
    real_total = sum({0: 0, 1: 2, 2: 5, 3: 8, 4: 12}.get(lvl, 0) for _, lvl in rows)
    m = re.search(r'<h2[^>]*id="js-contribution-activity-description"[^>]*>\s*'
                  r'([\d,]+)\s+contribution', html)
    if m:
        try:
            real_total = int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return rows, real_total


def compute_streaks(rows):
    """返回 (current, current_start, longest)。rows = [(date, level), ...] 升序。"""
    longest = cur = 0
    for _, lvl in rows:
        cur = cur + 1 if lvl >= 1 else 0
        longest = max(longest, cur)

    # 今天还没提交(level=0)不算断签，否则每天早上看卡片永远是 "0"
    seq = rows
    if seq and seq[-1][0] == date.today() and seq[-1][1] == 0:
        seq = seq[:-1]

    current = 0
    current_start = None
    for d, lvl in reversed(seq):
        if lvl >= 1:
            current += 1
            current_start = d
        else:
            break
    return current, current_start, longest


def render_streak(rows, real_total: int) -> str:
    W, H = 495, 220
    current, start, longest = compute_streaks(rows)
    since = start.strftime("%b %d, %Y") if start else "—"
    cx = W // 2

    p = []
    # 卡片：深色底 + 绿色细描边 + 圆角
    p.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" '
             f'fill="{BG}" rx="6" stroke="{GREEN}" stroke-width="1"/>')

    # Total Contributions
    p.append(f'<text x="{cx}" y="28" text-anchor="middle" font-family="Segoe UI,'
             f'Arial,sans-serif" font-size="12" fill="{TEXT}" '
             f'letter-spacing="0.4">Total Contributions</text>')
    p.append(f'<text x="{cx}" y="62" text-anchor="middle" font-family="Segoe UI,'
             f'Arial,sans-serif" font-size="30" font-weight="700" fill="{TEXT}">'
             f'{real_total}</text>')

    # Current Streak：金色 label + 🔥 + 数字 + 虚线圆环
    p.append(f'<text x="{cx}" y="92" text-anchor="middle" font-family="Segoe UI,'
             f'Arial,sans-serif" font-size="12" font-weight="600" fill="{GOLD}" '
             f'letter-spacing="0.4">Current Streak</text>')
    p.append(f'<circle cx="{cx + 10}" cy="120" r="20" fill="none" stroke="{RING}" '
             f'stroke-width="1.5" stroke-dasharray="3 3"/>')
    p.append(f'<text x="{cx - 28}" y="132" text-anchor="middle" font-family="Segoe UI '
             f'Emoji,Apple Color Emoji,Segoe UI,sans-serif" font-size="28">'
             f'{chr(0x1F525)}</text>')
    p.append(f'<text x="{cx + 10}" y="130" text-anchor="middle" font-family="Segoe UI,'
             f'Arial,sans-serif" font-size="30" font-weight="700" fill="{TEXT}">'
             f'{current}</text>')
    if current:
        sub = f"since {since}"
        sub_fill = TEXT
    else:                                   # 当前没有连续记录时，比 "since —" 好读
        sub = "no active streak"
        sub_fill = DIM
    p.append(f'<text x="{cx}" y="155" text-anchor="middle" font-family="Segoe UI,'
             f'Arial,sans-serif" font-size="10" fill="{sub_fill}">{sub}</text>')

    # Longest Streak
    p.append(f'<text x="{cx}" y="180" text-anchor="middle" font-family="Segoe UI,'
             f'Arial,sans-serif" font-size="12" fill="{TEXT}" '
             f'letter-spacing="0.4">Longest Streak</text>')
    p.append(f'<text x="{cx}" y="205" text-anchor="middle" font-family="Segoe UI,'
             f'Arial,sans-serif" font-size="20" font-weight="600" fill="{TEXT}">'
             f'{longest} days</text>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">\n  ' + "\n  ".join(p) + "\n</svg>\n")


def main():
    user = sys.argv[1] if len(sys.argv) > 1 else USER
    url = f"https://github.com/users/{user}/contributions"
    print(f"[1/2] fetch {url} ...")
    html = fetch_html(url)
    rows, real_total = parse_contrib(html)
    if not rows:
        sys.exit("NO DATA — 页面结构可能变了（找不到 <td data-date data-level>）")
    current, start, longest = compute_streaks(rows)
    print(f"[1/2] {len(rows)} days: {rows[0][0]} → {rows[-1][0]}, "
          f"total={real_total}, current={current}, longest={longest}")

    svg = render_streak(rows, real_total)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "streak.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"[2/2] wrote {out} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
