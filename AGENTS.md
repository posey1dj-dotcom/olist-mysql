# Olist 数据库任务约定

目标：使用本仓库的真实 CSV 快照，部署可继续分析的 MySQL 8.4 数据库。

1. 先读 README.md、docs/database_design.md 与 data/manifest.json，检查当前目录、Python、Docker 和现有 `.env`。不要读取或打印密码内容来做状态报告。
2. 部署入口是 `python3 scripts/bootstrap.py`。支持自动选择 Docker 或 Apple Silicon macOS 原生模式；明确模式见 README。Python 需要 3.10+。
3. 只导入 geolocation、customers、sellers、product_category、products、orders、order_items、order_payments、order_reviews，共 9 张表。不要导入分析宽表或清洗日志。
4. CSV 及 scripts/olist_preprocess.py 是提供的输入快照。不要重新清洗、覆盖、删行或重新生成 manifest 来掩盖不一致。所有字段来自实际文件。
5. 邮编是五位字符串。customers/sellers 保留原邮编，并通过可空的 geo_zip_code_prefix 关联 geolocation。缺失匹配不得导致删除客户/卖家，也不得制造坐标。
6. order_reviews 使用 (review_id, order_id) 联合主键。不要把 review_id 或 order_id 单独设为唯一键。
7. `.env` 由入口生成独立随机密码。不要提交、上传、回显 `.env`、运行日志或 `.local`。数据库默认只监听本机。
8. 不使用 DROP DATABASE、TRUNCATE、DELETE、REPLACE、INSERT IGNORE 或关闭外键检查来绕过问题。重复运行应验证已有快照；不一致时报告具体问题并保留已有库。
9. 部署后运行完整逐值校验、只读权限检查与 tests 中的测试。只有实际成功才报告数据库已就绪。区分本机、Docker 和 GitHub Actions 的真实验证状态。
10. 后续分析默认使用 `scripts/db.py` 的 `connect()`，即 SELECT-only 账号。涉及金额连接时先分别按 order_id 聚合。复购使用 customer_unique_id。
11. 最后报告数据库版本、主机、端口、库名、用户名、密码文件位置、9 表行数、校验结果和未验证部分。不输出真实密码。

