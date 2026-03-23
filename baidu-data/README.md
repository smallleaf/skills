# baidu-data — 百度指数查询助手

## 功能

输入关键词，自动打开浏览器访问百度指数，切换到移动端视图，抓取指定关键词的搜索指数数据并输出摘要。

## 触发场景

- "帮我查一下 xxx 的百度指数"
- "xxx 的移动端搜索指数是多少"
- "xxx 最近的搜索趋势怎么样"
- 询问同比、环比等数据

## 输出内容

- 整体搜索指数（PC + 移动端合计）
- 移动端指数
- 同比 / 环比变化
- 近期趋势摘要

## 依赖

- `playwright`：`pip install playwright && playwright install chromium`
- `openclaw browser` CLI（持久化 profile，Cookie 自动保存）

## 数据来源

[百度指数](https://index.baidu.com)
