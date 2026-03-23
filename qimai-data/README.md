# qimai-data — 七麦数据抓取助手

## 功能

自动打开浏览器读取七麦数据网站，抓取今日 App Store（中国区）新上架/下架应用数量、应用列表及审核时长等市场数据，输出简洁摘要。

## 触发场景

- "今天 App Store 新上架了多少应用"
- "今日 iOS 下架应用有哪些"
- "苹果审核现在要多久"
- "七麦数据今天的数据"

## 输出内容

- 今日新上架应用数量
- 今日下架应用数量
- 应用总数
- 当前审核时长
- 典型应用列表（部分）

## 依赖

- `playwright`：`pip install playwright && playwright install chromium`
- `openclaw browser` CLI

## 数据来源

[七麦数据](https://www.qimai.cn)
