---
name: baidu-data
description: 百度指数查询助手。当用户输入关键词并询问百度搜索指数、移动端指数、搜索趋势、同比环比等数据时触发。自动打开浏览器访问百度指数，切换到移动端视图，读取搜索指数数据并输出摘要。
---

# 百度指数查询引擎 (Baidu Index Crawler)

## 🎯 目标
打开 `https://index.baidu.com/v2/main/index.html#/trend/{keyword}?words={keyword}`，切换到**移动端**视图，抓取指定关键词的搜索指数数据并输出结构化摘要。

---

## 📋 执行流程

### Step 1：提取关键词
从用户输入中识别查询关键词，如：
- "帮我查一下水印相机的百度指数" → keyword=`水印相机`
- "看看微信的移动端搜索指数" → keyword=`微信`

---

### Step 2：环境检测
```bash
python3 -c "from playwright.sync_api import sync_playwright; print('OK')" 2>/dev/null || echo "MISSING"
```

---

### Step 3：运行爬虫
首页入口：`https://index.baidu.com/v2/index.html#/`

```bash
python3 ~/.openclaw/workspace/skills/baidu-data/scripts/baidu_index_crawler.py \
  --keyword "[关键词]" \
  --device "移动" \
  --output /tmp \
  --cookie ~/.openclaw/workspace/.baidu_cookies.json
```

爬虫行为：
1. 检查 `~/.openclaw/workspace/.baidu_cookies.json` 是否存在，有则自动加载免登录
2. 打开百度指数页面
3. 检测登录状态
4. 切换设备为**移动端**（点击 `PC+移动` 下拉 → 选择`移动`）
5. 读取搜索指数概览表格（日均值、同比、环比）
6. 截图保存，输出 JSON

---

### Step 4：读取结果
```bash
cat /tmp/baidu_index_{keyword}.json
```

---

### Step 5：输出格式

```
🔍 百度指数查询结果

关键词：[keyword]
设备：移动端
时间：近30天
数据更新：每天12~16时

📊 搜索指数概览
• 移动日均值：[avg_mobile]
• 整体日均值：[avg_overall]
• 移动同比：[mobile_yoy]（较去年同期）
• 移动环比：[mobile_mom]（较上月）
• 整体同比：[overall_yoy]
• 整体环比：[overall_mom]

📈 趋势解读
[根据同比/环比数据简单描述趋势]
```

---

## 🔐 登录说明

百度指数需要登录才能查看数据。支持两种方式：

### 方式1：Cookie 文件（推荐，免重复登录）
将百度登录 Cookie 保存到：
`~/.openclaw/workspace/.baidu_cookies.json`

格式：
```json
[
  {"name": "BDUSS", "value": "你的BDUSS值", "domain": ".baidu.com", "path": "/"},
  {"name": "STOKEN", "value": "你的STOKEN值", "domain": ".baidu.com", "path": "/"}
]
```

### 方式2：手动登录
不提供 Cookie 时，爬虫会打开登录框，等待 30 秒供用户手动扫码/密码登录，登录成功后自动保存 Cookie 供下次使用。

---

## ⚠️ 核心约束
1. **默认切换移动端** — 除非用户明确指定 PC 或 PC+移动
2. **只输出真实数据** — 未登录时明确告知，不编造指数数字
3. **Cookie 持久化** — 登录成功后自动保存，下次免登录
4. **多关键词支持** — 百度指数支持对比多个词，需多次调用脚本
