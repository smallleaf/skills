---
name: miyuan-news
description: 新浪电商新闻抓取助手。当用户询问今日电商动态、电商新闻、阿里/京东/拼多多/抖音电商等平台资讯时触发。自动打开浏览器搜索新浪新闻，过滤出当天的电商相关新闻，汇总成简洁的中文摘要返回。
---

# 新浪电商新闻爬虫 (miyuan-news)

## 🎯 目标
访问新浪新闻搜索，按电商关键词逐一抓取**当日**新闻，去重合并后输出结构化摘要。

---

## 📋 执行流程

### Step 1：确认关键词
默认内置电商关键词（无需用户指定）：
`阿里巴巴 / 淘宝 / 天猫 / 京东 / 拼多多 / 多多买菜 / 抖音电商 / 快手电商 / 美团 / 得物 / 唯品会`

用户也可指定额外关键词，如"帮我加上小红书电商"→ 追加到列表。

---

### Step 2：环境检测
```bash
python3 -c "from playwright.sync_api import sync_playwright; print('OK')" 2>/dev/null || echo "MISSING"
```

---

### Step 3：运行爬虫
```bash
python3 ~/.openclaw/workspace/skills/miyuan-news/scripts/sina_news_crawler.py \
  --output /tmp
```

自定义关键词时：
```bash
python3 ~/.openclaw/workspace/skills/miyuan-news/scripts/sina_news_crawler.py \
  --keywords "阿里巴巴,京东,拼多多,小红书" \
  --output /tmp
```

爬虫行为：
1. 使用持久化浏览器 profile（`sina_news`），Cookie 自动保存
2. 按关键词逐一访问新浪搜索：`https://search.sina.com.cn/search?q={keyword}&tp=news&sort=0`
3. 只保留**今日**新闻（匹配今天日期 / 相对时间如"1小时前"）
4. 跨关键词去重（相同标题只保留一条）
5. 输出 JSON + 可读摘要

---

### Step 4：读取结果
```bash
TODAY=$(date +%Y-%m-%d)
cat /tmp/miyuan_news_${TODAY}.json
```

---

### Step 5：输出格式

```
📰 电商新闻日报 · YYYY-MM-DD
共抓取今日新闻 N 条，涵盖关键词：阿里巴巴 / 京东 / ...

🔹 京东（3 条）
- **标题**  `来源 时间`
  _摘要..._
  🔗 链接

🔹 拼多多（2 条）
...
```

---

## ⚠️ 核心约束
1. **只输出今日新闻** — 非当天的内容一律过滤
2. **跨关键词去重** — 同一标题只展示一次
3. **无结果时明确告知** — 不编造新闻
4. **每关键词最多展示 5 条** — 超出截断，避免输出过长
