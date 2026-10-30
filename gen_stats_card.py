#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_stats_card.py — 本地渲染 GitHub Stats 卡（墨绿流金主题，495x195）

为什么要本地生成：公共 github-readme-stats 实例长期 503，卡片会变成破图。
这里直接调 GitHub REST API 自己算，输出 assets/stats.svg，零第三方依赖。

指标与口径：
  Total Stars Earned  = 所有公开仓库的 stargazers 之和
  Total Commits       = 各仓库中 author=本人 的提交数之和（公开仓库）
  Total PRs / Issues  = search API（author:本人 type:pr / type:issue）
  Contributions (1y)  = 贡献日历页 h2 里的总数（含私有，若账号已开启展示）
  Rank（环里的字母）  = 按 github-readme-stats 的加权中位数公式近似计算

依赖：仅 Python 标准库。用法：
    python gen_stats_card.py                 # 用下面 USER 的默认值
    python gen_stats_card.py SomeoneElse     # 临时换用户名
可选环境变量 GITHUB_TOKEN：带上它可把 API 限额从 60/h 提到 5000/h。
"""

import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

USER = "Possibility-He"

# 墨绿流金主题
BG = "#0d1117"
GREEN = "#2f8f5f"
RING = "#1f7a4d"
TRACK = "#30363d"
GOLD = "#d4a24e"
TEXT = "#c9d1d9"
DIM = "#8b949e"

UA = "possibility-he-profile-card-generator"
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()


# ---------- GitHub API ----------
def api(path: str):
    req = urllib.request.Request(f"{API}{path}", headers={
        "User-Agent": UA,
        "Accept": "application/vnd.github+json",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode("utf-8")
        return (json.loads(raw) if raw.strip() else None), dict(r.headers)


def count_commits(user: str, full_name: str) -> int:
    """某仓库里 author=user 的提交数：用 per_page=1 取 Link 头里的 last 页码。"""
    req = urllib.request.Request(
        f"{API}/repos/{full_name}/commits?author={user}&per_page=1",
        headers={"User-Agent": UA, "Accept": "application/vnd.github+json",
                 **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            link = r.headers.get("Link", "")
            items = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:      # 空仓库返回 409/404
        if e.code in (404, 409):
            return 0
        raise
    if 'rel="last"' in link:
        for part in link.split(","):
            if 'rel="last"' in part:
                m = re.search(r"[?&]page=(\d+)", part)
                if m:
                    return int(m.group(1))
    return len(items)


def search_count(query: str) -> int:
    data, _ = api(f"/search/issues?q={urllib.parse.quote(query)}&per_page=1")
    return int(data.get("total_count", 0))


def contributions_last_year(user: str) -> int:
    """复用 streak 卡那套：解析贡献日历页 h2 的总数。"""
    req = urllib.request.Request(f"https://github.com/users/{user}/contributions",
                                headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8")
    m = re.search(r'<h2[^>]*id="js-contribution-activity-description"[^>]*>\s*'
                  r'([\d,]+)\s+contribution', html)
    return int(m.group(1).replace(",", "")) if m else 0


# ---------- rank（github-readme-stats 的加权公式，近似复刻） ----------
def calculate_rank(stars: int, commits: int, prs: int, issues: int, followers: int):
    def cdf(x):                       # 1 - 2^-x
        return 1 - 2 ** (-x)

    medians = {"commits": 250, "prs": 50, "issues": 25, "stars": 50, "followers": 10}
    weights = {"commits": 2, "prs": 3, "issues": 1, "stars": 4, "followers": 1}
    vals = {"commits": commits, "prs": prs, "issues": issues,
            "stars": stars, "followers": followers}

    total_w = sum(weights.values())
    acc = sum(weights[k] * cdf(vals[k] / medians[k]) for k in weights)
    rank = 1 - acc / total_w          # 0 = 最强，1 = 最弱
    score = round(rank * 100, 2)      # 环里画多少（越大越"靠近 C"）

    thresholds = [1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100]
    levels = ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"]
    level = min(sum(1 for t in thresholds if score >= t), len(levels) - 1)
    return levels[level], score


# ---------- 画卡片 ----------
def render(stats: dict) -> str:
    W, H = 495, 195
    grade, score = stats["grade"], stats["score"]
    rows = [
        ("⭐", "Total Stars Earned", stats["stars"]),
        ("🕒", "Total Commits", stats["commits"]),
        ("🔀", "Total PRs", stats["prs"]),
        ("🐛", "Total Issues", stats["issues"]),
        ("📈", "Contributions (1y)", stats["contrib"]),
    ]

    p = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" fill="{BG}" rx="6" '
         f'stroke="{GREEN}" stroke-width="1"/>']
    p.append(f'<text x="26" y="34" font-family="Segoe UI,Arial,sans-serif" font-size="16" '
             f'font-weight="700" fill="{GOLD}">{stats["title"]}</text>')

    y = 66
    for icon, label, value in rows:
        p.append(f'<text x="26" y="{y}" font-family="Segoe UI Emoji,Segoe UI,sans-serif" '
                 f'font-size="13">{icon}</text>')
        p.append(f'<text x="48" y="{y}" font-family="Segoe UI,Arial,sans-serif" '
                 f'font-size="13" font-weight="600" fill="{TEXT}">{label}:</text>')
        p.append(f'<text x="292" y="{y}" text-anchor="end" '
                 f'font-family="Segoe UI,Arial,sans-serif" font-size="13" '
                 f'font-weight="700" fill="#ffffff">{value}</text>')
        y += 24

    # 右下的评级环：底色环 + 按 score 画的弧
    cx, cy, r = 386, 104, 46
    circ = 2 * math.pi * r
    filled = circ * min(max(score, 0), 100) / 100
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{TRACK}" '
             f'stroke-width="8" stroke-linecap="round"/>')
    if filled > 1:
        p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{GOLD}" '
                 f'stroke-width="8" stroke-linecap="round" '
                 f'stroke-dasharray="{filled:.1f} {circ - filled:.1f}" '
                 f'transform="rotate(-90 {cx} {cy})"/>')
    p.append(f'<text x="{cx}" y="{cy + 9}" text-anchor="middle" '
             f'font-family="Segoe UI,Arial,sans-serif" font-size="26" '
             f'font-weight="700" fill="#ffffff">{grade}</text>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">\n  ' + "\n  ".join(p) + "\n</svg>\n")


def main():
    user = sys.argv[1] if len(sys.argv) > 1 else USER

    print(f"[1/3] {user}: 拉取 user / repos ...")
    u, _ = api(f"/users/{user}")
    repos, _ = api(f"/users/{user}/repos?per_page=100&type=owner")
    stars = sum(r.get("stargazers_count", 0) for r in repos)

    print(f"[2/3] 统计 {len(repos)} 个仓库的提交数 ...")
    commits = 0
    for r in repos:
        n = count_commits(user, r["full_name"])
        if n:
            print(f"      {r['name']}: {n}")
        commits += n

    prs = search_count(f"author:{user} type:pr")
    issues = search_count(f"author:{user} type:issue")
    contrib = contributions_last_year(user)
    grade, score = calculate_rank(stars, commits, prs, issues, int(u.get("followers", 0)))

    stats = {
        "title": f"{u.get('name') or user}'s GitHub Stats",
        "stars": stars, "commits": commits, "prs": prs, "issues": issues,
        "contrib": contrib, "grade": grade, "score": score,
    }
    print("[3/3] 数据:", json.dumps({k: v for k, v in stats.items() if k != "title"},
                                   ensure_ascii=False))

    svg = render(stats)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "stats.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"[3/3] wrote {out} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
