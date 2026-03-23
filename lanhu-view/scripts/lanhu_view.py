"""
蓝湖原型需求提取爬虫 (lanhu-view)

流程：
  1. 打开蓝湖分享链接，输入密码
  2. 读取侧边栏所有页面列表
  3. 逐项点击 → 等 iframe 渲染 → 截 #lan-mapping-iframe → 保存 PNG
  4. 用 Claude Vision API 分析每张截图，提取页面功能和业务逻辑
  5. 整合输出完整需求文档

依赖: playwright (pip install playwright && playwright install chromium)
"""

import json, time, re, os, sys, argparse, hashlib, base64, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/skills/shared"))
from browser import new_cdp_context, new_browser_context, get_openclaw_cdp_ws

OUTPUT_DIR = "/tmp/lanhu_view"
PROFILE    = "lanhu_view"
SKIP_WORDS = ["弃用", "废弃", "deprecated", "旧版"]

# API 配置（从 openclaw.json 读取）
def load_api_config():
    cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
    with open(cfg_path) as f:
        d = json.load(f)
    provider = d.get("models", {}).get("providers", {}).get("claude-sonnet", {})
    return {
        "api_key":  provider.get("apiKey", ""),
        "base_url": provider.get("baseUrl", "").rstrip("/"),
        "model":    next((m["id"] for m in provider.get("models", [])), "anthropic/claude-sonnet-4.6"),
    }


def screenshot_full_iframe(page, iframe_el, output_path: str) -> int:
    """
    点击 iframe 后用 PageDown 分段滚动截图并垂直拼接，返回截图段数。
    蓝湖 Axure iframe 跨域，无法直接读取内部高度，用 MD5 检测内容变化来判断是否到底。
    """
    MAX_SEGS = 8  # 最多截 8 段，避免无限滚动

    # 先点击 iframe，确保键盘事件作用于其内部
    try:
        iframe_el.click()
        time.sleep(0.3)
    except:
        pass

    segments = []
    prev_hash = ""

    for i in range(MAX_SEGS):
        tmp = output_path + f"_seg{i}.png"
        iframe_el.screenshot(path=tmp)
        cur_hash = hashlib.md5(open(tmp, "rb").read()).hexdigest()

        if cur_hash == prev_hash:
            # 内容没变化，说明已到底
            os.remove(tmp)
            break

        prev_hash = cur_hash
        segments.append(tmp)

        # PageDown 滚动到下一屏
        page.keyboard.press("PageDown")
        time.sleep(0.8)

    if not segments:
        iframe_el.screenshot(path=output_path)
        return 1

    if len(segments) == 1:
        import shutil
        shutil.move(segments[0], output_path)
        return 1

    # 垂直拼接多段截图
    _png_vstack(segments, output_path)
    for f in segments:
        if os.path.exists(f):
            os.remove(f)
    return len(segments)


def _png_vstack(png_files: list, output_path: str):
    """用 subprocess 调用 swift 或系统工具拼接 PNG，不依赖 PIL"""
    # 写一个临时 swift 脚本做图片拼接
    # overlap: PageDown 在蓝湖 iframe(851px) 实际滚动约 651px，重叠约 200px
    swift_code = """
import AppKit
import Foundation
let args   = CommandLine.arguments
let files  = args[1..<(args.count-1)].map { $0 }
let out    = args.last!
let overlap = 200  // 相邻段顶部裁掉的重叠像素数

var reps: [NSBitmapImageRep] = []
var imgs: [NSImage] = []
for path in files {
    if let img = NSImage(contentsOfFile: path),
       let rep = img.representations.first as? NSBitmapImageRep {
        reps.append(rep)
        imgs.append(img)
    }
}
guard !reps.isEmpty else { exit(1) }

let w = reps.map { $0.pixelsWide }.max()!
let totalH = reps.enumerated().reduce(0) { acc, pair in
    let (i, rep) = pair
    return acc + rep.pixelsHigh - (i == 0 ? 0 : overlap)
}

let canvas = NSImage(size: NSSize(width: w, height: totalH))
canvas.lockFocus()
var curY = 0
for (i, rep) in reps.enumerated() {
    let cropTop = i == 0 ? 0 : overlap
    let drawH   = rep.pixelsHigh - cropTop
    let dstY    = totalH - curY - drawH
    imgs[i].draw(in: NSRect(x: 0, y: dstY, width: w, height: drawH),
                 from: NSRect(x: 0, y: 0, width: rep.pixelsWide, height: drawH),
                 operation: .copy, fraction: 1.0)
    curY += drawH
}
canvas.unlockFocus()
if let tiff = canvas.tiffRepresentation,
   let rep  = NSBitmapImageRep(data: tiff),
   let jpeg = rep.representation(using: .jpeg, properties: [.compressionFactor: 0.80]) {
    try! jpeg.write(to: URL(fileURLWithPath: out))
}
"""
    swift_path = output_path + "_stack.swift"
    with open(swift_path, "w") as f:
        f.write(swift_code)
    import subprocess
    cmd = ["swift", swift_path] + png_files + [output_path]
    subprocess.run(cmd, timeout=30)
    os.remove(swift_path)


def vision_analyze(image_path: str, page_name: str, api_cfg: dict) -> str:
    """用 Claude Vision 分析截图，返回页面需求描述"""
    # 发送前检查文件大小，超过 3MB 则用 sips 缩小后再发
    MAX_BYTES = 3 * 1024 * 1024
    send_path = image_path
    tmp_resized = None
    if os.path.getsize(image_path) > MAX_BYTES:
        tmp_resized = image_path + "_resized.jpg"
        import subprocess
        subprocess.run([
            "sips", "--resampleWidth", "1600",
            "-s", "format", "jpeg",
            "-s", "formatOptions", "75",
            image_path, "--out", tmp_resized
        ], capture_output=True)
        if os.path.exists(tmp_resized):
            send_path = tmp_resized

    with open(send_path, "rb") as f:
        img_b64 = base64.standard_b64encode(f.read()).decode()

    if tmp_resized and os.path.exists(tmp_resized):
        os.remove(tmp_resized)

    ext = os.path.splitext(send_path)[-1].lower()
    media_type = "image/png" if ext == ".png" else "image/jpeg"

    prompt = f"""这是蓝湖原型截图，页面名称「{page_name}」，属于「用户荣誉成就/勋章系统」需求。

第一步：只提取与勋章系统直接相关的内容，忽略无关内容，例如：
- 顶部手机状态栏（时间、信号、电量）
- 底部通用导航 Tab（首页/发现/我的等与勋章无关的 Tab）
- 与勋章无关的其他业务模块（收益数据、订单、粉丝数、活动 Banner 等）

第二步：按以下规则提取并输出：
1. 有文字说明/标注 → 原文罗列，不改写
2. 有 UI 状态变化 → 描述每个状态的展示内容和跳转，格式参考：
   「如果用户未获得任何勋章，显示勋章0个，点击跳转至【勋章中心】」
3. 有表单/列表字段 → 逐字段列出名称和示例值
4. 有交互操作 → 写明触发条件和跳转目标

不要总结、归纳、润色，不要添加截图中没有的内容。"""

    payload = {
        "model": api_cfg["model"],
        "max_tokens": 2048,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{img_b64}"}},
                {"type": "text", "text": prompt}
            ]
        }]
    }

    req = urllib.request.Request(
        f"{api_cfg['base_url']}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_cfg['api_key']}",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
            return resp["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        return f"[Vision 分析失败] HTTP {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return f"[Vision 分析失败] {e}"


def crawl(url: str, password: str, output_dir: str = OUTPUT_DIR) -> list:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    shot_dir = os.path.join(output_dir, "screenshots")
    Path(shot_dir).mkdir(exist_ok=True)
    tmp_path = os.path.join(output_dir, "_check.png")
    results  = []

    api_cfg = load_api_config()
    print(f"[INFO] Vision API: {api_cfg['base_url']} / {api_cfg['model']}", flush=True)

    # 优先使用 OpenClaw 管理的 Browser（CDP 模式），否则回退到独立 profile
    use_cdp = get_openclaw_cdp_ws() is not None
    browser_ctx = new_cdp_context({"width": 2560, "height": 900}) if use_cdp \
                  else new_browser_context(PROFILE, viewport={"width": 2560, "height": 900})
    print(f"[INFO] 浏览器模式: {'OpenClaw CDP' if use_cdp else 'Persistent Profile'}", flush=True)

    with browser_ctx as (_browser, page):

        # ── 打开 & 登录 ────────────────────────────────────────────────
        print(f"[INFO] 打开: {url}", flush=True)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        if password:
            el = page.query_selector("input")
            if el:
                el.fill(password)
                time.sleep(0.3)
                btn = page.query_selector("button")
                if btn:
                    btn.click()
                print("[INFO] 密码已提交", flush=True)
                time.sleep(7)

        try:
            page.evaluate("""() => document.querySelectorAll('button').forEach(b => {
                if (['确定','知道了','关闭'].some(t => b.innerText.includes(t))) b.click();
            })""")
        except:
            pass
        time.sleep(2)

        # ── 等侧边栏加载 ───────────────────────────────────────────────
        for _ in range(15):
            n = page.evaluate("() => document.querySelectorAll('.lan-tree-list-item').length")
            if n > 0:
                print(f"[INFO] 侧边栏已加载（{n} 项）", flush=True)
                break
            time.sleep(1)
        time.sleep(1)

        # ── 读侧边栏 ───────────────────────────────────────────────────
        nav_items = page.evaluate(r"""() =>
            Array.from(document.querySelectorAll('.lan-tree-list-item'))
                .map((item, idx) => {
                    const el = item.querySelector('.tree-name');
                    if (!el) return null;
                    const name = el.innerText.trim();
                    if (!name || name.length > 80) return null;
                    const m = (item.className || '').match(/deepD-(\d+)/);
                    return { name, depth: m ? +m[1] : 0, idx };
                }).filter(Boolean)
        """)

        print(f"\n[INFO] 侧边栏 ({len(nav_items)} 项):", flush=True)
        for item in nav_items:
            skip = " ← 跳过" if any(w in item["name"] for w in SKIP_WORDS) else ""
            print(f"  {'  ' * item['depth']}└─ {item['name']}{skip}", flush=True)

        # ── 逐页点击 & 截图 & Vision 分析 ─────────────────────────────
        processed = set()
        prev_md5  = ""

        for nav in nav_items:
            name, depth, idx = nav["name"], nav["depth"], nav["idx"]

            if any(kw in name for kw in SKIP_WORDS):
                print(f"\n[SKIP] {name}", flush=True)
                continue
            if name in processed:
                print(f"\n[SKIP] {name}（重复）", flush=True)
                continue
            processed.add(name)

            pg_num = len(results) + 1
            print(f"\n[PAGE {pg_num}] {'  ' * depth}{name}", flush=True)

            # 点击侧边栏
            try:
                items = page.query_selector_all(".lan-tree-list-item")
                if idx < len(items):
                    items[idx].click()
                else:
                    print(f"  [WARN] 找不到索引 {idx}", flush=True)
                    continue
            except Exception as e:
                print(f"  [WARN] 点击失败: {e}", flush=True)
                continue

            # 等 iframe 内容变化（最多 8s）
            for _ in range(16):
                time.sleep(0.5)
                try:
                    iframe_el = page.query_selector("#lan-mapping-iframe")
                    target = iframe_el or page
                    if iframe_el:
                        iframe_el.screenshot(path=tmp_path)
                    else:
                        page.screenshot(path=tmp_path)
                    cur = hashlib.md5(open(tmp_path, "rb").read()).hexdigest()
                    if cur != prev_md5:
                        prev_md5 = cur
                        break
                except:
                    pass
            time.sleep(1.5)

            # 截图（分段滚动截图后垂直拼接，确保内容不被截断）
            safe  = re.sub(r'[^\w\u4e00-\u9fff]', '_', name)
            p_out = os.path.join(shot_dir, f"{pg_num:02d}_{safe}.jpg")
            iframe_el = page.query_selector("#lan-mapping-iframe")
            try:
                if iframe_el:
                    segments = screenshot_full_iframe(page, iframe_el, p_out)
                    print(f"  截图: {os.path.basename(p_out)} ({segments} 段拼接)", flush=True)
                else:
                    page.screenshot(path=p_out, full_page=True)
                    print(f"  截图: {os.path.basename(p_out)}", flush=True)
            except Exception as e:
                print(f"  [ERROR] 截图失败: {e}", flush=True)
                continue

            # Vision 分析
            print(f"  Vision 分析中...", flush=True)
            analysis = vision_analyze(p_out, name, api_cfg)
            preview = analysis[:80].replace("\n", " ")
            print(f"  ✓ {preview}...", flush=True)

            results.append({
                "name":       name,
                "depth":      depth,
                "screenshot": p_out,
                "analysis":   analysis,
            })

    # 清理 & 保存
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    index = os.path.join(output_dir, "pages.json")
    with open(index, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] {len(results)} 页 → {output_dir}", flush=True)
    return results


def format_requirements(pages: list) -> str:
    """整合 Vision 分析结果，生成需求文档"""
    lines = ["# 用户荣誉成就 — 需求文档\n"]

    for pg in pages:
        depth   = pg.get("depth", 0)
        heading = "#" * (depth + 2)
        lines.append(f"\n{heading} {pg['name']}\n")
        analysis = pg.get("analysis", "（暂无内容）")
        lines.append(analysis)
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="蓝湖原型需求提取（截图 + Claude Vision）")
    ap.add_argument("--url",      required=True)
    ap.add_argument("--password", default="")
    ap.add_argument("--output",   default=OUTPUT_DIR)
    args = ap.parse_args()

    pages = crawl(args.url, args.password, args.output)

    doc = format_requirements(pages)
    doc_path = os.path.join(args.output, "requirements.md")
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(doc)

    print("\n" + "=" * 60)
    print(doc)
    print(f"\n[SAVED] {doc_path}")
