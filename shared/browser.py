"""
公共浏览器启动工具 (Shared Browser Launcher)
使用 launch_persistent_context 持久化 Cookie，一次登录永久有效。

用法:
    from browser import new_browser_context
    with new_browser_context("baidu") as (browser, page):
        page.goto("https://www.baidu.com")
"""

import os
from contextlib import contextmanager

# 所有 profile 统一存放在这里
PROFILES_DIR = os.path.expanduser("~/.openclaw/workspace/.browser_profiles")
CHROME_PATH  = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def get_profile_dir(name: str) -> str:
    """获取指定 profile 的持久化目录"""
    path = os.path.join(PROFILES_DIR, name)
    os.makedirs(path, exist_ok=True)
    return path


@contextmanager
def new_browser_context(profile: str = "default", headless: bool = False,
                        viewport: dict = None, locale: str = "zh-CN"):
    """
    启动持久化浏览器上下文，Cookie 自动保存。

    Args:
        profile:  profile 名称，如 "baidu" / "xueqiu" / "lanhu"
        headless: 是否无头模式（默认 False，显示浏览器窗口）
        viewport: 视口大小，默认 1440x900
        locale:   语言，默认 zh-CN
    """
    from playwright.sync_api import sync_playwright

    profile_dir = get_profile_dir(profile)
    vp = viewport or {"width": 1440, "height": 900}

    print(f"[Browser] Profile: {profile} -> {profile_dir}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
            viewport=vp,
            locale=locale,
            timezone_id="Asia/Shanghai",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            yield ctx, page
        finally:
            ctx.close()
            print(f"[Browser] Profile '{profile}' Cookie 已自动保存")
