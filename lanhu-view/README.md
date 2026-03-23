# lanhu-view — 蓝湖原型需求提取

## 功能

提供蓝湖分享链接，自动完成截图 + Claude Vision 图像识别，提取页面内容、UI 状态变化、字段说明、交互流程，输出结构化需求文档。

## 触发场景

- "用 lanhu-view 抓取下这个需求 https://lanhuapp.com/link/..."
- "提取蓝湖原型的需求内容"
- "分析这个蓝湖分享链接"

## 输出内容

- 各页面 UI 状态变化（不同条件下的展示内容）
- 表单/列表字段及示例值
- 交互操作（触发条件 → 跳转目标）
- 文字标注原文（不改写）
- 完整需求文档（`/tmp/lanhu_view/requirements.md`）

## 使用方式

```
用 lanhu-view 抓取：https://lanhuapp.com/link/#/invite?sid=xxx
密码：xxxx
```

## 技术实现

- `playwright` 持久化 profile（`lanhu_view`）打开蓝湖并截图
- Claude Vision API（`anthropic/claude-sonnet-4.6`）图像识别
- 自动跳过含「弃用/废弃/deprecated/旧版」的页面
- 截图等待 iframe MD5 变化，确保内容渲染完成

## 依赖

- `playwright`：`pip install playwright && playwright install chromium`
- Claude Vision API（通过 `~/.openclaw/openclaw.json` 配置）
