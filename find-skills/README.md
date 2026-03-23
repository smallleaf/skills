# find-skills — Agent 技能发现助手

## 功能

帮助用户发现和安装 Agent 技能。当用户询问"如何做某件事"或"有没有某个技能"时，自动搜索技能生态并给出推荐。

## 触发场景

- "有没有能做 xxx 的技能"
- "找一个 xxx 技能"
- "我想扩展 xxx 能力"
- "怎么做 xxx"（可能存在现成技能）

## 功能说明

- 搜索 [clawhub.com](https://clawhub.com) 技能市场
- 使用 `npx skills find [query]` 查找技能
- 使用 `npx skills add <package>` 安装技能
- 使用 `npx skills check` / `npx skills update` 检查和更新

## 依赖

- Node.js（`npx` 命令）
