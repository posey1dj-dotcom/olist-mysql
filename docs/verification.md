# 验证记录

验证日期：2026-10-14。输入为本仓库 `data/manifest.json` 锁定的清洗快照。

## 本机真实运行

- 平台：Apple Silicon macOS；Python 3.12；MySQL Community Server **8.4.11**。
- 9 张表成功导入 **569,773 行**，原始 CSV 和预处理脚本保持逐字节一致。
- 全量读取 MySQL，与 CSV 比较 **6,113,333 个字段值**，全部一致；该数量包括两列新增可空地理外键。
- 9 个主键、9 条外键、字段类型、可空性、字符集和已启用的检查约束验证通过。
- 279 条客户、7 条卖家的地理外键为 NULL，原邮编和记录完整保留。
- 再次执行 setup 验证通过，未插入、删除或覆盖任何已有记录。
- 使用分析账号执行完整验证和月度分析示例成功；只读账号只有该库 SELECT 权限，UPDATE 被 MySQL 拒绝。
- 12 项测试全部通过，其中 5 项在真实 MySQL 上检查主键、外键、CHECK 和只读权限；测试事务均回滚。
- 订单宽表的 gzip 副本解压后 SHA-256 与原文件一致。

## 金额校验值

以下是完整快照的控制合计，包含所有订单状态，不是单独定义的已完成销售收入。

| 指标 | BRL |
| --- | ---: |
| 商品价格合计 | 13,591,643.70 |
| 运费合计 | 2,251,909.54 |
| 商品价格与运费合计 | 15,843,553.24 |
| 支付金额合计 | 16,008,872.12 |

支付和商品合计的差异保留源数据，不强行修改为相等。

## 可重跑命令

```bash
.venv/bin/python scripts/manage.py audit
.venv/bin/python scripts/manage.py setup
.venv/bin/python scripts/manage.py verify
OLIST_RUN_DB_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/example_analysis.py
```

动态报告写到本机 `reports/source_audit.json` 和 `reports/database_validation.json`。它们由当前环境生成，不包含连接密码。

## 平台验证边界

macOS 原生 MySQL 已真实验证。本机没有 Docker；Docker 的端到端结果以仓库 [GitHub Actions](https://github.com/posey1dj-dotcom/olist-mysql/actions) 为准。Windows 本机和用户自有远程服务器未在本次验证中运行。
