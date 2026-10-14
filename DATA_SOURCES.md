# 数据来源与处理记录

原始数据：**Brazilian E-Commerce Public Dataset by Olist**，由 Olist 发布。

- 原始发布页：https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- 发布页标注的授权：**CC BY-NC-SA 4.0**。
- 授权链接：https://creativecommons.org/licenses/by-nc-sa/4.0/
- 本仓库的清洗数据是该数据的衍生版本，数据按上述授权提供；请保留 Olist 来源及清洗说明。

本项目的输入是用户于 2026-10-14 提供的 `olist_clean` 文件夹和 `olist_preprocess.py`，不宣称 CSV 是未经修改的 Kaggle 原文件。清洗程序按字节原样复制至 `scripts/olist_preprocess.py`，清洗记录原样复制至 `analysis/data_quality_report.csv`。

源清洗包括：地理点按邮编聚合、城市文本规范化、类目修复、少量尺寸/重量填补、订单异常标记、商品金额衍生、支付分期修复、评价文字整理及订单宽表生成。具体步骤及影响数量以随附脚本和 47 条清洗记录为准。**数据库建设阶段没有再次执行这些清洗，也没有改变源 CSV。**

建库阶段的明确映射：

1. 保留 9 个业务 CSV 的全部行、原始列及值。
2. 可空日期、时长、标记的空字段映射为 SQL NULL；空评价文本仍是空字符串。
3. 客户和卖家表各添加一个可空地理外键，不覆盖原邮编。
4. 金额和小数使用十进制定点类型，拒绝会造成舍入的输入。
5. 9 个业务 CSV 和宽表都以 `.csv.gz` 无损压缩交付，可按 SHA-256 验证还原。程序直接读取压缩业务表；宽表和清洗日志不入库。

文件哈希、大小、字段及业务表行数见 `data/manifest.json`。课件 PDF 仅供本地参考，没有包含在仓库中。

技术参考：

- MySQL 8.4 官方文档：https://dev.mysql.com/doc/refman/8.4/en/
- 官方 Docker 镜像：https://hub.docker.com/_/mysql
- macOS 官方下载页：https://dev.mysql.com/downloads/mysql/8.4.html
