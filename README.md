# Olist MySQL 数据库

将提供的 Olist 清洗数据部署为 **MySQL 8.4 的 9 张业务表**。仓库包含完整数据快照、关系设计、可审阅 DDL、Python 导入/校验程序和分析示例。克隆后可直接让 Codex 完成部署。

`data/clean/` 中的 9 个文件采用 `.csv.gz` 无损压缩，程序直接读取，不需要手工解压。每张表同时记录压缩文件和原始 CSV 的 SHA-256；解压后与提供的文件逐字节一致。

这是一份可复现的数据库项目：每位协作者在自己的电脑或服务器运行 MySQL。GitHub 保存代码和数据文件，数据库连接地址是部署机器的地址。

## 给 Codex 的启动指令

在本仓库目录打开 Codex，发送：

> 请阅读 AGENTS.md 和 README.md，按这个仓库提供的入口配置 MySQL，导入指定的 9 张表并运行完整校验。不要把分析宽表或清洗报告导入数据库。完成后给我连接参数，并使用只读账号进行后续分析。保留已有数据库和 .env，不要打印密码。

## 一键搭建

本仓库已公开，可直接克隆并部署：

```bash
git clone https://github.com/posey1dj-dotcom/olist-mysql.git
cd olist-mysql
python3 scripts/bootstrap.py
```

需要 **Python 3.10+**。如果 macOS 的 `python3` 指向系统 Python 3.9，请使用已安装的 `python3.12`。首次运行需要联网下载 MySQL 或 Docker 镜像及 Python 依赖。

部署入口自动选择：

- Docker 已启动：使用 Compose，支持 macOS、Windows 和 Linux。Windows 可使用 `py -3 scripts/bootstrap.py`。
- Apple Silicon macOS 没有 Docker：下载官方 MySQL ARM 包到项目的 `.local/`，创建隔离环境并启动数据库；不需要 sudo。
- 其他没有 Docker 的系统：先安装并启动 Docker Desktop，或在 Linux 安装 Docker Engine 与 Compose。

也可明确指定：

```bash
python3 scripts/bootstrap.py --mode docker
python3 scripts/bootstrap.py --mode native   # Apple Silicon macOS
```

成功输出 `PASS` 才表示导入和完整校验通过。已有相同快照时再次运行会逐值验证，**不会重复导入**。已有数据不符时会停止，不会清空或覆盖。

## 数据库连接配置

| 参数 | 默认值 |
| --- | --- |
| MySQL 版本 | 8.4.11 LTS |
| 主机 | `127.0.0.1` |
| 端口 | `3307`，避免与已有 `3306` 冲突 |
| 数据库名 | `olist` |
| 分析账号 | `olist_analyst`，只有该库的 `SELECT` 权限 |
| 导入账号 | `olist_loader`，用于建表与导入 |
| 密码 | 首次运行随机生成，保存在本机 `.env` |
| 字符集 / 引擎 | `utf8mb4` / `InnoDB` |
| 文本排序规则 | `utf8mb4_0900_as_cs`；ID 和邮编使用 `ascii_bin` |

`.env.example` 是配置说明，真实 `.env`、数据库文件和日志均被 Git 忽略。不要把 `.env` 发到聊天或提交到 GitHub。协作者独立生成自己的密码。

在 MySQL Workbench、DBeaver 等客户端中，填写上述主机、端口、库名与分析用户名，密码使用 `.env` 中的 `MYSQL_ANALYST_PASSWORD`。

## 9 张表与实际行数

| 表 | 行数 | 主键 |
| --- | ---: | --- |
| `geolocation` | 19,011 | `zip_code_prefix` |
| `customers` | 99,441 | `customer_id` |
| `sellers` | 3,095 | `seller_id` |
| `product_category` | 74 | `product_category_name` |
| `products` | 32,951 | `product_id` |
| `orders` | 99,441 | `order_id` |
| `order_items` | 112,650 | `(order_id, order_item_id)` |
| `order_payments` | 103,886 | `(order_id, payment_sequential)` |
| `order_reviews` | 99,224 | `(review_id, order_id)` |
| **合计** | **569,773** | |

以下两个文件只作为文件交付，**不会创建对应 SQL 表**：

- `analysis/fact_orders_wide.csv.gz`：99,441 行订单级分析宽表的无损压缩副本。可运行 `python3 scripts/unpack_analysis.py` 还原 CSV，或用 `pandas.read_csv(..., compression='gzip')` 读取。
- `analysis/data_quality_report.csv`：原始清洗日志，共 47 条记录。

## 关系设计与数据处理

完整说明见 [数据库设计](docs/database_design.md)，字段定义见 [数据字典](docs/data_dictionary.md)，可直接阅读 [schema.sql](sql/schema.sql)。

- 保留 9 个 CSV 的全部字段和记录，日期空值导入为 SQL `NULL`，评价空文本保留为空字符串。
- 保留源邮编前导零；客户、卖家各增加一个 `geo_zip_code_prefix` 可空外键。匹配不到地理表的 279 条客户记录、7 条卖家记录仍保留原邮编，新外键设为 `NULL`。
- 设置 9 条真实外键。导入全程不关闭外键检查，不使用 `INSERT IGNORE` 或 `REPLACE`。
- `review_id` 本身不唯一，不能单独作为主键；一个订单也可能有多条评价。
- 保留清洗脚本的异常标记和衍生字段。本库是便于分析的关系模型，包含有意保留的冗余衍生字段，并不宣称所有字段都严格满足第三范式。
- 金额用 `DECIMAL(...,2)`，其他小数保留源文件的 4 位精度，不使用浮点数中转。

## Python 连接与分析

Docker 部署后，如果需要在宿主机运行 Python 分析，先创建 Python 环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/example_analysis.py
```

Windows 对应的 Python 路径是 `.venv\Scripts\python.exe`。原生部署已经创建 `.venv`，可直接运行示例。

```python
import sys
sys.path.insert(0, 'scripts')
from db import connect

with connect() as conn:  # 默认使用 olist_analyst
    with conn.cursor() as cur:
        cur.execute('SELECT order_status, COUNT(*) FROM orders GROUP BY order_status')
        print(cur.fetchall())
```

`sql/analysis_examples.sql` 提供订单状态、月度金额和客户复购查询。金额分析先在订单粒度分别聚合商品与支付，避免把多条商品、支付、评价直接连接后重复计算。

## 校验与测试

```bash
.venv/bin/python scripts/manage.py audit
.venv/bin/python scripts/manage.py verify
.venv/bin/python -m unittest discover -s tests -v
OLIST_RUN_DB_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
```

Docker 容器内校验可运行：

```bash
docker compose run --rm setup python scripts/manage.py verify
```

校验包含 SHA-256、字段顺序、主键重复、引用完整性、实际 SQL 类型和约束、全部记录逐值比对、金额合计，以及只读账号权限。运行报告写入 `reports/`，不包含密码；本次交付的验证结果见 [验证记录](docs/verification.md)。

GitHub Actions 会使用一个新的 MySQL 容器执行部署、再次运行、完整校验和约束测试。工作流文件已提供；是否真正通过以仓库 Actions 状态为准。

## 启动、停止与保留数据

Docker：

```bash
docker compose stop mysql
docker compose up -d --wait mysql
```

原生 macOS：

```bash
.venv/bin/python scripts/native_mysql.py stop
.venv/bin/python scripts/native_mysql.py start
```

原生服务不会注册开机自启，重启电脑后需要运行 `start`。Docker 使用具名数据卷，原生模式使用 `.local/mysql-data/`。停止服务不会删除数据。保留原始 `.env`；更改其中的密码不会自动重置现有 MySQL 账号。

## 在自己的服务器上部署

在自己的 Linux 服务器克隆仓库，使用 Docker 模式即可。默认仍只绑定 `127.0.0.1:3307`。从电脑远程分析时可通过 SSH 隧道连接：

```bash
ssh -L 3307:127.0.0.1:3307 your_user@your_server
```

也支持已经安装好的 **MySQL 8.4**：运行 `python3 scripts/bootstrap.py --env-only`，在本地编辑 `.env` 填入该服务器的管理凭据、未占用的专用库名和独立应用账号，然后运行 `python3 scripts/bootstrap.py --mode existing`。远程直连需配置 `MYSQL_SSL_CA` 并验证证书；使用 SSH 隧道时主机仍填 `127.0.0.1`。

## 数据来源与复现边界

原始数据由 [Olist 在 Kaggle 发布](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)。本仓库使用用户提供的清洗快照，原样保留清洗程序 `scripts/olist_preprocess.py` 和清洗日志；构建数据库无需重新清洗，也不需要 Kaggle 凭据。

`data/manifest.json` 记录每张表的行数、字段、文件大小与 SHA-256。若使用另一版数据，请单独审计并更新数据契约，不要只改哈希绕过校验。需要从原始数据重新清洗时，另行安装 `requirements-preprocess.txt` 并按脚本说明运行。

课程 PDF 只用来参考关系、键和完整性约束设计，没有被上传到仓库。数据出处、授权标识及处理边界见 [DATA_SOURCES.md](DATA_SOURCES.md)。
