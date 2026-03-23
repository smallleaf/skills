"""
云发单 Grafana 健康检查工具 v2
策略：抓取 5min（当前）+ 6h + 24h（历史基准），分四大模块分析：
  1. 核心指标（整体失败率、时延、待推送量）
  2. 消息堆积（ECO / LAKA / LALA_NEW / 发单帝 分服务商）
  3. 第三方接口异常（发单帝 / ECO / Laka 异常统计）
  4. 实时在线用户（各服务商在线量）

依赖: playwright
用法:
  python3 grafana_checker.py
  python3 grafana_checker.py --output /tmp
"""

import sys, os, time, json, re, argparse
from datetime import datetime
sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/skills/shared"))
from browser import new_browser_context

GRAFANA_BASE  = "https://grafana.gzmiyuan.com/d/de9bygt0s2nlsf/yun-fa-dan-tui-song-shu-ju-da-pan?orgId=1"
GRAFANA_LOGIN = "https://grafana.gzmiyuan.com/login"

WINDOWS = [
    ("now", "now-5m",  "now"),
    ("6h",  "now-6h",  "now"),
    ("24h", "now-24h", "now"),
]

# 偏离告警倍数
DEV_WARN = 1.5
DEV_CRIT = 2.5

# 绝对值兜底
ABS = {
    "失败率_warn": 0.05,  "失败率_crit": 0.15,
    "时延_warn":   60,    "时延_crit":   180,    # 秒
    "堆积_warn":   50000, "堆积_crit":   100000,
    "mq_warn":     500,   "mq_crit":     2000,
}


# ─── 数值解析 ────────────────────────────────────────────────────────────────
def parse_num(val: str) -> float:
    if not val:
        return 0.0
    val = val.strip()
    if re.search(r'min$', val, re.I):
        return float(re.sub(r'[^\d.]', '', val)) * 60
    val = re.sub(r'\s*ms$', '', val)   # 毫秒暂不换算，保持原值
    val = re.sub(r'\s*s$',  '', val)
    mul = 1.0
    if re.search(r'[Kk]$', val):
        mul = 1e3;  val = re.sub(r'[Kk\s]+$', '', val)
    elif re.search(r'(Mil|M)$', val, re.I):
        mul = 1e6;  val = re.sub(r'(Mil|M)\s*$', '', val, flags=re.I)
    try:
        return float(val.replace(",", "")) * mul
    except ValueError:
        return 0.0

def fmt_num(n: float) -> str:
    if n >= 1e6: return f"{n/1e6:.2f}M"
    if n >= 1e3: return f"{n/1e3:.1f}K"
    return f"{n:.0f}"

def fmt_sec(s: float) -> str:
    return f"{s/60:.1f}min" if s >= 60 else f"{s:.0f}s"


# ─── Dashboard 解析 ──────────────────────────────────────────────────────────
def parse_dashboard(text: str) -> dict:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    d = {}

    # 1. 核心单值指标
    core_keys = [
        "待推送消息", "待推送用户数量", "待推送时间预估(s)",
        "推送消息失败", "接受消息数量总计", "推送消息总计",
    ]
    for i, line in enumerate(lines):
        if line in core_keys and i + 1 < len(lines):
            d[line] = lines[i + 1]

    # 2. 推送消息堆积数量（按服务商）
    heap = {}
    if "推送消息堆积数量" in lines:
        idx = lines.index("推送消息堆积数量")
        # 结构: Last\nECO\n2.53K\nLAKA\n9\n...总堆积\n23.9K
        i = idx + 2  # 跳过 "Last"
        provider_map = {"ECO": "ECO", "LAKA": "LAKA", "LALA_NEW": "LALA_NEW",
                        "longPool": "longPool", "发单帝": "发单帝"}
        while i < len(lines) and lines[i] != "mq堆积数量":
            name = lines[i]
            if name in provider_map and i + 1 < len(lines):
                heap[name] = lines[i + 1]
                i += 2
            elif name == "总堆积" and i + 1 < len(lines):
                heap["总堆积"] = lines[i + 1]
                i += 2
            else:
                i += 1
    d["堆积_分服务商"] = heap

    # 3. MQ堆积
    for i, line in enumerate(lines):
        if line == "堆积数量" and i + 1 < len(lines):
            d["MQ堆积数量"] = lines[i + 1]
            break

    # 4. 消息推送等待时长（P50/P80/P95）
    wait = {}
    if "消息推送等待时长(消息回调到推送的时间)" in lines:
        idx = lines.index("消息推送等待时长(消息回调到推送的时间)")
        # 结构: Mean\tMin\tMax\n指标名\n值\t值\t值
        i = idx + 2  # 跳过表头行
        while i < len(lines) and lines[i] != "第三方接口QPS":
            label = lines[i]
            if i + 1 < len(lines) and "\t" in lines[i + 1]:
                parts = lines[i + 1].split("\t")
                wait[label] = {"mean": parts[0], "min": parts[1], "max": parts[2] if len(parts) > 2 else ""}
                i += 2
            else:
                i += 1
    d["推送等待时长"] = wait

    # 5. 第三方接口异常统计
    exceptions = {}
    if "第三方接口异常统计" in lines:
        idx = lines.index("第三方接口异常统计")
        i = idx + 2  # 跳过表头 "Last (not null)\tTotal"
        while i < len(lines) and lines[i] not in ("各队列消息堆积用户数量", "待推送用户总和"):
            label = lines[i]
            if i + 1 < len(lines) and "\t" in lines[i + 1]:
                parts = lines[i + 1].split("\t")
                exceptions[label] = {"last": parts[0], "total": parts[1] if len(parts) > 1 else ""}
                i += 2
            else:
                i += 1
    d["接口异常"] = exceptions

    # 6. 实时在线用户数（各服务商）
    online = {}
    if "实时在线用户数" in lines:
        idx = lines.index("实时在线用户数")
        i = idx + 2
        providers = ["ECO", "LAKA", "LAKA_NEW", "发单帝"]
        while i < len(lines) and lines[i] not in ("消息统计", "调度任务"):
            name = lines[i]
            if name in providers and i + 1 < len(lines) and "\t" in lines[i + 1]:
                parts = lines[i + 1].split("\t")
                online[name] = {"last": parts[0], "max": parts[1] if len(parts) > 1 else "", "min": parts[2] if len(parts) > 2 else ""}
                i += 2
            else:
                i += 1
    d["实时在线"] = online

    # 7. 第三方接口QPS总计（ECO/laka/lakaNew）
    qps_total = {}
    for label in ("ECO总计", "laka总计", "lakaNew总计"):
        if label in lines:
            idx = lines.index(label)
            if idx + 1 < len(lines) and "\t" in lines[idx + 1]:
                parts = lines[idx + 1].split("\t")
                qps_total[label] = {"last": parts[0], "max": parts[1] if len(parts)>1 else "", "min": parts[2] if len(parts)>2 else ""}
    d["QPS总计"] = qps_total

    return d


# ─── 分析 ────────────────────────────────────────────────────────────────────
def fail_rate(d: dict) -> float:
    recv = parse_num(d.get("接受消息数量总计", "0"))
    fail = parse_num(d.get("推送消息失败", "0"))
    return fail / recv if recv > 0 else 0.0


def analyze(data: dict) -> dict:
    w_now = data["windows"].get("now", {})
    w_6h  = data["windows"].get("6h",  {})
    w_24h = data["windows"].get("24h", {})

    alerts   = []
    insights = []
    sections = {}   # 分模块摘要

    def alert(level, msg): alerts.append({"level": level, "msg": msg})
    def ok(msg):           insights.append(msg)

    # ══ 模块1：核心指标 ════════════════════════════════════════════
    sec1 = []

    # 失败率
    rate_now = fail_rate(w_now)
    rate_6h  = fail_rate(w_6h)
    rate_24h = fail_rate(w_24h)
    base_rate = min(r for r in [rate_6h, rate_24h] if r > 0) if any(r > 0 for r in [rate_6h, rate_24h]) else 0
    r_pct = f"{rate_now*100:.2f}%"
    b_pct = f"{base_rate*100:.2f}%"
    if rate_now >= ABS["失败率_crit"] or (base_rate > 0 and rate_now > base_rate * DEV_CRIT):
        alert("🔴", f"[核心] 推送失败率严重偏高：当前 {r_pct} vs 历史均值 {b_pct}")
    elif rate_now >= ABS["失败率_warn"] or (base_rate > 0 and rate_now > base_rate * DEV_WARN):
        alert("🟡", f"[核心] 推送失败率偏高：当前 {r_pct} vs 历史均值 {b_pct}")
    else:
        ok(f"[核心] 推送失败率正常：{r_pct}（历史 {b_pct}）")
    sec1.append(f"失败率：{r_pct}（历史均值 {b_pct}）")

    # 时延
    delay_now = parse_num(w_now.get("待推送时间预估(s)", "0"))
    delay_6h  = parse_num(w_6h.get("待推送时间预估(s)", "0"))
    delay_24h = parse_num(w_24h.get("待推送时间预估(s)", "0"))
    base_delay = (delay_6h + delay_24h) / 2 if delay_6h and delay_24h else max(delay_6h, delay_24h)
    if delay_now >= ABS["时延_crit"] or (base_delay > 0 and delay_now > base_delay * DEV_CRIT):
        alert("🔴", f"[核心] 推送时延严重：当前 {fmt_sec(delay_now)} vs 历史均值 {fmt_sec(base_delay)}")
    elif delay_now >= ABS["时延_warn"] or (base_delay > 0 and delay_now > base_delay * DEV_WARN):
        alert("🟡", f"[核心] 推送时延偏高：当前 {fmt_sec(delay_now)} vs 历史均值 {fmt_sec(base_delay)}")
    else:
        ok(f"[核心] 推送时延正常：{fmt_sec(delay_now)}（历史均值 {fmt_sec(base_delay)}）")
    sec1.append(f"待推送时间：{w_now.get('待推送时间预估(s)', '-')}（历史均值 {fmt_sec(base_delay)}）")
    sec1.append(f"待推送消息：{w_now.get('待推送消息', '-')} | 待推送用户：{w_now.get('待推送用户数量', '-')}")
    sections["核心指标"] = sec1

    # ══ 模块2：消息堆积（分服务商） ══════════════════════════════════
    sec2 = []
    heap_now = w_now.get("堆积_分服务商", {})
    heap_6h  = w_6h.get("堆积_分服务商",  {})
    heap_24h = w_24h.get("堆积_分服务商", {})

    providers_heap = ["ECO", "LAKA", "LALA_NEW", "发单帝", "总堆积"]
    for prov in providers_heap:
        v_now = heap_now.get(prov, "-")
        v_6h  = heap_6h.get(prov, "-")
        v_24h = heap_24h.get(prov, "-")
        n_now = parse_num(v_now)
        n_6h  = parse_num(v_6h)
        n_24h = parse_num(v_24h)
        base  = (n_6h + n_24h) / 2 if n_6h and n_24h else max(n_6h, n_24h)

        flag = ""
        if base > 0 and n_now > base * DEV_CRIT:
            alert("🔴", f"[堆积-{prov}] 严重堆积：当前 {fmt_num(n_now)} vs 历史均值 {fmt_num(base)}")
            flag = " ⚠️🔴"
        elif base > 0 and n_now > base * DEV_WARN:
            alert("🟡", f"[堆积-{prov}] 堆积偏高：当前 {fmt_num(n_now)} vs 历史均值 {fmt_num(base)}")
            flag = " ⚠️🟡"
        elif prov == "总堆积" and n_now >= ABS["堆积_warn"]:
            alert("🟡", f"[堆积] 总堆积偏高：{fmt_num(n_now)}")
            flag = " ⚠️🟡"

        trend = ""
        if base > 0:
            ratio = n_now / base
            trend = f"  ({'↑' if ratio>1.1 else '↓' if ratio<0.9 else '→'} 历史均值 {fmt_num(base)})"

        sec2.append(f"{prov}：{v_now or '-'}{trend}{flag}")

    # MQ堆积
    mq_now = parse_num(w_now.get("MQ堆积数量", "0"))
    mq_6h  = parse_num(w_6h.get("MQ堆积数量", "0"))
    mq_24h = parse_num(w_24h.get("MQ堆积数量", "0"))
    mq_base = (mq_6h + mq_24h) / 2 if mq_6h and mq_24h else max(mq_6h, mq_24h)
    mq_flag = ""
    if mq_now >= ABS["mq_crit"] or (mq_base > 0 and mq_now > mq_base * DEV_CRIT):
        alert("🔴", f"[MQ] 堆积严重：当前 {mq_now:.0f} vs 历史均值 {mq_base:.0f}")
        mq_flag = " ⚠️🔴"
    elif mq_now >= ABS["mq_warn"] or (mq_base > 0 and mq_now > mq_base * DEV_WARN):
        alert("🟡", f"[MQ] 堆积偏高：当前 {mq_now:.0f} vs 历史均值 {mq_base:.0f}")
        mq_flag = " ⚠️🟡"
    sec2.append(f"MQ堆积：{w_now.get('MQ堆积数量', '-')}（历史均值 {mq_base:.0f}）{mq_flag}")
    sections["消息堆积（分服务商）"] = sec2

    # ══ 模块3：第三方接口异常（发单帝/ECO/Laka） ═══════════════════
    sec3 = []
    exc_now = w_now.get("接口异常", {})
    exc_6h  = w_6h.get("接口异常",  {})
    if exc_now:
        for iface, vals in exc_now.items():
            last  = vals.get("last", "0")
            total = vals.get("total", "0")
            # 判断服务商归属
            vendor = "发单帝" if "发单帝" in iface else "ECO" if "eco" in iface.lower() else "Laka" if "laka" in iface.lower() else "其他"
            base_total = parse_num(exc_6h.get(iface, {}).get("total", "0"))
            n_total = parse_num(total)
            flag = ""
            if n_total > 0 and (base_total == 0 or n_total > base_total * DEV_WARN):
                alert("🟡", f"[异常-{vendor}] {iface} 出现异常：last={last} total={total}")
                flag = " ⚠️🟡"
            sec3.append(f"[{vendor}] {iface}：last={last} total={total}{flag}")
    else:
        sec3.append("无接口异常记录")
        ok("[接口异常] 暂无异常")
    sections["第三方接口异常"] = sec3

    # ══ 模块4：实时在线用户（各服务商） ═══════════════════════════════
    sec4 = []
    online_now = w_now.get("实时在线", {})
    online_6h  = w_6h.get("实时在线",  {})
    for prov, vals in online_now.items():
        last = vals.get("last", "-")
        n_now_ol = parse_num(last)
        n_6h_ol  = parse_num(online_6h.get(prov, {}).get("last", "0"))
        flag = ""
        if n_6h_ol > 0 and n_now_ol < n_6h_ol * 0.5:
            alert("🟡", f"[在线-{prov}] 在线用户骤降：当前 {fmt_num(n_now_ol)} vs 历史 {fmt_num(n_6h_ol)}")
            flag = " ⚠️🟡 骤降"
        elif n_6h_ol > 0 and n_now_ol > n_6h_ol * 1.5:
            flag = " ↑ 增长"
        sec4.append(f"{prov}：{last}（历史均值 {fmt_num(n_6h_ol)}）{flag}")
    if not online_now:
        sec4.append("数据未加载")
    sections["实时在线用户"] = sec4

    return {"alerts": alerts, "insights": insights, "sections": sections}


# ─── 抓取 ────────────────────────────────────────────────────────────────────
def crawl_all(output_dir: str = "/tmp") -> dict:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = {"time": now_str, "windows": {}}

    with new_browser_context("grafana") as (ctx, page):
        print("[INFO] 检测登录状态...")
        page.goto(GRAFANA_LOGIN, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        body = page.inner_text("body")
        if "Log in" in body or "登录" in body:
            print("[WARN] 未登录，请在浏览器中手动登录（60秒）...")
            time.sleep(60)
            if "Log in" in page.inner_text("body"):
                result["error"] = "未登录"
                return result

        print("[INFO] 已登录，开始抓取...")
        for label, frm, to in WINDOWS:
            url = f"{GRAFANA_BASE}&from={frm}&to={to}"
            print(f"[INFO] 抓取 {label} 窗口（等待12s数据加载）...")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(12)   # 等待所有面板渲染完毕
                body = page.inner_text("body")
                metrics = parse_dashboard(body)
                result["windows"][label] = metrics
                page.screenshot(path=f"{output_dir}/grafana_{label}.png", full_page=False)
                print(f"  → 核心: 失败={metrics.get('推送消息失败','-')} 接收={metrics.get('接受消息数量总计','-')} 堆积={metrics.get('堆积_分服务商',{}).get('总堆积','-')}")
            except Exception as e:
                print(f"[WARN] {label} 失败: {e}")
                result["windows"][label] = {}
            time.sleep(2)

    out = os.path.join(output_dir, "grafana_stats.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


# ─── 格式化报告 ──────────────────────────────────────────────────────────────
def format_report(data: dict, analysis: dict) -> str:
    alerts   = analysis["alerts"]
    insights = analysis["insights"]
    sections = analysis["sections"]
    now_str  = data.get("time", "")

    has_crit = any(a["level"] == "🔴" for a in alerts)
    has_warn = any(a["level"] == "🟡" for a in alerts)
    if has_crit:
        icon, text = "🔴", "异常 · 需立即处理"
    elif has_warn:
        icon, text = "🟡", "注意 · 存在风险"
    else:
        icon, text = "🟢", "正常运行"

    lines = []
    lines.append(f"【云发单推送系统健康报告】{icon} {text}")
    lines.append(f"检查时间：{now_str}  |  对比基准：近6h / 近24h")
    lines.append("═" * 40)

    # 分模块输出
    module_icons = {
        "核心指标":        "📌",
        "消息堆积（分服务商）": "📦",
        "第三方接口异常":   "⚡",
        "实时在线用户":    "👥",
    }
    for mod, items in sections.items():
        lines.append(f"\n{module_icons.get(mod, '▪')} 【{mod}】")
        for item in items:
            lines.append(f"  {item}")

    # 告警汇总
    lines.append(f"\n{'═'*40}")
    if alerts:
        lines.append("⚠️  告警汇总")
        for a in alerts:
            lines.append(f"  {a['level']} {a['msg']}")
    else:
        lines.append("✅ 全部指标正常，无告警")

    lines.append(f"\n数据来源：Grafana · 云发单推送数据大盘")
    return "\n".join(lines)


# ─── 入口 ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="云发单 Grafana 健康检查 v2")
    parser.add_argument("--output", default="/tmp", help="输出目录")
    args = parser.parse_args()

    data = crawl_all(args.output)
    if data.get("error"):
        print(f"❌ 错误：{data['error']}")
        sys.exit(1)

    analysis = analyze(data)
    report   = format_report(data, analysis)
    print("\n" + report)

    rpath = os.path.join(args.output, "wechat_stats_report.txt")
    with open(rpath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n[DONE] 报告: {rpath}")
