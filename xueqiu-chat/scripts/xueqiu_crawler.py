"""
雪球股票讨论爬虫 (Xueqiu Discussion Crawler)
职责：打开雪球股票页面 → 直接读取 HTML → 解析讨论内容
输出：/tmp/xueqiu_{code}.json

依赖: playwright
用法: python3 xueqiu_crawler.py --code SH600026
"""

import json
import time
import argparse
import os
import random
import re
import sys
sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/skills/shared"))
from browser import new_browser_context
from pathlib import Path


def human_delay(min_s=1.0, max_s=3.0):
    time.sleep(random.uniform(min_s, max_s))


def parse_discussions_from_html(html: str) -> list:
    """从 HTML 中提取讨论内容"""
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.texts = []
            self._current = []
            self._skip_tags = {'script', 'style', 'head', 'meta', 'link'}
            self._skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in self._skip_tags:
                self._skip += 1

        def handle_endtag(self, tag):
            if tag in self._skip_tags and self._skip > 0:
                self._skip -= 1

        def handle_data(self, data):
            if self._skip == 0:
                text = data.strip()
                if text:
                    self._current.append(text)

    extractor = TextExtractor()
    extractor.feed(html)
    raw = extractor._current

    # 过滤掉太短、纯数字、UI导航文字的行
    noise = {'转发', '收藏', '评论', '赞', '来自', '展开', '全文', '回复',
             '关注', '粉丝', '关注他', '私信', '举报', '更多', '加载中',
             '登录', '注册', '首页', '行情', '自选', '个股', '市场'}
    results = []
    for t in raw:
        t = t.strip()
        if not t:
            continue
        if len(t) < 5:
            continue
        if t in noise:
            continue
        if re.match(r'^\d+$', t):
            continue
        results.append(t)

    return results


def parse_stock_info_from_html(html: str) -> dict:
    """从 HTML 中提取股票基础信息"""
    info = {"name": "", "price": "", "change": ""}

    # 股票名称
    name_match = re.search(r'<title>([^<]+)</title>', html)
    if name_match:
        info["name"] = name_match.group(1).strip()

    # 尝试从 JSON 数据中提取价格（雪球部分数据内嵌在 JS 变量中）
    price_match = re.search(r'"current":\s*([\d.]+)', html)
    if price_match:
        info["price"] = price_match.group(1)

    chg_match = re.search(r'"percent":\s*(-?[\d.]+)', html)
    if chg_match:
        info["change"] = chg_match.group(1) + "%"

    return info


def merge_into_posts(raw_lines: list) -> list:
    """
    把散列的文本行合并为完整帖子。
    策略：遇到时间戳行（如"30分钟前"、"2小时前"、"昨天"）就开启新帖。
    """
    time_pattern = re.compile(
        r'(\d+分钟前|\d+小时前|昨天|前天|\d{2}-\d{2}|\d{4}-\d{2}-\d{2}|今天\s*\d+:\d+)'
    )

    posts = []
    current = []

    for line in raw_lines:
        if time_pattern.search(line) and current:
            post = " | ".join(current)
            if len(post) > 15:
                posts.append(post)
            current = [line]
        else:
            current.append(line)

    if current:
        post = " | ".join(current)
        if len(post) > 15:
            posts.append(post)

    return posts[:30]


def crawl_xueqiu(code: str, output_dir: str = "/tmp"):

    code = code.upper()
    if code.isdigit():
        code = ("SH" if code.startswith("6") else "SZ") + code

    url = f"https://xueqiu.com/S/{code}"
    output_path = os.path.join(output_dir, f"xueqiu_{code}.json")

    result = {
        "code": code,
        "url": url,
        "stock_info": {},
        "discussions": [],
    }

    with new_browser_context("xueqiu") as (ctx, page):
        print("[INFO] 启动持久化浏览器（xueqiu profile）...")
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {} };
        """)

        try:
            # 先访问首页建立 session
            print("[INFO] 访问雪球首页建立 session...")
            page.goto("https://xueqiu.com", wait_until="domcontentloaded", timeout=30000)
            human_delay(3, 5)
            page.mouse.move(random.randint(200, 800), random.randint(100, 400))
            human_delay(1, 2)

            # 跳转股票页
            print(f"[INFO] 跳转股票页面: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            human_delay(4, 7)

            # 关闭弹窗
            try:
                page.keyboard.press("Escape")
                human_delay(0.5, 1)
            except:
                pass

            # 滚动加载更多内容
            print("[INFO] 滚动加载讨论...")
            for _ in range(4):
                page.evaluate(f"window.scrollBy(0, {random.randint(500, 900)})")
                human_delay(1.5, 2.5)

            # ── 核心：直接读取 HTML ──────────────────────────────────────
            print("[INFO] 读取页面 HTML...")
            html = page.content()
            print(f"[INFO] HTML 大小: {len(html)} 字符")

            # 解析股票信息
            result["stock_info"] = parse_stock_info_from_html(html)

            # 尝试用 inner_text 直接获取结构化文字（更干净）
            print("[INFO] 提取页面文字内容...")
            body_text = page.inner_text("body")
            raw_lines = [l.strip() for l in body_text.split("\n") if l.strip()]

            # 合并为帖子
            posts = merge_into_posts(raw_lines)

            if posts:
                result["discussions"] = posts
                print(f"[INFO] 解析到 {len(posts)} 条讨论")
            else:
                # fallback: 直接用过滤后的行
                filtered = parse_discussions_from_html(html)
                result["discussions"] = filtered[:30]
                print(f"[INFO] fallback 提取 {len(result['discussions'])} 条内容")

        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[DONE] 保存至: {output_path}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="雪球股票讨论爬虫（HTML解析版）")
    parser.add_argument("--code",   required=True,  help="股票代码，如 SH600026")
    parser.add_argument("--output", default="/tmp", help="输出目录")
    args = parser.parse_args()

    data = crawl_xueqiu(args.code, args.output)
    print(f"\n股票: {data['stock_info']}")
    print(f"讨论条数: {len(data['discussions'])}")
    if data["discussions"]:
        print("\n前3条预览:")
        for d in data["discussions"][:3]:
            print(f"  · {d[:100]}")
