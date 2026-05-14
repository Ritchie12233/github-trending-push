"""推送内容归档模块
所有推送内容自动保存到 library/ 目录，按日期组织，
INDEX.md 自动维护目录索引。包含去重查询功能。
"""

import os
import re
import glob
from datetime import datetime, timezone, timedelta

KL_TZ = timezone(timedelta(hours=8))
LIBRARY_DIR = "library"


def save(category, content):
    """保存推送内容到 library/YYYY-MM-DD/HH-MM-category.md"""
    now = datetime.now(KL_TZ)
    date_dir = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H-%M")

    dir_path = os.path.join(LIBRARY_DIR, date_dir)
    os.makedirs(dir_path, exist_ok=True)

    filename = f"{time_str}-{category}.md"
    filepath = os.path.join(dir_path, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  📁 已归档: {filepath}")

    # 每次保存后重建索引
    rebuild_index()
    return filepath


def rebuild_index():
    """重建 library/INDEX.md"""
    os.makedirs(LIBRARY_DIR, exist_ok=True)

    # 扫描所有日期目录
    date_dirs = sorted(
        [d for d in os.listdir(LIBRARY_DIR) if os.path.isdir(os.path.join(LIBRARY_DIR, d))],
        reverse=True,
    )

    lines = [
        "# 📚 推送归档索引",
        "",
        "> 自动维护，每次推送后更新。点击文件名直接查看。",
        "",
    ]

    for date_dir in date_dirs:
        dir_path = os.path.join(LIBRARY_DIR, date_dir)
        files = sorted(os.listdir(dir_path))
        if not files:
            continue

        # 解析日期为星期几
        try:
            d = datetime.strptime(date_dir, "%Y-%m-%d")
            weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            label = f"{date_dir} {weekdays[d.weekday()]}"
        except ValueError:
            label = date_dir

        emoji_map = {
            "新闻早报": "📰", "新闻晚报": "🌙",
            "GitHub精选": "📦", "本周汇总": "📊",
            "每日概念卡": "📖", "每日工具": "🔧",
        }

        lines.append(f"## {label}")
        for f in files:
            # 提取分类名
            parts = f.rsplit("-", 1)[-1].replace(".md", "") if "-" in f else f
            emoji = emoji_map.get(parts, "📄")
            lines.append(f"- {emoji} [{parts}]({date_dir}/{f})")
        lines.append("")

    with open(os.path.join(LIBRARY_DIR, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("  📑 INDEX.md 已更新")


# ── 去重查询 ──────────────────────────────────────────────

def _read_archives(category_filter, days=5):
    """读取最近 N 天指定分类的归档内容，返回列表"""
    results = []
    now_kl = datetime.now(KL_TZ)
    for i in range(days):
        date_str = (now_kl - timedelta(days=i)).strftime("%Y-%m-%d")
        dir_path = os.path.join(LIBRARY_DIR, date_str)
        if not os.path.isdir(dir_path):
            continue
        for f in sorted(os.listdir(dir_path)):
            if category_filter in f and f.endswith(".md"):
                filepath = os.path.join(dir_path, f)
                try:
                    with open(filepath, encoding="utf-8") as fh:
                        results.append(fh.read())
                except Exception:
                    pass
    return results


def get_recent_github_repos(days=5):
    """提取最近 N 天 GitHub 推送中推荐过的仓库名（owner/repo）"""
    repos = set()
    for content in _read_archives("GitHub精选", days):
        for m in re.finditer(r"原名：(\S+)", content):
            repos.add(m.group(1))
    for content in _read_archives("本周汇总", days):
        for m in re.finditer(r"原名：(\S+)", content):
            repos.add(m.group(1))
    return sorted(repos)


def get_today_concepts():
    """今天已推送过的概念名称列表"""
    concepts = []
    today = datetime.now(KL_TZ).strftime("%Y-%m-%d")
    for content in _read_archives("每日概念卡", 1):
        m = re.search(r"今天搞懂：(.+)", content)
        if m:
            concepts.append(m.group(1).strip())
    return concepts


def get_today_tools():
    """今天已推送过的工具名称列表"""
    tools = []
    today = datetime.now(KL_TZ).strftime("%Y-%m-%d")
    for content in _read_archives("每日工具", 1):
        m = re.search(r"今日推荐：(.+)", content)
        if m:
            tools.append(m.group(1).strip())
    return tools


def get_recent_news_headlines(days=2):
    """提取最近 N 天新闻推送中的标题，用于去重"""
    headlines = set()
    for content in _read_archives("新闻早报", days):
        for m in re.finditer(r"^\d+\.\s+(.+)$", content, re.MULTILINE):
            headlines.add(m.group(1).strip()[:60])
    for content in _read_archives("新闻晚报", days):
        for m in re.finditer(r"^\d+\.\s+(.+)$", content, re.MULTILINE):
            headlines.add(m.group(1).strip()[:60])
    return sorted(headlines)
