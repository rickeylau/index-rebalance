# Index Rebalance Calendar

适用于 SPX / ES 交易的独立日历。所有指数调整事件均标为 Expected，属于按已公布方法规则计算的计划提醒，不是公告抓取结果。月末/季末只是自定义提醒，不保证实际有大额资金流。

- SPX / NDX 季度调整尾盘：第三个周五，休市时采用上一交易日作为预估；默认收盘前 30 分钟至收盘。
- NDX 公告：生效日之前第六个交易日收盘后（以收盘时点提醒，15 分钟显示长度并非官方发布时间）。
- NDX 生效：第三个周五之后第一个交易日开盘。12 月年度重组和季度调权合并显示。
- 月末/季末：最后一个交易日的最后 30 分钟，季度末不重复生成月末事件。
- 所有时间按纽约时区处理并输出 UTC；事件均为透明，不占用忙碌状态。
- 每日读取 rickeylau/market-holidays 的 holidays.json，新增已公布年份后自动扩展。失败保留仓库上次日历；不预测缺失年份。GitHub 调度和 Google Calendar 同步可能延迟。
- 不抓取非定期成分调整、临时特别再平衡或具体买卖股票/资金规模。S&P 500 成分可以随时调整，实际日期以官方公告为准。

## 安装
1. 创建公开仓库 `index-rebalance`，上传六个普通文件（README、config、Python 脚本、测试、holidays_snapshot.json、index-rebalance.ics）。
2. 单独创建 `.github/workflows/update-calendar.yml` 并粘贴工作流。Actions → Update Index Rebalance → Run workflow。
3. 订阅 `https://raw.githubusercontent.com/rickeylau/index-rebalance/main/index-rebalance.ics`。若缓存问题可尝试在末尾加 `#1`，也可更换为 `?v=2`。
4. 每日 UTC 07:33 自动运行，修改 config 后也会运行。无需 API Key 或本地电脑。

## 自定义
config.json 开关为 true/false，close_reminder_minutes 默认 30。关闭全部开关时拒绝发布空日历。初始文件包含 2026–2027 年日历。

## 本地验证
`python -m unittest -v`；`python index_rebalance.py --offline` 使用已有快照。`python index_rebalance.py` 真实抓取节假日仓库。

## 官方参考
- https://indexes.nasdaq.com/docs/Methodology_NDX.pdf
- https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-us-indices.pdf
- https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-equity-indices-policies-practices.pdf
- https://www.cboe.com/about/hours/us-options/
