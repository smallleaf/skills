# miyuan-wechat-stats — 云发单服务状态检查

## 功能

自动抓取 Grafana Dashboard 的多时间窗口（5分钟/15分钟/30分钟/1小时）数据，对比关键指标，输出云发单服务健康报告和异常告警。

## 触发场景

- "云发单现在正常吗"
- "推送有没有异常"
- "Grafana 数据怎么样"
- "系统健康状态检查"

## 输出内容

- 待推送消息数 / 堆积量
- 失败率
- MQ 堆积情况
- 推送延迟
- 多时间窗口对比分析
- 健康状态结论 + 异常告警

## 依赖

- `playwright`：`pip install playwright && playwright install chromium`
- Grafana 访问权限（Cookie 持久化，通常无需重复登录）
