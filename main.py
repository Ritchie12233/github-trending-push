"""GitHub Trending 项目每日推送
- 周一至周五：5条精选（3 AI/DS + 1 CS基础 + 1 信息茧房打破器）
- 周六：本周深度汇总（10条分层 + 趋势分析）
- 周日：休息，不推送

目标用户：马来亚大学数据科学研究生，非CS本科背景。
"""

import os
import json
import sys
import random
import requests
from datetime import datetime, timezone, timedelta

# ── 配置 ──────────────────────────────────────────────────
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
SERVERCHAN_SENDKEY = os.environ["SERVERCHAN_SENDKEY"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"
SERVERCHAN_API = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
KL_TZ = timezone(timedelta(hours=8))

HEADERS = {"User-Agent": "github-trending-push-bot/1.0"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


# ── 日期工具 ──────────────────────────────────────────────
def get_day_of_week():
    """返回 KL 时区的星期几: 0=周一, 6=周日"""
    return datetime.now(KL_TZ).weekday()


def day_name(d):
    return ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][d]


# ── 搜索参数构建 ──────────────────────────────────────────

def build_weekday_search_params():
    """周一至周五搜索：AI/DS + CS基础 + 随机破圈"""
    today = datetime.now(timezone.utc)
    d7 = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    d14 = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    d30 = (today - timedelta(days=30)).strftime("%Y-%m-%d")

    return [
        # AI/DS 板块（3个来源）
        {"q": f"stars:>300 pushed:>={d7} topic:data-science", "sort": "stars", "order": "desc", "per_page": 10},
        {"q": f"stars:>200 pushed:>={d7} topic:llm", "sort": "stars", "order": "desc", "per_page": 10},
        {"q": f"stars:>300 pushed:>={d14} topic:machine-learning", "sort": "stars", "order": "desc", "per_page": 10},
        # CS 基础
        {"q": f"stars:>200 pushed:>={d30} topic:algorithms", "sort": "stars", "order": "desc", "per_page": 10},
        # Python 工具生态
        {"q": f"stars:>500 pushed:>={d14} language:python topic:data-science", "sort": "stars", "order": "desc", "per_page": 10},
        # 破圈随机池 — 无主题限制，纯看近期热度（提供20个候选）
        {"q": f"stars:>1000 pushed:>={d7}", "sort": "stars", "order": "desc", "per_page": 20},
    ]


def build_saturday_search_params():
    """周六搜索：覆盖一周，更大范围"""
    today = datetime.now(timezone.utc)
    d7 = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    d14 = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    d30 = (today - timedelta(days=30)).strftime("%Y-%m-%d")

    return [
        {"q": f"stars:>300 pushed:>={d7} topic:data-science", "sort": "stars", "order": "desc", "per_page": 15},
        {"q": f"stars:>200 pushed:>={d7} topic:llm", "sort": "stars", "order": "desc", "per_page": 15},
        {"q": f"stars:>300 pushed:>={d14} topic:machine-learning", "sort": "stars", "order": "desc", "per_page": 15},
        {"q": f"stars:>500 pushed:>={d14} language:python topic:data-science", "sort": "stars", "order": "desc", "per_page": 10},
        {"q": f"stars:>200 pushed:>={d30} topic:algorithms", "sort": "stars", "order": "desc", "per_page": 15},
        {"q": f"stars:>500 pushed:>={d14} topic:awesome-list", "sort": "stars", "order": "desc", "per_page": 10},
        # 更泛化的破圈池
        {"q": f"stars:>1000 pushed:>={d7}", "sort": "stars", "order": "desc", "per_page": 25},
    ]


# ── 第一步：获取 GitHub 项目 ──────────────────────────────

def fetch_github_repos(search_params):
    """合并多个搜索查询，去重后按 star 降序返回"""
    all_repos = {}
    base_url = "https://api.github.com/search/repositories"
    for params in search_params:
        desc = params["q"][:60]
        try:
            resp = requests.get(base_url, params=params, headers=HEADERS, timeout=30)
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
                        "pushed_at": item["pushed_at"],
                        "created_at": item["created_at"],
                    }
            print(f"  ✓ {desc}... → {len(items)} 个")
        except requests.RequestException as e:
            print(f"  ✗ 请求失败: {e}")
            continue

    repos = sorted(all_repos.values(), key=lambda r: r["stars"], reverse=True)
    print(f"  去重后共 {len(repos)} 个项目")
    return repos


# ── 第二步：DeepSeek 筛选（工作日版）──────────────────────

def call_deepseek_weekday(repos):
    """5 条精选：3 AI/DS + 1 CS基础 + 1 信息茧房打破器"""

    system_prompt = """你是马来亚大学数据科学研究生的专属 GitHub 项目推荐专家。
受众：非CS本科背景，正在同步补计算机基础，对AI/ML/LLM前沿有浓厚兴趣。

## 推送规则（重要！）
每天精选恰好5个项目，结构固定：
1. **AI/数据科学 / LLM 前沿**（3个）—— 与你研究方向直接相关
2. **计算机基础入门**（1个）—— 算法可视化、Linux/命令行、Git、数据库、网络基础，必须适合非CS背景
3. **信息茧房打破器**（1个）—— 必须是你受众平时不会主动搜索的方向。例如：
   - Rust/Go/Zig 写的开发者工具
   - 游戏引擎/图形学
   - 生物信息/量化金融等交叉学科
   - 设计工具/创意编程
   - 去中心化/P2P/隐私工具
   - 嵌入式/IoT
   - 任何新颖的、非AI/DS/Web的优质项目
   - 排除：纯前端框架、纯商业产品、已过时技术栈

## 筛选要求
- 项目名称用中文简写（3-8字概括核心功能），不要直接写 GitHub 原名称
- 每个项目的「一句话介绍」包含：做什么 + 具体能学到什么技能
- CS基础项目标注「适合非CS背景」
- 破圈项目说明「你为什么会觉得这东西有意思」
- 排除：已归档、无实际代码、面试题库

## 输出格式（严格按此模板）

📅 {date} · 每日 GitHub 精选

📊 今日速览
1. 🤖 [中文简写名] — [12字以内极简描述]（⭐xxk）
2. 🤖 [中文简写名] — [12字以内极简描述]（⭐xxk）
3. 🤖 [中文简写名] — [12字以内极简描述]（⭐xxk）
4. 🏗️ [中文简写名] — [12字以内极简描述]（⭐xxk）
5. 🫧 [中文简写名] — [12字以内极简描述]（⭐xxk）

━━━━━━━━━━━━━━━━━━
🤖 AI/数据科学 / LLM 前沿
━━━━━━━━━━━━━━━━━━

🌟 [中文简写名]（原名：owner/repo）
🔧 技术栈：[语言 + 框架]
📝 [一句话：做什么 + 学到什么]
⭐ Star：[数字]  🔗 [链接]

🌟 [中文简写名]（原名：owner/repo）
🔧 [同上格式]
📝 [同上]
⭐ [同上]  🔗 [链接]

🌟 [中文简写名]（原名：owner/repo）
🔧 [同上格式]
📝 [同上]
⭐ [同上]  🔗 [链接]

━━━━━━━━━━━━━━━━━━
🏗️ 计算机基础入门
━━━━━━━━━━━━━━━━━━

🌟 [中文简写名]（原名：owner/repo）
🔧 [同上格式]
📝 [同上，标注适合非CS背景]
⭐ [同上]  🔗 [链接]

━━━━━━━━━━━━━━━━━━
🫧 信息茧房打破器
━━━━━━━━━━━━━━━━━━

🌟 [中文简写名]（原名：owner/repo）
🔧 [技术栈]
📝 [这是什么 + 为什么你可能会感兴趣]
⭐ [同上]  🔗 [链接]
💬 为什么推荐：[1句话]
"""

    # 读取最近已推荐项目，避免重复
    try:
        from archive import get_recent_github_repos
        recent = get_recent_github_repos(days=5)
        exclusion = f"\n\n⚠️ 以下项目过去5天内已推荐过，今天请务必不要推荐：\n{json.dumps(recent, ensure_ascii=False)}" if recent else ""
    except ImportError:
        exclusion = ""

    today_str = datetime.now(KL_TZ).strftime("%Y年%m月%d日") + " " + day_name(get_day_of_week())
    user_prompt = f"""请为 {today_str} 筛选5个项目（3 AI/DS + 1 CS基础 + 1 破圈）。
项目池如下：
{json.dumps(repos, ensure_ascii=False, indent=2)}{exclusion}"""

    return _call_deepseek_api(system_prompt.replace("{date}", today_str), user_prompt)


# ── 第二步：DeepSeek 筛选（周六汇总版）───────────────────

def call_deepseek_saturday(repos):
    """周六深度汇总：10条分层 + 趋势分析"""

    system_prompt = """你是马来亚大学数据科学研究生的专属 GitHub 项目推荐专家。
周六的任务是对本周热门项目进行深度汇总和分层推荐。

## 分层推荐规则
从本周项目中选出最多10个项目，严格分为三层：

### 第一层：必看 🔥（3个）
本周最重要的项目。标准：
- 技术上有突破性或非常实用
- 与数据科学/AI研究密切相关
- 能让研究生直接用到学习或研究中

### 第二层：可收藏 📌（4个）
值得书签保存，但不急着一周内看完：
- 优质学习资源/教程
- 有潜力的新项目（star增长快但还不够成熟）
- 实用的开发工具/效率提升

### 第三层：新人友好 🌱（3个）
适合非CS背景上手：
- CS基础相关
- 有详细文档/教程
- 门槛低但学到的东西扎实

## 额外要求
- 项目名称用中文简写（3-8字），不要直接写 GitHub 原名称
- 最后附一段「📊 本周趋势观察」（3-4句话，总结本周开源社区的值得关注的动向）
- 附一段「📖 学习建议」（结合本周项目给非CS背景研究生1-2条可操作的建议）

## 输出格式

📅 {date} 周六 · 本周深度汇总

📊 本周总览
🔥 必看（3个）
1. [中文简写名] — [12字以内极简描述]（⭐xxk）
2. [中文简写名] — [12字以内极简描述]（⭐xxk）
3. [中文简写名] — [12字以内极简描述]（⭐xxk）

📌 可收藏（4个）
4. [中文简写名] — [12字以内极简描述]（⭐xxk）
5. [中文简写名] — [12字以内极简描述]（⭐xxk）
6. [中文简写名] — [12字以内极简描述]（⭐xxk）
7. [中文简写名] — [12字以内极简描述]（⭐xxk）

🌱 新人友好（3个）
8. [中文简写名] — [12字以内极简描述]（⭐xxk）
9. [中文简写名] — [12字以内极简描述]（⭐xxk）
10. [中文简写名] — [12字以内极简描述]（⭐xxk）

━━━━━━━━━━━━━━━━━━
🔥 必看（3个）
━━━━━━━━━━━━━━━━━━
[每个项目详细格式同工作日]

━━━━━━━━━━━━━━━━━━
📌 可收藏（4个）
━━━━━━━━━━━━━━━━━━
[同上]

━━━━━━━━━━━━━━━━━━
🌱 新人友好（3个）
━━━━━━━━━━━━━━━━━━
[同上]

📊 本周趋势观察
[3-4句话]

📖 学习建议
[1-2条建议]
"""

    today_str = datetime.now(KL_TZ).strftime("%Y年%m月%d日") + " 周六"
    user_prompt = f"请为本周汇总筛选10个项目并分层。项目池（包含本周热门）：\n\n{json.dumps(repos, ensure_ascii=False, indent=2)}"

    return _call_deepseek_api(system_prompt.replace("{date}", today_str), user_prompt, max_tokens=6144)


# ── 通用 DeepSeek API 调用 ────────────────────────────────

def _call_deepseek_api(system_prompt, user_prompt, max_tokens=4096):
    payload = {
        "model": "deepseek-chat",
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(
            DEEPSEEK_API,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", "?")
        print(f"  DeepSeek 返回成功，消耗 tokens: {tokens}")
        return content
    except requests.RequestException as e:
        print(f"  ✗ DeepSeek API 调用失败: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"    响应体: {e.response.text[:500]}")
        sys.exit(1)


# ── 第三步：推送到微信 ────────────────────────────────────

def push_to_wechat(content, test_mode=False):
    """通过 Server酱 推送到微信"""
    today = datetime.now(KL_TZ).strftime("%Y年%m月%d日")
    prefix = "🧪 [测试] " if test_mode else ""
    title = f"{prefix}📦 GitHub 项目推荐 — {today}"

    # Server酱 body
    body = {"title": title, "desp": content.replace("\n", "\n\n")}

    try:
        resp = requests.post(SERVERCHAN_API, data=body, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 0:
            print("  ✓ 微信推送成功")
        else:
            print(f"  ✗ Server酱返回错误: {result}")
            sys.exit(1)
    except requests.RequestException as e:
        print(f"  ✗ 微信推送失败: {e}")
        sys.exit(1)


# ── 主流程 ────────────────────────────────────────────────

def main():
    test_mode = "--test" in sys.argv
    weekday = get_day_of_week()
    dn = day_name(weekday)

    tz_label = datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M (UTC+8)")
    print(f"🚀 GitHub Trending 推送任务 — {dn} {tz_label}")

    # ── 周日：休息 ──────────────────────────────────────
    if weekday == 6:
        print("🌴 今天是周日，休息不推送。明天见！")
        return

    # ── 周六：深度汇总 ──────────────────────────────────
    if weekday == 5:
        print(f"\n📊 {dn} 模式：本周深度汇总（10条分层）")
        print("\n📡 第一步：获取本周热门项目...")
        repos = fetch_github_repos(build_saturday_search_params())
        if len(repos) < 10:
            print(f"  ⚠️ 项目数量不足 ({len(repos)})，任务终止")
            sys.exit(1)

        print("\n🤖 第二步：DeepSeek 深度汇总...")
        ai_content = call_deepseek_saturday(repos)

        print("\n📲 第三步：推送到微信...")
        push_to_wechat(ai_content, test_mode=test_mode)
        print("\n📁 归档...")
        try:
            from archive import save
            save("本周汇总", ai_content)
        except ImportError:
            pass
        print(f"\n✅ {dn}汇总推送完成")
        return

    # ── 周一至周五：5条精选 ─────────────────────────────
    print(f"\n📋 {dn} 模式：5条精选（3 AI/DS + 1 CS基础 + 1 破圈）")
    print("\n📡 第一步：获取热门项目...")
    repos = fetch_github_repos(build_weekday_search_params())
    if len(repos) < 8:
        print(f"  ⚠️ 项目数量不足 ({len(repos)})，任务终止")
        sys.exit(1)

    print("\n🤖 第二步：DeepSeek 精选筛选...")
    ai_content = call_deepseek_weekday(repos)

    print("\n📲 第三步：推送到微信...")
    push_to_wechat(ai_content, test_mode=test_mode)
    print("\n📁 归档...")
    try:
        from archive import save
        save("GitHub精选", ai_content)
    except ImportError:
        pass
    print(f"\n✅ {dn}推送完成")


if __name__ == "__main__":
    main()
