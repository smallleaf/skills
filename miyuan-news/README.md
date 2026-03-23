# miyuan-news — 新浪电商新闻抓取助手

## 功能

自动打开浏览器搜索新浪新闻，过滤出当天的电商相关新闻，汇总成简洁的中文摘要返回。

## 触发场景

- "今日电商动态有哪些"
- "最新电商新闻"
- "阿里/京东/拼多多/抖音电商今天有什么新闻"
- "电商行业今天发生了什么"

## 输出内容

- 当日电商平台动态（阿里、京东、拼多多、抖音等）
- 行业政策/监管动态
- 重要融资/并购消息
- 新闻标题 + 简要摘要 + 来源链接

## 依赖

- `playwright`：`pip install playwright && playwright install chromium`
- `openclaw browser` CLI

## 数据来源

[新浪新闻](https://news.sina.com.cn)
