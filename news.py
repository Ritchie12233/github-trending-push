"""新闻简报每日推送
- 早报 7:27 AM：昨夜今晨重要新闻
- 晚报 9:27 PM：今日要闻回顾

覆盖国际政治、战争冲突、科技AI、经济、科学、亚洲 六大板块，
通过 DeepSeek 筛选分类，生成中文简报推送到微信。
"""

import os
import sys
import json
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree

# ── 配置 ──────────────────────────────────────────────────
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
SERVERCHAN_SENDKEY = os.environ["SERVERCHAN_SENDKEY"]

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"
SERVERCHAN_API = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
KL_TZ = timezone(timedelta(hours=8))

# ── RSS 源：覆盖六大板块 ──────────────────────────────────
RSS_FEEDS = {
    "国际/政治": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.theguardian.com/world/rss",
        "https://feeds.npr.org/1001/rss.xml",
    ],
    "冲突/安全": [
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",  # BBC 也覆盖冲突新闻
    ],
    "科技/AI": [
        "https://hnrss.org/frontpage?count=15",
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://feeds.arstechnica.com/arstechnica/index",
    ],
    "经济/商业": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ],
    "科学/研究": [
        "https://www.sciencedaily.com/rss/all.xml",
    ],
    "亚洲/东南亚": [
        "https://www.theguardian.com/world/asia-pacific/rss",
    ],
}

HEADERS = {"User-Agent": "news-briefing-bot/1.0"}


# ── RSS 抓取 ──────────────────────────────────────────────

def fetch_rss_articles():
    """抓取所有 RSS 源，返回去重后的文章列表"""
    seen = set()
    articles = []

    for category, urls in RSS_FEEDS.items():
        for url in urls:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=20)
                resp.raise_for_status()
                root = ElementTree.fromstring(resp.content)

                # RSS 2.0: <channel> → <item>*
                # Atom: <feed> → <entry>*
                ns = {"atom": "http://www.w3.org/2005/Atom"}

                items = root.findall(".//item")
                if not items:
                    items = root.findall(".//atom:entry", ns)

                count = 0
                for item in items:
                    # 提取标题
                    title = _find_text(item, "title", ns)
                    if not title:
                        continue
                    title = title.strip()

                    # 提取链接
                    link = _find_text(item, "link", ns)
                    if not link:
                        link_elem = item.find("link")
                        if link_elem is not None:
                            link = link_elem.text or link_elem.get("href", "")

                    # 去重：标题 hash
                    h = hashlib.md5(title.lower().encode()).hexdigest()
                    if h in seen:
                        continue
                    seen.add(h)

                    # 提取摘要
                    desc = _find_text(item, "description", ns) or ""
                    # 清理 HTML 标签
                    desc = _strip_html(desc)[:300]

                    articles.append({
                        "title": title,
                        "link": link or "",
                        "summary": desc,
                        "source": url.split("/")[2],
                        "category": category,
                    })
                    count += 1

                print(f"  ✓ {category}: {url.split('/')[2]} → {count} 篇")
            except Exception as e:
                print(f"  ✗ {url.split('/')[2]}: {e}")
                continue

    print(f"  去重后共 {len(articles)} 篇文章")
    return articles


def _find_text(element, tag, ns):
    """在 RSS/Atom 中查找文本"""
    # 尝试直接子元素
    child = element.find(tag)
    if child is not None and child.text:
        return child.text
    # 尝试 Atom 命名空间
    child = element.find(f"atom:{tag}", ns)
    if child is not None and child.text:
        return child.text
    # 尝试子元素的子元素
    for c in element:
        if c.tag.endswith(tag) and c.text:
            return c.text
    return None


def _strip_html(text):
    """移除 HTML 标签"""
    import re
    return re.sub(r"<[^>]+>", "", text)


# ── DeepSeek 新闻筛选 ─────────────────────────────────────

def call_deepseek_news(articles, is_morning):
    """调用 DeepSeek 筛选分类，生成中文新闻简报"""
    period = "早报" if is_morning else "晚报"
    time_desc = "昨夜今晨" if is_morning else "今日全天"
    today_str = datetime.now(KL_TZ).strftime("%Y年%m月%d日") + (" 早" if is_morning else " 晚")

    system_prompt = f"""你是马来亚大学数据科学研究生的专属新闻简报编辑。
受众：在马来西亚留学的中国研究生，对国际政治、战争冲突、科技AI、经济、科学都有浓厚兴趣。

## 任务
从原始新闻池中筛选出 {time_desc} 最重要、最相关的约20条新闻，
用中文生成简练的新闻简报。

## 筛选与分类规则
新闻按以下六大板块分类，每个板块2-5条：

1. 🌏 **国际/政治** — 大国博弈、重要外交、选举、政策变动
2. ⚔️ **冲突/安全** — 战争进展、地区冲突、恐怖主义、人道危机
3. 💻 **科技/AI** — 重大技术突破、AI行业动态、监管政策
4. 📊 **经济/商业** — 市场动向、贸易政策、重要企业新闻
5. 🔬 **科学/研究** — 重要研究发现、医学进展、环境科学
6. 🌐 **亚洲/东南亚** — 中国、马来西亚、东盟相关新闻

## 筛选要求
- 优先：对研究生群体有实际影响的新闻（签证政策、留学政策、科技监管等）
- 保留：重大国际事件，即使与科技无关
- 科技板块：不要全是AI新闻，也要关注网络安全、半导体、能源技术等
- 每条新闻写成一句话中文摘要（30-50字），保持原意、不夸张
- 新闻数量可以略少于20条，但绝不能为了凑数塞入不重要的内容
- 如果某个板块今天确实没有重要新闻，可以标「今日无重大新闻」

## 输出格式
📰 {period} — {today_str}

📊 今日概览
[2句话概括今天最值得关注的趋势或事件]

🌏 国际/政治（X条）
1. [一句话中文摘要]
   🔗 [原文链接]
2. ...

⚔️ 冲突/安全（X条）
1. ...

💻 科技/AI（X条）
1. ...

📊 经济/商业（X条）
1. ...

🔬 科学/研究（X条）
1. ...

🌐 亚洲/东南亚（X条）
1. ...

📌 与你相关
[1-2条对马来西亚中国留学生/数据科学研究生可能有直接影响的新闻或提醒]
"""

    user_prompt = f"请为 {today_str} 筛选并生成新闻简报。原始新闻池（英文为主）：\n\n{json.dumps(articles, ensure_ascii=False, indent=2)}"

    return _call_deepseek(system_prompt, user_prompt, max_tokens=5120)


def _call_deepseek(system_prompt, user_prompt, max_tokens=4096):
    payload = {
        "model": "deepseek-chat",
        "temperature": 0.2,  # 新闻要准确，降低随机性
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


# ── 推送到微信 ────────────────────────────────────────────

def push_to_wechat(content, test_mode=False, is_morning=True):
    today = datetime.now(KL_TZ).strftime("%Y年%m月%d日")
    prefix = "🧪 [测试] " if test_mode else ""
    period = "早报" if is_morning else "晚报"
    title = f"{prefix}📰 新闻{period} — {today}"

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
    # 根据当前 KL 时间判断早晚报：7am 附近 → 早报，9pm 附近 → 晚报
    now_kl = datetime.now(KL_TZ)
    is_morning = now_kl.hour < 14  # 下午2点前 → 早报模式

    period = "早报" if is_morning else "晚报"
    tz_label = now_kl.strftime("%Y-%m-%d %H:%M (UTC+8)")
    print(f"📰 新闻{period}任务开始 — {tz_label}\n")

    # Step 1: 抓取 RSS
    print("📡 第一步：抓取新闻 RSS 源...")
    articles = fetch_rss_articles()
    if len(articles) < 15:
        print(f"  ⚠️ 文章数量不足 ({len(articles)})，继续但质量可能下降")

    # Step 2: DeepSeek 筛选
    print(f"\n🤖 第二步：DeepSeek 生成中文{period}...")
    ai_content = call_deepseek_news(articles, is_morning)

    # Step 3: 推送
    print(f"\n📲 第三步：推送到微信...")
    push_to_wechat(ai_content, test_mode=test_mode, is_morning=is_morning)

    # 归档
    print("\n📁 归档...")
    try:
        from archive import save
        cat = "新闻早报" if is_morning else "新闻晚报"
        save(cat, ai_content)
    except ImportError:
        pass

    print(f"\n✅ 新闻{period}推送完成")


if __name__ == "__main__":
    main()
