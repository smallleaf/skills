---
name: qimai-data
description: 七麦数据抓取助手。当用户询问今日 App Store 新上架/下架应用数量、应用列表、审核时长等市场数据时触发。自动打开浏览器读取七麦网站内容，输出简洁的市场动态摘要。
---

# 七麦数据抓取引擎 (Qimai Data Crawler)

## 🎯 目标
打开浏览器读取 https://www.qimai.cn/ 首页及相关子页，抓取今日 App Store（中国区）新上架/下架应用数量和列表，输出简洁摘要。

---

## 📋 执行流程

### Step 1：环境检测
```bash
python3 -c "from playwright.sync_api import sync_playwright; print('OK')" 2>/dev/null || echo "MISSING"
```
- ✅ OK：继续 Step 2
- ❌ MISSING：告知用户环境未就绪

---

### Step 2：运行爬虫
```bash
python3 ~/.openclaw/workspace/skills/qimai-data/scripts/qimai_crawler.py --output /tmp
```

爬虫访问顺序：
1. `https://www.qimai.cn/` — 抓取核心统计（新上架数、下架数、总数、审核时长）
2. `https://www.qimai.cn/rank/release` — 抓取新上架应用列表
3. `https://www.qimai.cn/rank/offline` — 抓取下架应用列表

---

### Step 3：读取结果
```bash
cat /tmp/qimai_data.json
```

---

### Step 4：输出摘要

按以下格式输出：

---

## 📄 输出格式

```
📱 App Store 市场动态（中国区）
🕒 数据更新：YYYY-MM-DD HH:mm

📊 今日概览
• 新上架应用：XXX 个
• 下架应用：X,XXX 个
• 应用总数：X,XXX,XXX 个
• 30天平均审核时长：X.XH

🆕 新上架应用（部分）
1. [应用名] · [开发者] · [类别] · 上架：YYYY-MM-DD
2. ...

🔻 下架应用（部分）
1. [应用名] · [开发者] · [类别] · 下架：YYYY-MM-DD
2. ...
```

---

## ⚠️ 核心约束
1. **只输出真实抓取内容**，不补充或编造数据
2. **数字直接引用**，不做四舍五入或估算
3. 七麦需要登录才能查看完整列表，免登录仅能看到部分数据，如数据不完整需说明
