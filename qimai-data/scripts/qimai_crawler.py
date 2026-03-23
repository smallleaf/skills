"""
七麦数据爬虫 (Qimai Data Crawler)
职责：打开七麦网站 → 读取今日新上架/下架应用数量及列表
输出：/tmp/qimai_data.json

依赖: playwright
用法: python3 qimai_crawler.py
"""

import json
import time
import re
import os
import random
import sys
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/skills/shared'))
from browser import new_browser_context
from pathlib import Path


def human_delay(min_s=1.0, max_s=3.0):
    time.sleep(random.uniform(min_s, max_s))


def crawl_qimai(output_dir: str = "/tmp"):

    output_path = os.path.join(output_dir, "qimai_data.json")

    result = {
        "updated_at": "",
        "summary": {
            "new_apps": "",       # 新上架数量
            "removed_apps": "",   # 下架数量
            "total_apps": "",     # 应用总数
            "avg_review_days": "" # 平均审核时长
        },
        "new_apps_list": [],      # 新上架应用列表
        "removed_apps_list": [],  # 下架应用列表
    }

    with new_browser_context("qimai") as (ctx, page):
        print("[INFO] 启动持久化浏览器（qimai profile）...")
    七麦的应用列表格式通常是：应用名 -> 开发者 -> 类别 -> 时间
    """
    noise = {
        '应用', '开发者', '类别', '更新时间', '上架时间', '当前状态',
        '近期最高排名', '总榜(免费)', '下载量', '下架', '上架',
        '查看更多', '榜单', '工具', '登录', '注册', '七麦数据',
        '筛选', '排序', 'App Store', '中国区', '显示设置'
    }
    category_keywords = ['游戏', '工具', '教育', '社交', '娱乐', '生活', '健康',
                         '金融', '购物', '效率', '医疗', '旅行', '体育', '美食',
                         '音乐', '摄影', '商务', '新闻', '图书', '导航']

    apps = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # 跳过噪音行
        if line in noise or len(line) < 2 or re.match(r'^[\d\s\-/:.]+$', line):
            i += 1
            continue

        # 识别应用名（长度合理、不是纯英文域名/路径）
        if (4 <= len(line) <= 30
                and not line.startswith("http")
                and not re.match(r'^[A-Za-z\s.]+$', line)
                and line not in noise):

            app = {"name": line, "developer": "", "category": "", "date": ""}

            # 向后看几行补充信息
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j]
                if not app["developer"] and 2 < len(next_line) <= 40 and next_line not in noise:
                    # 判断是否像开发者名
                    if not any(kw in next_line for kw in category_keywords) and not re.match(r'^\d{4}-\d{2}', next_line):
                        app["developer"] = next_line
                elif not app["category"] and any(kw in next_line for kw in category_keywords):
                    app["category"] = next_line
                elif not app["date"] and re.search(r'\d{4}-\d{2}-\d{2}|\d{2}-\d{2}', next_line):
                    app["date"] = next_line

            # 只保留有名称的条目
            if app["name"] and app["name"] not in [a["name"] for a in apps]:
                apps.append(app)

        i += 1

    return apps


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="七麦数据爬虫")
    parser.add_argument("--output", default="/tmp", help="输出目录")
    args = parser.parse_args()

    data = crawl_qimai(args.output)
    print(f"\n=== 七麦数据摘要 ===")
    print(f"更新时间: {data['updated_at']}")
    print(f"新上架: {data['summary']['new_apps']} 个")
    print(f"下架: {data['summary']['removed_apps']} 个")
    print(f"应用总数: {data['summary']['total_apps']}")
    print(f"平均审核: {data['summary']['avg_review_days']}")
    print(f"\n新上架前5条:")
    for a in data['new_apps_list'][:5]:
        print(f"  · {a['name']} | {a['developer']} | {a['category']} | {a['date']}")
    print(f"\n下架前5条:")
    for a in data['removed_apps_list'][:5]:
        print(f"  · {a['name']} | {a['developer']} | {a['category']} | {a['date']}")
