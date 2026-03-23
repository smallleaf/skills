"""
公共浏览器启动工具 (Shared Browser Launcher)

支持两种模式：
  1. persistent profile 模式 (new_browser_context)：自己启动 Chromium，Cookie 持久化保存
  2. CDP 模式 (new_cdp_context)：连接 OpenClaw 管理的 Browser（推荐，无需维护 profile）

用法（CDP 模式，优先）:
    from browser import new_cdp_context
    with new_cdp_context() as (browser, page):
        page.goto("https://www.example.com")

用法（profile 模式，兜底）:
    from browser import new_browser_context
    with new_browser_context("baidu") as (browser, page):
        page.goto("https://www.baidu.com")
"""

import os, json, urllib.request
from contextlib import contextmanager

# 所有 profile 统一存放在这里（profile 模式使用）
PROFILES_DIR = os.path.expanduser("~/.openclaw/workspace/.browser_profiles")
CHROME_PATH  = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# OpenClaw Browser 默认 CDP 端口
OPENCLAW_CDP_PORT = 18800


def get_profile_dir(name: str) -> str:
    """获取指定 profile 的持久化目录"""
    path = os.path.join(PROFILES_DIR, name)
    os.makedirs(path, exist_ok=True)
    return path


def get_openclaw_cdp_ws() -> str | None:
    """
    从 OpenClaw Browser 控制服务获取 CDP WebSocket URL。
    返回 ws:// 地址，失败返回 None。
    """
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{OPENCLAW_CDP_PORT}/json/version", timeout=3
        ) as r:
            info = json.loads(r.read())
            return info.get("webSocketDebuggerUrl")
    except Exception:
        return None


@contextmanager
def new_cdp_context(viewport: dict = None):
    """
    连接 OpenClaw 管理的 Browser（CDP 模式）。
    OpenClaw 负责维护 Cookie / profile，无需自己启动浏览器。

    Args:
        viewport: 视口大小，默认 2560x900（宽屏确保蓝湖等横向内容完整）

    Raises:
        RuntimeError: 如果 OpenClaw Browser 未运行
    """
    from playwright.sync_api import sync_playwright

    ws_url = get_openclaw_cdp_ws()
    if not ws_url:
        raise RuntimeError(
            "OpenClaw Browser 未运行，请先执行: openclaw browser start"
        )

    vp = viewport or {"width": 2560, "height": 900}

    print(f"[Browser] CDP 连接: {ws_url[:60]}...", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(ws_url)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_viewport_size(vp)
        try:
            yield browser, page
        finally:
            # CDP 模式不关闭浏览器，只关闭连接
            browser.close()
            print("[Browser] CDP 连接已释放", flush=True)


@contextmanager
def new_browser_context(profile: str = "default", headless: bool = False,
                        viewport: dict = None, locale: str = "zh-CN"):
    """
    启动持久化浏览器上下文（profile 模式），Cookie 自动保存。
    仅在 CDP 模式不可用时使用。

    Args:
        profile:  profile 名称，如 "baidu" / "xueqiu" / "lanhu"
        headless: 是否无头模式（默认 False，显示浏览器窗口）
        viewport: 视口大小，默认 2560x900
        locale:   语言，默认 zh-CN
    """
    from playwright.sync_api import sync_playwright

    profile_dir = get_profile_dir(profile)
    vp = viewport or {"width": 2560, "height": 900}

    print(f"[Browser] Profile: {profile} -> {profile_dir}", flush=True)

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
            print(f"[Browser] Profile '{profile}' Cookie 已自动保存", flush=True)
