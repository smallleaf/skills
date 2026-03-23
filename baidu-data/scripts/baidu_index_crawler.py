"""
百度指数爬虫 (Baidu Index Crawler)
职责：打开百度指数 → 登录（如需）→ 切换移动端 → 读取指定关键词搜索指数
输出：/tmp/baidu_index_{keyword}.json

依赖: playwright
用法:
  python3 baidu_index_crawler.py --keyword 水印相机
  python3 baidu_index_crawler.py --keyword 水印相机 --cookie "BDUSS=xxx..."
"""

import json, time, re, os, argparse, random, sys
sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/skills/shared"))
from browser import new_browser_context
from pathlib import Path


def human_delay(a=0.8, b=2.0):
    time.sleep(random.uniform(a, b))


def load_cookies(cookie_file: str):
    """从文件加载 cookie"""
    if not os.path.exists(cookie_file):
        return []
    with open(cookie_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cookies(page, cookie_file: str):
    """保存当前 cookie 到文件"""
    cookies = page.context.cookies()
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Cookie 已保存: {cookie_file}")


def crawl_baidu_index(keyword: str, device: str = "移动", output_dir: str = "/tmp",
                      cookie_file: str = None, period: str = "近30天"):
    from playwright.sync_api import sync_playwright

    safe_kw = re.sub(r'[^\w\u4e00-\u9fff]', '_', keyword)
    output_path = os.path.join(output_dir, f"baidu_index_{safe_kw}.json")

    result = {
        "keyword": keyword,
        "device": device,
        "period": period,
        "url": f"https://index.baidu.com/v2/main/index.html#/trend/{keyword}?words={keyword}",
        "search_index": {
            "avg_overall": "",    # 整体日均值
            "avg_mobile": "",     # 移动日均值
            "overall_yoy": "",    # 整体同比
            "overall_mom": "",    # 整体环比
            "mobile_yoy": "",     # 移动同比
            "mobile_mom": "",     # 移动环比
        },
        "trend_data": [],         # 趋势数据点
        "related_words": [],      # 相关词
        "logged_in": False,
        "error": ""
    }

    with new_browser_context("baidu") as (ctx, page):
        print("[INFO] 启动持久化浏览器（baidu profile）...")

        try:
            # ── Step1: 打开首页（让 SPA 完整渲染）────────────────────────
            print("[INFO] 打开百度指数首页...")
            page.goto("https://index.baidu.com/v2/index.html#/",
                      wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)

            # ── Step2: 检测登录状态 ───────────────────────────────────────
            body_text = page.inner_text("body")
            lines_check = [l.strip() for l in body_text.split("\n") if l.strip()]
            need_login = len(lines_check) < 20 and "登录" in body_text

            if need_login:
                print("[WARN] 未登录，尝试引导登录...")
                result["logged_in"] = False
                result["error"] = "需要登录百度账号"
                login_btn = page.query_selector("a:has-text('登录'), .login-btn")
                if login_btn:
                    login_btn.click()
                    time.sleep(3)
                    print("[INFO] 等待用户登录（45秒）...")
                    time.sleep(45)
                body_text = page.inner_text("body")
                if len([l for l in body_text.split("\n") if l.strip()]) > 20:
                    result["logged_in"] = True
                    result["error"] = ""
                else:
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    return result
            else:
                result["logged_in"] = True
                print("[INFO] 已登录")

            # ── Step3: 搜索关键词（比 hash 路由更稳定）──────────────────
            print(f"[INFO] 搜索关键词: {keyword}")
            search_box = page.query_selector("input.search-input, input[placeholder*='关键词']")
            if search_box:
                search_box.click()
                search_box.fill(keyword)
                time.sleep(0.5)
                search_box.press("Enter")
                time.sleep(8)
            else:
                # fallback: 直接跳转 hash URL
                page.goto(f"https://index.baidu.com/v2/main/index.html#/trend/{keyword}?words={keyword}",
                          wait_until="domcontentloaded", timeout=30000)
                time.sleep(8)

            # ── Step4: 切换设备类型 ───────────────────────────────────────
            print(f"[INFO] 切换设备类型为: {device}")
            try:
                clicked = page.evaluate("""() => {
                    const btns = document.querySelectorAll('.veui-button');
                    for (const btn of btns) {
                        const txt = btn.innerText.trim();
                        if (txt === 'PC+移动' || txt === 'PC' || txt === '移动') {
                            btn.click();
                            return 'clicked:' + txt;
                        }
                    }
                    return 'not_found';
                }""")
                print(f"[INFO] 点击下拉: {clicked}")
                human_delay(1, 1.5)

                clicked2 = page.evaluate(f"""(device) => {{
                    const items = document.querySelectorAll('.list-item');
                    for (const item of items) {{
                        if (item.innerText.trim() === device) {{
                            item.click();
                            return true;
                        }}
                    }}
                    return false;
                }}""", device)
                if clicked2:
                    print(f"[INFO] 已切换到: {device}")
                    human_delay(3, 4)
            except Exception as e:
                print(f"[WARN] 切换设备失败: {e}")

            # ── 等待数据加载 ─────────────────────────────────────────────
            time.sleep(4)

            # ── 读取搜索指数概览表格 ─────────────────────────────────────
            print("[INFO] 读取搜索指数数据...")
            body_text = page.inner_text("body")

            # 解析概览表格：格式为 "水印相机\t3,010\t2,870\t-28% \t11% \t-27% \t12%"
            lines = [l.strip() for l in body_text.split("\n") if l.strip()]

            for line in lines:
                # 匹配 "关键词\t整体日均\t移动日均\t..." 格式（忽略大小写）
                if keyword.lower() in line.lower() and "\t" in line:
                    parts = [p.strip() for p in line.split("\t")]
                    if len(parts) >= 3:
                        result["search_index"]["avg_overall"] = parts[1] if len(parts) > 1 else ""
                        result["search_index"]["avg_mobile"]  = parts[2] if len(parts) > 2 else ""
                        result["search_index"]["overall_yoy"] = parts[3] if len(parts) > 3 else ""
                        result["search_index"]["overall_mom"] = parts[4] if len(parts) > 4 else ""
                        result["search_index"]["mobile_yoy"]  = parts[5] if len(parts) > 5 else ""
                        result["search_index"]["mobile_mom"]  = parts[6] if len(parts) > 6 else ""
                        print(f"[INFO] 搜索指数: {result['search_index']}")
                        break

            # ── 尝试拦截 API 响应获取趋势数据 ────────────────────────────
            trend_data = []
            api_data = {}

            def handle_response(response):
                if "getindex" in response.url or "trend" in response.url.lower():
                    try:
                        data = response.json()
                        if isinstance(data, dict) and data.get("data"):
                            api_data["trend"] = data
                    except:
                        pass

            page.on("response", handle_response)
            page.reload()
            time.sleep(6)

            if api_data.get("trend"):
                result["trend_data"] = api_data["trend"]

            # ── 提取相关词 ───────────────────────────────────────────────
            try:
                related = page.query_selector_all("[class*='related'] span, [class*='word'] span")
                result["related_words"] = list(set([
                    r.inner_text().strip() for r in related
                    if 2 <= len(r.inner_text().strip()) <= 20
                ]))[:20]
            except:
                pass

            # ── 截图留存 ─────────────────────────────────────────────────
            shot_path = os.path.join(output_dir, f"baidu_index_{safe_kw}.png")
            page.screenshot(path=shot_path, full_page=False)
            result["screenshot"] = shot_path
            print(f"[INFO] 截图: {shot_path}")

            # ── 完整 body 文字 ───────────────────────────────────────────
            result["raw_text"] = [l.strip() for l in page.inner_text("body").split("\n")
                                  if l.strip() and len(l.strip()) > 1]

        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            result["error"] = str(e)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[DONE] 保存至: {output_path}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="百度指数爬虫")
    parser.add_argument("--keyword",  required=True,         help="查询关键词，如：水印相机")
    parser.add_argument("--device",   default="移动",         help="设备类型：移动/PC/PC+移动（默认：移动）")
    parser.add_argument("--period",   default="近30天",       help="时间范围（默认：近30天）")
    parser.add_argument("--output",   default="/tmp",         help="输出目录")
    parser.add_argument("--cookie",   default=os.path.expanduser("~/.openclaw/workspace/.baidu_cookies.json"),
                                                              help="Cookie 文件路径")
    args = parser.parse_args()

    data = crawl_baidu_index(
        keyword=args.keyword,
        device=args.device,
        period=args.period,
        output_dir=args.output,
        cookie_file=args.cookie,
    )

    print(f"\n=== 百度指数摘要 ===")
    print(f"关键词: {data['keyword']} | 设备: {data['device']} | 已登录: {data['logged_in']}")
    print(f"整体日均值: {data['search_index']['avg_overall']}")
    print(f"移动日均值: {data['search_index']['avg_mobile']}")
    print(f"整体同比: {data['search_index']['overall_yoy']}")
    print(f"移动同比: {data['search_index']['mobile_yoy']}")
    if data["error"]:
        print(f"⚠️  错误: {data['error']}")
