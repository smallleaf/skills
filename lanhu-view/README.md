# lanhu-view — 蓝湖原型需求提取助手

## 功能

输入蓝湖分享链接，自动打开浏览器遍历所有原型页面截图，使用 Claude Vision 图像识别提取需求内容，输出结构化需求文档。

## 触发场景

- "用 lanhu-view 抓取这个蓝湖需求：https://lanhuapp.com/link/#/invite?sid=xxx"
- "读取蓝湖原型内容"

## 功能说明

- 自动输入分享密码，登录蓝湖
- 读取侧边栏页面列表，自动跳过含「弃用/废弃/deprecated/旧版」的页面
- 逐页点击截图，等待 iframe 渲染完成
- 调用 Claude Vision API 分析每张截图：
  - 只提取与当前需求相关的内容
  - 忽略无关通用 UI（状态栏、底部导航等）
  - 原文罗列标注文字，描述 UI 状态变化和交互流程
- 输出 `requirements.md` 需求文档

## 输出文件

| 文件 | 说明 |
|------|------|
| `screenshots/*.png` | 各页面截图 |
| `pages.json` | 页面数据（含 Vision 分析结果） |
| `requirements.md` | 结构化需求文档 |

默认输出目录：`/tmp/lanhu_view/`

## 依赖

- `playwright`：`pip install playwright && playwright install chromium`
- `openclaw browser` CLI（持久化 profile `lanhu_view`）
- Claude Vision API（通过 `~/.openclaw/openclaw.json` 配置读取）

## 使用示例

```
用 lanhu-view 抓取下这个需求：
https://lanhuapp.com/link/#/invite?sid=qxzLkrM7
密码：AOLp
```
