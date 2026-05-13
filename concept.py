"""每日概念卡 — 每天中午12点
一个 CS/DS 基础概念，3分钟读完，专为非CS背景设计。
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

# ── 概念库：按板块分类，每天轮换 ──────────────────────────
CONCEPTS = {
    "数据结构与算法": [
        "哈希表（Hash Table）", "链表 vs 数组", "栈与队列",
        "二叉树与二叉搜索树", "图的广度优先搜索(BFS)", "图的深度优先搜索(DFS)",
        "动态规划入门", "递归与分治", "排序算法（快排/归并）",
        "大O表示法与时间复杂度", "堆与优先队列", "前缀树（Trie）",
    ],
    "机器学习基础": [
        "梯度下降直观理解", "过拟合与正则化", "偏差-方差权衡",
        "交叉验证", "特征工程入门", "混淆矩阵与评估指标",
        "决策树与随机森林", "支持向量机(SVM)", "K-Means 聚类",
        "主成分分析(PCA)", "朴素贝叶斯", "集成学习（Bagging/Boosting）",
    ],
    "计算机系统": [
        "内存与缓存", "进程与线程", "什么是 API",
        "RESTful API 设计", "SQL 与 NoSQL", "数据库索引原理",
        "Git 分支与合并", "Docker 是什么", "HTTP 请求与响应",
        "JSON 与序列化", "正则表达式入门", "Linux 文件权限",
    ],
    "数学与统计": [
        "贝叶斯定理", "最大似然估计", "信息熵",
        "协方差与相关性", "中心极限定理", "假设检验",
        "线性代数在 ML 中的应用", "概率分布（正态/泊松/二项）",
        "矩阵乘法直观理解", "梯度与方向导数",
    ],
    "工程实践": [
        "测试驱动开发(TDD)", "CI/CD 流水线", "日志与监控",
        "代码重构", "设计模式入门（单例/工厂）", "并发与并行",
        "缓存策略（Redis）", "消息队列", "负载均衡",
    ],
}

# 展平为有序列表，按板块轮换确保多样性
FLAT_CONCEPTS = []
for category, items in CONCEPTS.items():
    for item in items:
        FLAT_CONCEPTS.append((category, item))


def get_today_concept():
    """按日期索引选取今日概念，确保不重复"""
    idx = datetime.now(KL_TZ).toordinal() % len(FLAT_CONCEPTS)
    return FLAT_CONCEPTS[idx]


def call_deepseek(category, concept):
    """生成概念卡"""
    today_str = datetime.now(KL_TZ).strftime("%Y年%m月%d日")

    system_prompt = """你是为非CS背景研究生讲解计算机/数据科学概念的优秀教师。
你的受众：马来亚大学数据科学硕士生，本科非计算机专业。

## 讲解要求
1. 用生活化的类比开头（比如用图书馆比喻数据库索引）
2. 核心概念用最朴素的语言解释，不用术语解释术语
3. 给出一个数据科学场景中的实际应用
4. 一句话总结（方便记忆）

## 输出格式（严格）
📖 每日概念卡 — {date}

┏━━━━━━━━━━━━━━━━━━━━━━
┃ 今天搞懂：{concept}
┃ 板块：{category}
┗━━━━━━━━━━━━━━━━━━━━━━

💡 通俗理解
[生活化类比，不超过100字]

🧠 核心要点
[3-4个要点，每个一句话]

📊 数据科学中的应用
[这个知识在你日常学习中什么时候会用到，不超过80字]

🔖 一句话记住
[朗朗上口的一句话]

⏱ 阅读时间：约3分钟
"""

    user_prompt = f"请讲解概念：{concept}（属于{category}板块）"

    payload = {
        "model": "deepseek-chat",
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system_prompt.replace("{date}", today_str).replace("{concept}", concept).replace("{category}", category)},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 2048,
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
    title = f"{prefix}📖 每日概念卡 — {today}"
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
    print(f"📖 每日概念卡任务开始 — {now}")

    category, concept = get_today_concept()
    print(f"  今日概念: [{category}] {concept}")

    print("\n🤖 生成概念讲解...")
    content = call_deepseek(category, concept)

    print("\n📲 推送到微信...")
    push_to_wechat(content, test_mode=test_mode)

    # 归档
    try:
        from archive import save
        save("每日概念卡", content)
    except ImportError:
        pass

    print("\n✅ 概念卡推送完成")


if __name__ == "__main__":
    main()
