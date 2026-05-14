"""每日工具/技巧卡 — 每天下午5:30
一个实用工具或 Python 技巧，马上能用。
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
SERVERCHAN_SENDKEY = os.environ["SERVERCHAN_SENDKEY"]
DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"
SERVERCHAN_API = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
KL_TZ = timezone(timedelta(hours=8))

# ── 工具库：按类别，每天轮换 ──────────────────────────────
TOOLS = {
    "Python库": [
        ("tqdm", "一行代码给循环加进度条，训练模型时必备"),
        ("pathlib", "Python 标准库的现代化文件路径操作，告别 os.path"),
        ("rich", "终端美化打印，表格、进度条、语法高亮一站式"),
        ("pydantic", "数据校验神器，FastAPI 的核心，让类型安全落到实处"),
        ("functools.lru_cache", "一行装饰器实现函数结果缓存，加速重复计算"),
        ("itertools", "迭代器瑞士军刀，chain/groupby/product 省掉无数 for 循环"),
        ("dataclass", "Python 3.7+ 的数据容器，省掉 __init__ 样板代码"),
        ("loguru", "替代 print 调试，日志即插即用，比 logging 简单100倍"),
        ("httpx", "现代 HTTP 客户端，支持 async，比 requests 更适合新项目"),
        ("typer", "把函数秒变 CLI 工具，基于类型注解自动生成命令行接口"),
        ("polars", "比 pandas 更快的大数据 DataFrame 库，Rust 写的"),
        ("ruff", "超快的 Python linter+formatter，一个工具替代 flake8+black+isort"),
    ],
    "命令行工具": [
        ("jq", "命令行 JSON 处理器，API 返回数据秒解析"),
        ("bat", "带语法高亮和行号的 cat 替代品，看代码更舒服"),
        ("fd", "比 find 快 10 倍的文件搜索，语法更直观"),
        ("fzf", "模糊搜索神器，Ctrl+R 增强、文件搜索、Git 分支切换都用它"),
        ("ripgrep (rg)", "比 grep 快一个数量级的代码搜索，自动忽略 .gitignore"),
        ("tmux", "终端复用器，SSH 断开后任务继续跑，分屏不新开窗口"),
        ("zoxide", "更聪明的 cd，按使用频率跳转，不再记长路径"),
        ("delta", "Git diff 美化器，对比视图像 IDE 一样清晰"),
        ("tldr", "比 man 更友好的命令帮助，直接给常用示例"),
        ("ncdu", "终端磁盘空间分析，快速找到占用大户"),
    ],
    "VS Code技巧": [
        ("多光标编辑", "Cmd+D 选中下一个相同词，同时编辑多处"),
        ("命令面板", "Cmd+Shift+P 打开，所有操作不用鼠标"),
        ("GitLens 扩展", "行级 Git blame，谁改的、什么时候、为什么"),
        ("Jupyter 内联", "VS Code 原生支持 .ipynb，变量浏览器 + 交互绘图"),
        ("代码片段(Snippets)", "自定义快捷模板，输入触发词自动展开代码块"),
        ("远程开发(Remote SSH)", "在本地 VS Code 编辑远程服务器上的代码"),
    ],
    "效率技巧": [
        ("Shell 别名", "alias ll='ls -lah' 之类的快捷方式，省掉重复输入"),
        ("Git stash", "临时保存修改切分支，git stash pop 恢复"),
        ("Python 虚拟环境", "venv/conda 隔离依赖，每个项目独立环境不冲突"),
        ("pip freeze > requirements.txt", "一键导出当前环境所有依赖"),
        ("Jupyter 魔法命令", "%timeit 测性能、%%writefile 写文件、%history 查历史"),
        ("Mac Spotlight 计算器", "Cmd+Space 直接输入算式，不需要打开计算器 App"),
        ("浏览器 DevTools", "F12 网络面板看 API 请求，复制为 cURL 直接调试"),
        ("Markdown 图表", "Mermaid 语法在 GitHub Markdown 里画流程图/时序图"),
    ],
}

# 展平
FLAT_TOOLS = []
for cat, items in TOOLS.items():
    for name, desc in items:
        FLAT_TOOLS.append((cat, name, desc))


def get_today_tool():
    """按日期索引选取，跳过今日已推送的"""
    try:
        from archive import get_today_tools
        done = get_today_tools()
    except ImportError:
        done = []

    base = datetime.now(KL_TZ).toordinal()
    for offset in range(len(FLAT_TOOLS)):
        idx = (base + offset) % len(FLAT_TOOLS)
        category, name, desc = FLAT_TOOLS[idx]
        if name not in done:
            return (category, name, desc)
    return FLAT_TOOLS[base % len(FLAT_TOOLS)]


def call_deepseek(category, name, description):
    today_str = datetime.now(KL_TZ).strftime("%Y年%m月%d日")

    system_prompt = """你是为数据科学研究生推荐实用工具的专家。
受众：马来亚大学数据科学硕士，非CS本科，用 Mac，主要写 Python。

## 要求
1. 简洁实用，突出"这个工具解决什么痛点"
2. 给一个马上能用的命令/代码示例
3. 如果和常见工具有对比，一句话说明优势

## 输出格式（严格）
🔧 每日工具 — {date}

┏━━━━━━━━━━━━━━━━━━━━━━
┃ 今日推荐：{name}
┃ 类别：{category}
┗━━━━━━━━━━━━━━━━━━━━━━

🎯 解决什么痛点
[一句话]

⚡ 快速上手
[安装命令或使用方法，1-3行代码/命令]

💪 为什么比默认方式好
[一句话对比，不超过50字]

🧪 数据科学场景
[这个工具在你日常中最实用的场景]
"""

    user_prompt = f"请介绍工具：{name}（{category}），它的核心功能是：{description}"

    payload = {
        "model": "deepseek-chat",
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system_prompt.replace("{date}", today_str).replace("{name}", name).replace("{category}", category)},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 1536,
    }
    try:
        resp = requests.post(
            DEEPSEEK_API,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json=payload, timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", "?")
        print(f"  DeepSeek 返回成功，消耗 tokens: {tokens}")
        return content
    except requests.RequestException as e:
        print(f"  ✗ DeepSeek API 调用失败: {e}")
        sys.exit(1)


def push_to_wechat(content, test_mode=False):
    today = datetime.now(KL_TZ).strftime("%Y年%m月%d日")
    prefix = "🧪 [测试] " if test_mode else ""
    title = f"{prefix}🔧 每日工具 — {today}"
    body = {"title": title, "desp": content.replace("\n", "\n\n")}
    try:
        resp = requests.post(SERVERCHAN_API, data=body, timeout=30)
        resp.raise_for_status()
        if resp.json().get("code") == 0:
            print("  ✓ 微信推送成功")
        else:
            print(f"  ✗ Server酱返回错误: {resp.json()}")
            sys.exit(1)
    except requests.RequestException as e:
        print(f"  ✗ 微信推送失败: {e}")
        sys.exit(1)


def main():
    test_mode = "--test" in sys.argv
    now = datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M (UTC+8)")
    print(f"🔧 每日工具任务开始 — {now}")

    category, name, desc = get_today_tool()
    print(f"  今日工具: [{category}] {name}")

    print("\n🤖 生成工具介绍...")
    content = call_deepseek(category, name, desc)

    print("\n📲 推送到微信...")
    push_to_wechat(content, test_mode=test_mode)

    # 归档
    try:
        from archive import save
        save("每日工具", content)
    except ImportError:
        pass

    print("\n✅ 工具卡推送完成")


if __name__ == "__main__":
    main()
