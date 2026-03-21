"""
新浪电商新闻爬虫 (Sina E-commerce News Crawler)
职责：搜索新浪新闻 → 抓取当天电商相关新闻 → 输出早报格式

依赖: playwright
用法:
  python3 sina_news_crawler.py
  python3 sina_news_crawler.py --keywords "阿里,京东,拼多多" --output /tmp
"""

import json, time, re, os, argparse, sys
from datetime import datetime, date, timedelta
sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/skills/shared"))
from browser import new_browser_context

# 默认电商关键词列表
DEFAULT_KEYWORDS = [
    "阿里巴巴", "淘宝", "天猫",
    "京东",
    "拼多多",
    "抖音电商",
    "快手电商",
    "美团",
    "得物",
    "唯品会",
]

SINA_SEARCH_URL = "https://search.sina.com.cn/search?q={keyword}&tp=news&sort=0&page=1&size=10&from=search_result"

TODAY = date.today()
TODAY_STR = TODAY.strftime("%Y-%m-%d")

WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# 时间行正则
TIME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?|\d+分钟前|\d+小时前|刚刚|今天|今日)$"
)
# 来源行特征
SOURCE_RE = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9·（）\-]{2,20}$")

# 噪音标题黑名单（导航、热榜等）
NAV_NOISE = {
    "搜 索", "综合", "新闻", "图集", "视频", "相关度", "时间", "高级搜索",
    "新浪热榜", "找到", "1", "2", "3", "4", "5", "10 / page", "Go to",
}

# 噪音内容过滤词（与电商无关的无效结果）
NOISE_KEYWORDS = [
    "马拉松", "音乐", "噪音地图", "文旅", "医院", "寺街", "股东会", "拼豆",
    "招聘", "气象", "天气", "体育", "赛车", "赛跑", "ESports", "JDG", "AG",
    "野生动物", "医疗", "学历", "艺术学院", "画展", "文创",
    "台球", "世锦赛", "球台", "博物馆", "格力电器", "专利",
    "睡眠", "食物", "健康指南", "美食", "赛事", "赞助",
    "跑步", "跑者", "迁马", "迁安", "宿迁马",
    "春晚", "演唱会", "综艺", "电影", "电视",
]

# 电商相关白名单关键词（标题含其一才保留）
ECOMMERCE_WHITELIST = [
    "电商", "淘宝", "天猫", "京东", "拼多多", "抖音", "快手",
    "美团", "得物", "唯品会", "阿里", "蒋凡", "刘强东",
    "外卖", "闪购", "即时零售", "网购", "直播", "带货",
    "平台", "商家", "商户", "旗舰店", "大促", "618", "双11",
    "补贴", "优惠券", "流量", "GMV", "用户增长", "活跃买家",
    "跨境", "出海", "供应链", "物流", "快递", "仓储",
    "消费", "购物", "零售", "电子商务", "网红", "博主",
    "入驻", "开店", "闭店", "营收", "财报", "增长",
]


def is_today(date_str: str) -> bool:
    if not date_str:
        return True
    relative = ["分钟前", "小时前", "刚刚", "今天", "今日"]
    for p in relative:
        if p in date_str:
            return True
    today_strs = [
        TODAY.strftime("%Y-%m-%d"),
        TODAY.strftime("%Y年%m月%d日"),
        TODAY.strftime("%m月%d日"),
    ]
    return any(s in date_str for s in today_strs)


def is_relevant(title: str, summary: str) -> bool:
    """过滤与电商无关的噪音新闻（双重过滤：黑名单 + 白名单）"""
    text = title + summary
    # 黑名单：含噪音词直接排除
    for noise in NOISE_KEYWORDS:
        if noise in text:
            return False
    # 白名单：标题或摘要必须含至少一个电商词
    for kw in ECOMMERCE_WHITELIST:
        if kw in text:
            return True
    return False


def parse_news_from_text(body_text: str, keyword: str) -> list:
    """
    新浪搜索 inner_text 格式（每条新闻结构）：
    [标题行]
    [摘要行（可选，含 · 或较长）]
    [来源行]
    [时间行]
    策略：找时间行，向前回溯标题/摘要/来源。
    """
    lines = [l.strip() for l in body_text.split("\n") if l.strip()]
    results = []

    for i, line in enumerate(lines):
        if not TIME_RE.match(line):
            continue
        date_str = line
        if not is_today(date_str):
            continue

        source = ""
        title = ""
        summary = ""

        if i >= 1 and SOURCE_RE.match(lines[i - 1]):
            source = lines[i - 1]
            if i >= 2:
                prev2 = lines[i - 2]
                if len(prev2) > 25 or "·" in prev2:
                    summary = prev2
                    title = lines[i - 3] if i >= 3 else ""
                else:
                    title = prev2
        else:
            continue

        if not title or len(title) < 5 or title in NAV_NOISE:
            continue
        if not is_relevant(title, summary):
            continue

        results.append({
            "keyword": keyword,
            "title": title,
            "url": "",
            "summary": summary[:300] if summary else "",
            "source": source,
            "date": date_str,
        })

    return results


def crawl_keyword(page, keyword: str) -> list:
    url = SINA_SEARCH_URL.format(keyword=keyword)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        link_map: dict[str, str] = {}
        try:
            anchors = page.query_selector_all("a[href]")
            for a in anchors:
                href = a.get_attribute("href") or ""
                text = (a.inner_text() or "").strip()
                if href.startswith("http") and 5 < len(text) < 100:
                    link_map[text] = href
        except Exception:
            pass

        body_text = page.inner_text("body")
        results = parse_news_from_text(body_text, keyword)

        for item in results:
            if item["title"] in link_map:
                item["url"] = link_map[item["title"]]

        return results

    except Exception as e:
        print(f"[WARN] 关键词「{keyword}」抓取失败: {e}")
        return []


def crawl_all(keywords: list, output_dir: str = "/tmp") -> dict:
    output_path = os.path.join(output_dir, f"miyuan_news_{TODAY_STR}.json")
    all_news = []
    seen_titles: set[str] = set()

    with new_browser_context("sina_news") as (ctx, page):
        print(f"[INFO] 开始抓取，共 {len(keywords)} 个关键词...")
        for kw in keywords:
            print(f"[INFO] 搜索: {kw}")
            items = crawl_keyword(page, kw)
            for item in items:
                t = item["title"]
                if t and t not in seen_titles:
                    seen_titles.add(t)
                    all_news.append(item)
            print(f"[INFO] 「{kw}」→ 今日新闻 {len(items)} 条")
            time.sleep(1.2)

    result = {
        "date": TODAY_STR,
        "keywords": keywords,
        "total": len(all_news),
        "news": all_news,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[DONE] 保存至: {output_path}，共 {len(all_news)} 条新闻")
    return result


def format_morning_report(data: dict) -> str:
    """
    生成早报格式：
    【每日电商早报】1分钟了解互联网大事
    YYYY年M月D日 星期X
    ———————————————
    【今日热点】
    ◆ 标题
    摘要正文...

    【资讯快览】
    1、简短标题
    2、简短标题
    ...
    """
    news = data["news"]
    if not news:
        return "⚠️ 今日暂无电商相关新闻，请稍后重试。"

    # 日期格式
    d = date.fromisoformat(data["date"])
    weekday = WEEKDAY_CN[d.weekday()]
    date_display = f"{d.year}年{d.month}月{d.day}日 {weekday}"

    lines = []
    lines.append("【每日电商早报】1分钟了解互联网大事")
    lines.append(date_display)
    lines.append("———————————————")
    lines.append("")

    # 热点：挑选有摘要、最具代表性的 1-2 条
    hot_items = [n for n in news if n.get("summary") and len(n["summary"]) > 30]
    quick_items = [n for n in news if n not in hot_items]

    # 若热点不足，从快览里补
    if not hot_items and news:
        hot_items = news[:1]
        quick_items = news[1:]

    # 热点最多 2 条，剩余进快览
    if len(hot_items) > 2:
        quick_items = hot_items[2:] + quick_items
        hot_items = hot_items[:2]

    lines.append("【今日热点】")
    for item in hot_items:
        title = item["title"]
        summary = item.get("summary", "").strip()
        source = item.get("source", "")
        dt = item.get("date", "")
        # 标题行
        lines.append(f"◆{title}")
        # 摘要：清理中间点号前的无关内容
        if "·" in summary:
            summary = summary.split("·", 1)[-1].strip()
        if summary:
            lines.append(summary)
        if source or dt:
            lines.append(f"（{source} {dt}）".strip())
        lines.append("")

    # 快览：简短一行，最多 15 条
    if quick_items:
        lines.append("【资讯快览】")
        for idx, item in enumerate(quick_items[:15], 1):
            title = item["title"].strip()
            lines.append(f"{idx}、{title}")
        lines.append("")

    lines.append("———————————————")
    lines.append(f"数据来源：新浪新闻  |  共 {data['total']} 条")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="新浪电商新闻爬虫")
    parser.add_argument("--keywords", default="",
                        help="关键词列表，逗号分隔。默认使用内置电商关键词")
    parser.add_argument("--output", default="/tmp", help="输出目录")
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else DEFAULT_KEYWORDS

    data = crawl_all(keywords, args.output)
    report = format_morning_report(data)
    print("\n" + report)

    # 同时保存早报文本
    report_path = os.path.join(args.output, f"miyuan_report_{TODAY_STR}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[DONE] 早报已保存: {report_path}")
