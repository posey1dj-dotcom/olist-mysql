# 数据字典

SQL 定义以 `sql/schema.sql` 为准。`NULL=是` 的列允许缺失；其余列必须有值。标记位为 0/1，金额为 BRL，尺寸为 cm、重量为 g。

## geolocation

| 字段 | MySQL 类型 | NULL | 说明 |
| --- | --- | --- | --- |
| `zip_code_prefix` | CHAR(5) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段；主键组成部分 |
| `lat` | DECIMAL(8,4) | 否 | 源 CSV 字段 |
| `lng` | DECIMAL(8,4) | 否 | 源 CSV 字段 |
| `city` | VARCHAR(100) | 否 | 源 CSV 字段 |
| `state` | CHAR(2) | 否 | 源 CSV 字段 |
| `n_points` | INT UNSIGNED | 否 | 源 CSV 字段 |

## customers

| 字段 | MySQL 类型 | NULL | 说明 |
| --- | --- | --- | --- |
| `customer_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段；主键组成部分 |
| `customer_unique_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段；复购分析使用此身份标识 |
| `customer_zip_code_prefix` | CHAR(5) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段 |
| `customer_city` | VARCHAR(100) | 否 | 源 CSV 字段 |
| `customer_state` | CHAR(2) | 否 | 源 CSV 字段 |
| `customer_total_orders` | INT UNSIGNED | 否 | 源 CSV 字段 |
| `geo_zip_code_prefix` | CHAR(5) CHARACTER SET ascii COLLATE ascii_bin | 是 | 新增：存在于 geolocation 的邮编，否则 NULL |

## sellers

| 字段 | MySQL 类型 | NULL | 说明 |
| --- | --- | --- | --- |
| `seller_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段；主键组成部分 |
| `seller_zip_code_prefix` | CHAR(5) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段 |
| `seller_city` | VARCHAR(100) | 否 | 源 CSV 字段 |
| `seller_state` | CHAR(2) | 否 | 源 CSV 字段 |
| `geo_zip_code_prefix` | CHAR(5) CHARACTER SET ascii COLLATE ascii_bin | 是 | 新增：存在于 geolocation 的邮编，否则 NULL |

## product_category

| 字段 | MySQL 类型 | NULL | 说明 |
| --- | --- | --- | --- |
| `product_category_name` | VARCHAR(64) | 否 | 源 CSV 字段；主键组成部分 |
| `product_category_name_english` | VARCHAR(100) | 否 | 源 CSV 字段 |

## products

| 字段 | MySQL 类型 | NULL | 说明 |
| --- | --- | --- | --- |
| `product_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段；主键组成部分 |
| `product_category_name` | VARCHAR(64) | 否 | 源 CSV 字段 |
| `product_name_length` | SMALLINT UNSIGNED | 否 | 源 CSV 字段 |
| `product_description_length` | INT UNSIGNED | 否 | 源 CSV 字段 |
| `product_photos_qty` | SMALLINT UNSIGNED | 否 | 源 CSV 字段 |
| `product_weight_g` | DECIMAL(12,4) | 否 | 源 CSV 字段 |
| `product_length_cm` | DECIMAL(10,4) | 否 | 源 CSV 字段 |
| `product_height_cm` | DECIMAL(10,4) | 否 | 源 CSV 字段 |
| `product_width_cm` | DECIMAL(10,4) | 否 | 源 CSV 字段 |
| `is_listing_info_missing` | TINYINT UNSIGNED | 否 | 源 CSV 字段；保留源清洗标记 |
| `product_volume_cm3` | DECIMAL(16,4) | 否 | 源 CSV 字段 |

## orders

| 字段 | MySQL 类型 | NULL | 说明 |
| --- | --- | --- | --- |
| `order_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段；主键组成部分 |
| `customer_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段 |
| `order_status` | VARCHAR(20) | 否 | 源 CSV 字段 |
| `order_purchase_timestamp` | DATETIME | 否 | 源 CSV 字段 |
| `order_approved_at` | DATETIME | 是 | 源 CSV 字段 |
| `order_delivered_carrier_date` | DATETIME | 是 | 源 CSV 字段 |
| `order_delivered_customer_date` | DATETIME | 是 | 源 CSV 字段 |
| `order_estimated_delivery_date` | DATE | 否 | 源 CSV 字段 |
| `is_time_anomaly` | TINYINT UNSIGNED | 否 | 源 CSV 字段；保留源清洗标记 |
| `is_status_anomaly` | TINYINT UNSIGNED | 否 | 源 CSV 字段；保留源清洗标记 |
| `purchase_date` | DATE | 否 | 源 CSV 字段 |
| `purchase_year` | SMALLINT UNSIGNED | 否 | 源 CSV 字段 |
| `purchase_month` | CHAR(7) | 否 | 源 CSV 字段 |
| `purchase_dow` | TINYINT UNSIGNED | 否 | 源 CSV 字段 |
| `purchase_hour` | TINYINT UNSIGNED | 否 | 源 CSV 字段 |
| `approve_hours` | DECIMAL(14,4) | 是 | 源 CSV 字段 |
| `delivery_days` | DECIMAL(12,4) | 是 | 源 CSV 字段 |
| `estimated_days` | DECIMAL(12,4) | 否 | 源 CSV 字段 |
| `delay_days` | DECIMAL(12,4) | 是 | 源 CSV 字段 |
| `is_late` | TINYINT UNSIGNED | 是 | 源 CSV 字段；保留源清洗标记 |
| `is_slow_approval` | TINYINT UNSIGNED | 否 | 源 CSV 字段；保留源清洗标记 |
| `is_full_period` | TINYINT UNSIGNED | 否 | 源 CSV 字段；保留源清洗标记 |

## order_items

| 字段 | MySQL 类型 | NULL | 说明 |
| --- | --- | --- | --- |
| `order_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段；主键组成部分 |
| `order_item_id` | SMALLINT UNSIGNED | 否 | 源 CSV 字段；主键组成部分 |
| `product_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段 |
| `seller_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段 |
| `shipping_limit_date` | DATETIME | 否 | 源 CSV 字段 |
| `price` | DECIMAL(12,2) | 否 | 源 CSV 字段 |
| `freight_value` | DECIMAL(12,2) | 否 | 源 CSV 字段 |
| `item_total` | DECIMAL(12,2) | 否 | 源 CSV 字段 |
| `freight_ratio` | DECIMAL(14,4) | 否 | 源 CSV 字段 |
| `is_price_outlier` | TINYINT UNSIGNED | 否 | 源 CSV 字段；保留源清洗标记 |

## order_payments

| 字段 | MySQL 类型 | NULL | 说明 |
| --- | --- | --- | --- |
| `order_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段；主键组成部分 |
| `payment_sequential` | SMALLINT UNSIGNED | 否 | 源 CSV 字段；主键组成部分 |
| `payment_type` | VARCHAR(20) | 否 | 源 CSV 字段 |
| `payment_installments` | SMALLINT UNSIGNED | 否 | 源 CSV 字段 |
| `payment_value` | DECIMAL(12,2) | 否 | 源 CSV 字段 |

## order_reviews

| 字段 | MySQL 类型 | NULL | 说明 |
| --- | --- | --- | --- |
| `review_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段；主键组成部分 |
| `order_id` | CHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 否 | 源 CSV 字段；主键组成部分 |
| `review_score` | TINYINT UNSIGNED | 否 | 源 CSV 字段 |
| `review_comment_title` | VARCHAR(255) | 否 | 源 CSV 字段 |
| `review_comment_message` | TEXT | 否 | 源 CSV 字段 |
| `review_creation_date` | DATETIME | 否 | 源 CSV 字段 |
| `review_answer_timestamp` | DATETIME | 否 | 源 CSV 字段 |
| `has_comment` | TINYINT UNSIGNED | 否 | 源 CSV 字段 |
| `comment_length` | INT UNSIGNED | 否 | 源 CSV 字段 |
| `answer_hours` | DECIMAL(14,4) | 否 | 源 CSV 字段 |
| `sentiment_label` | VARCHAR(10) | 否 | 源 CSV 字段 |
