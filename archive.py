"""推送内容归档模块
所有推送内容自动保存到 library/ 目录，按日期组织，
INDEX.md 自动维护目录索引。
"""

import os
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
