"""GitHub Trending AI/ML 项目每日推送
每天早上8点自动获取 GitHub 热门 AI/机器学习项目，
通过 DeepSeek 智能筛选并生成中文介绍，推送到微信。
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

# AI/ML 研究方向定制的 GitHub 搜索关键词
SEARCH_QUERIES = [
    # 主要：AI/ML 主题
    "https://api.github.com/search/repositories?q=stars:>300+pushed:>14d+topic:machine-learning+topic:deep-learning&sort=stars&order=desc&per_page=15",
    # 补充：LLM/NLP 主题
    "https://api.github.com/search/repositories?q=stars:>200+pushed:>14d+topic:llm+topic:large-language-models&sort=stars&order=desc&per_page=10",
    # 补充：通用 AI 标签
    "https://api.github.com/search/repositories?q=stars:>300+pushed:>14d+topic:artificial-intelligence&sort=stars&order=desc&per_page=10",
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
    system_prompt = """你是一位专门为 AI/机器学习方向研究生服务的开源项目推荐专家。
你的任务是从 GitHub 热门项目中筛选出最有学习价值的项目，生成清晰易懂的中文介绍。

## 筛选规则
1. 优先推荐与大模型(LLM)、深度学习框架、模型训练/推理/部署、AI Agent、RAG、NLP/CV/多模态相关的项目
2. 保留适合研究生学习水平的项目：教程、论文复现、实用工具、前沿模型实现
3. 排除：纯商业产品、已归档项目、无实际代码的awesome-list、面试题仓库
4. 最终保留恰好 10 个项目

## 输出格式（严格遵循，不要添加多余内容）
🌟 项目名称
🔧 技术栈：[编程语言 + 核心框架]
📚 适合人群：[AI研究生/AI初学者/有经验的研究者]
📝 一句话介绍：[通俗中文说明项目做什么，研究生能学什么]
⭐ Star数：[数字]
🔗 [项目链接]

...（共10个）

🎯 今日 Top 3 重点推荐
1. [项目名]：[为什么 AI 研究生应该关注]
2. [项目名]：[为什么 AI 研究生应该关注]
3. [项目名]：[为什么 AI 研究生应该关注]
"""

    payload = {
        "model": "deepseek-chat",
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请分析以下 GitHub 项目数据（JSON 格式），筛选10个最适合 AI/ML 研究生的项目并生成介绍：\n\n{json.dumps(repos, ensure_ascii=False, indent=2)}"},
        ],
        "max_tokens": 4096,
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
