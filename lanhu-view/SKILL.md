---
name: lanhu-view
description: 蓝湖原型需求提取。当用户提供蓝湖分享链接（lanhuapp.com/link）并要求提取需求、分析原型内容时触发。自动截图并使用 Claude Vision 图像识别，提取页面内容、UI 状态变化、交互流程，输出结构化需求文档。
---

# lanhu-view — 蓝湖原型需求提取

## 执行流程

### Step 1：运行抓取脚本

```bash
python3 ~/.openclaw/workspace/skills/lanhu-view/scripts/lanhu_view.py \
  --url "<蓝湖分享链接>" \
  --password "<访问密码（无密码可省略）>" \
  --output /tmp/lanhu_view
```

脚本自动完成：
1. 用持久化 browser profile（`lanhu_view`）打开蓝湖链接并输入密码
2. 读取侧边栏所有页面，自动跳过含「弃用/废弃/deprecated/旧版」的页面
3. 逐页点击 → 等待 iframe 渲染稳定 → 截图保存为 PNG
4. 对每张截图调用 Claude Vision API 进行图像识别
5. 输出 `pages.json`（含识别结果）和 `requirements.md`（结构化需求文档）

**输出目录：**
- `/tmp/lanhu_view/screenshots/` — 各页截图（PNG，按侧边栏顺序编号）
- `/tmp/lanhu_view/pages.json` — 页面列表（name / depth / screenshot / analysis）
- `/tmp/lanhu_view/requirements.md` — 结构化需求文档

### Step 2：输出需求文档

直接读取并输出 `/tmp/lanhu_view/requirements.md` 内容。

如有个别页面 Vision 分析失败（网络超时），单独对该页重试：

```python
import json, base64, urllib.request

API_KEY  = "<从 openclaw.json 读取>"
BASE_URL = "https://aigw.gzmiyuan.com/aicoding/v1"
MODEL    = "anthropic/claude-sonnet-4.6"

with open("<screenshot_path>", "rb") as f:
    img_b64 = base64.standard_b64encode(f.read()).decode()

payload = {
    "model": MODEL, "max_tokens": 2048,
    "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
        {"type": "text", "text": "<prompt>"}
    ]}]
}
req = urllib.request.Request(
    f"{BASE_URL}/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
)
with urllib.request.urlopen(req, timeout=60) as r:
    print(json.loads(r.read())["choices"][0]["message"]["content"])
```

## Vision 识别规则

每张截图的识别 prompt 遵循以下规则：

1. **只提取与本次需求相关的内容**，忽略：顶部状态栏（时间/信号/电量）、底部通用导航 Tab、与需求无关的其他业务模块
2. **有文字说明/标注** → 原文罗列，不改写
3. **有 UI 状态变化** → 描述每个状态的展示内容和跳转，格式：「如果用户xxx，显示xxx，点击跳转至【xxx】」
4. **有表单/列表字段** → 逐字段列出名称和示例值
5. **有交互操作** → 写明触发条件和跳转目标
6. 不总结、不归纳、不润色，不添加截图中没有的内容

## API 配置

Vision API 配置从 `~/.openclaw/openclaw.json` 自动读取：
- provider：`claude-sonnet`
- baseUrl：`https://aigw.gzmiyuan.com/aicoding/v1`
- model：`anthropic/claude-sonnet-4.6`

## 环境依赖

```bash
# 检查 playwright
python3 -c "from playwright.sync_api import sync_playwright; print('OK')"

# 安装（如未安装）
pip install playwright && playwright install chromium
```

## 注意事项

- 使用独立 browser profile `lanhu_view`，不影响其他 openclaw browser 会话
- 截图等待逻辑：点击侧边栏后检测 iframe 内容 MD5 变化，确认渲染完成再截图
- 同名页面只处理一次（跳过重复）
- Vision API 网络超时时，对失败页面单独重试即可，无需重新截图
