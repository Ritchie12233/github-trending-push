"""GitHub Trending 项目每日推送
每天早上8点自动获取 GitHub 热门项目（数据科学 + AI/ML + CS基础），
通过 DeepSeek 智能筛选并生成中文介绍，推送到微信。

目标用户：马来亚大学数据科学研究生，非CS本科背景，需要同时强化计算机基础。
"""

import os
import json
import sys
import requests
from datetime import datetime, timezone, timedelta

# ── 配置：全部从环境变量读取 ──────────────────────────────
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
SERVERCHAN_SENDKEY = os.environ["SERVERCHAN_SENDKEY"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # 可选，提高 API 限额

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"
SERVERCHAN_API = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"

# 搜索关键词：覆盖 数据科学 + AI/ML + CS 基础 三块
SEARCH_QUERIES = [
    # 数据科学 / 机器学习
    "https://api.github.com/search/repositories?q=stars:>300+pushed:>21d+topic:data-science&sort=stars&order=desc&per_page=15",
    # 大模型 / NLP
    "https://api.github.com/search/repositories?q=stars:>200+pushed:>21d+topic:llm+topic:large-language-models&sort=stars&order=desc&per_page=10",
    # 通用 AI
    "https://api.github.com/search/repositories?q=stars:>300+pushed:>21d+topic:machine-learning&sort=stars&order=desc&per_page=10",
    # Python（数据科学生态核心语言）
    "https://api.github.com/search/repositories?q=stars:>500+pushed:>21d+language:python+topic:data-science&sort=stars&order=desc&per_page=10",
    # CS 基础：算法/数据结构/系统设计（帮助你补计算机基础）
    "https://api.github.com/search/repositories?q=stars:>500+pushed:>90d+topic:computer-science+topic:algorithms&sort=stars&order=desc&per_page=10",
    # 学习资源类
    "https://api.github.com/search/repositories?q=stars:>500+pushed:>90d+topic:awesome+topic:data-science&sort=stars&order=desc&per_page=5",
]

HEADERS = {"User-Agent": "github-trending-push-bot/1.0"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


# ── 第一步：获取 GitHub 项目 ──────────────────────────────
def fetch_github_repos():
    """合并多个搜索查询的结果，去重后返回"""
    all_repos = {}
    for url in SEARCH_QUERIES:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            for item in items:
                rid = item["id"]
                if rid not in all_repos:
                    all_repos[rid] = {
                        "name": item["full_name"],
                        "html_url": item["html_url"],
                        "description": item.get("description", "无描述"),
                        "stars": item["stargazers_count"],
                        "language": item.get("language", "未知"),
                        "topics": item.get("topics", []),
                        "forks": item["forks_count"],
                        "open_issues": item["open_issues_count"],
                        "pushed_at": item["pushed_at"],
                        "created_at": item["created_at"],
                    }
            print(f"  ✓ {url.split('?')[1][:60]}... → {len(items)} 个")
        except requests.RequestException as e:
            print(f"  ✗ 请求失败: {e}")
            continue

    repos = sorted(all_repos.values(), key=lambda r: r["stars"], reverse=True)
    print(f"  去重后共 {len(repos)} 个项目")
    return repos


# ── 第二步：DeepSeek 智能筛选 ─────────────────────────────
def call_deepseek(repos):
    """调用 DeepSeek API 筛选项目并生成中文介绍"""
    system_prompt = """你是一位专门为数据科学研究生服务的 GitHub 开源项目推荐专家。
你的受众是马来亚大学数据科学硕士生，本科非计算机专业，正在同步补充计算机基础知识。

## 你的受众画像
- 数据科学方向：机器学习、统计分析、数据可视化、大数据处理
- 已掌握：Python 基础、pandas/sklearn 等常用库、基本数学统计知识
- 正在学习：算法与数据结构、系统设计、Linux/命令行、数据库原理、分布式系统基础
- 兴趣前沿：LLM 大模型应用、RAG、AI Agent、MCP 协议、模型部署

## 筛选规则（重要！）
每次推送必须同时覆盖三大板块，比例大致为 6:2:2：
1. **数据科学与 AI（约占6个）**：ML/DL框架、LLM应用、RAG、模型训练与部署、数据分析工具、可视化
2. **计算机基础入门（约占2个）**：算法可视化、数据结构教程、Linux命令、Git学习、数据库基础、计算机网络图解——必须是适合非CS背景入门的内容
3. **Python工程与工具（约占2个）**：Python进阶、Web框架（FastAPI/Flask）、Docker入门、命令行工具、生产力工具

## 筛选要求
- 优先推荐有中文文档或教程的项目
- 入门项目标注"适合非CS背景"
- 避免：纯底层系统项目（如Linux内核、编译器等，受众暂时用不上）、纯前端项目
- 排除：已归档、无实际代码、纯商业、面试题库
- 每个项目的"一句话介绍"必须说明：做什么 + 研究生能学到什么具体技能

## 输出格式（严格遵循）
🌟 项目名称
🔧 技术栈：[语言 + 框架]
📚 适合人群：[数据科学研究生 / 非CS入门 / 有经验者]
📝 一句话介绍：[做什么 + 学到什么]
⭐ Star数：[数字]
🔗 [项目链接]

...（共10个，按板块分组，每组前加小标题）

🎯 今日 Top 3 重点推荐
1. [项目名]：[为什么数据科学研究生应该关注]
2. [项目名]：[为什么数据科学研究生应该关注]
3. [项目名]：[为什么数据科学研究生应该关注]

💡 给非CS背景研究生的学习建议（2-3句话，结合今日推荐给出具体可操作的建议）
"""

    payload = {
        "model": "deepseek-chat",
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请分析以下 GitHub 项目数据（JSON 格式），为马来亚大学数据科学研究生（非CS本科背景）筛选10个项目。严格按 数据科学+AI(6个)、计算机基础(2个)、Python工程(2个) 的比例分配：\n\n{json.dumps(repos, ensure_ascii=False, indent=2)}"},
        ],
        "max_tokens": 5120,
    }

    try:
        resp = requests.post(
            DEEPSEEK_API,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        tokens_used = data.get("usage", {}).get("total_tokens", "未知")
        print(f"  DeepSeek 返回成功，消耗 tokens: {tokens_used}")
        return content
    except requests.RequestException as e:
        print(f"  ✗ DeepSeek API 调用失败: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"    响应体: {e.response.text[:500]}")
        sys.exit(1)


# ── 第三步：推送到微信 ────────────────────────────────────
def push_to_wechat(content, test_mode=False):
    """通过 Server酱 推送到微信"""
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).strftime("%Y年%m月%d日")
    prefix = "🧪 [测试] " if test_mode else ""
    title = f"{prefix}📦 GitHub AI/ML 热门项目推荐 — {today}"

    # Server酱 Markdown 格式
    body = {
        "title": title,
        "desp": content.replace("\n", "\n\n"),  # Server酱需要双换行
    }

    try:
        resp = requests.post(SERVERCHAN_API, data=body, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 0:
            print(f"  ✓ 微信推送成功")
        else:
            print(f"  ✗ Server酱返回错误: {result}")
            sys.exit(1)
    except requests.RequestException as e:
        print(f"  ✗ 微信推送失败: {e}")
        sys.exit(1)


# ── 主流程 ────────────────────────────────────────────────
def main():
    test_mode = "--test" in sys.argv
    if test_mode:
        print("⚠️  测试模式\n")

    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M (UTC+8)")
    print(f"🚀 GitHub Trending 推送任务开始 — {now}\n")

    # Step 1: 获取项目
    print("📡 第一步：获取 GitHub AI/ML 热门项目...")
    repos = fetch_github_repos()
    if len(repos) < 5:
        print(f"  ⚠️ 项目数量不足 ({len(repos)})，任务终止")
        sys.exit(1)

    # Step 2: AI 筛选
    print("\n🤖 第二步：DeepSeek 智能筛选...")
    ai_content = call_deepseek(repos)

    # Step 3: 推送
    print("\n📲 第三步：推送到微信...")
    push_to_wechat(ai_content, test_mode=test_mode)

    print(f"\n✅ 任务完成 — {datetime.now(tz).strftime('%Y-%m-%d %H:%M (UTC+8)')}")


if __name__ == "__main__":
    main()
