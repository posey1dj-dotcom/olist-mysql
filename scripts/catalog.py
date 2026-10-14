"""Reviewed schema contract. Source fields are preserved; two geo FK fields are added."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re


@dataclass(frozen=True)
class Column:
    name: str
    sql: str
    nullable: bool = False
    derived: bool = False

    @property
    def base_type(self):
        return self.sql.lower().split(' character set')[0]


ID = 'CHAR(32) CHARACTER SET ascii COLLATE ascii_bin'
ZIP = 'CHAR(5) CHARACTER SET ascii COLLATE ascii_bin'
FLAG = 'TINYINT UNSIGNED'


def c(name, sql, nullable=False, derived=False):
    return Column(name, sql, nullable, derived)


TABLES = {
    'geolocation': [c('zip_code_prefix', ZIP), c('lat', 'DECIMAL(8,4)'),
        c('lng', 'DECIMAL(8,4)'), c('city', 'VARCHAR(100)'), c('state', 'CHAR(2)'),
        c('n_points', 'INT UNSIGNED')],
    'customers': [c('customer_id', ID), c('customer_unique_id', ID),
        c('customer_zip_code_prefix', ZIP), c('customer_city', 'VARCHAR(100)'),
        c('customer_state', 'CHAR(2)'), c('customer_total_orders', 'INT UNSIGNED'),
        c('geo_zip_code_prefix', ZIP, True, True)],
    'sellers': [c('seller_id', ID), c('seller_zip_code_prefix', ZIP),
        c('seller_city', 'VARCHAR(100)'), c('seller_state', 'CHAR(2)'),
        c('geo_zip_code_prefix', ZIP, True, True)],
    'product_category': [c('product_category_name', 'VARCHAR(64)'),
        c('product_category_name_english', 'VARCHAR(100)')],
    'products': [c('product_id', ID), c('product_category_name', 'VARCHAR(64)'),
        c('product_name_length', 'SMALLINT UNSIGNED'),
        c('product_description_length', 'INT UNSIGNED'),
        c('product_photos_qty', 'SMALLINT UNSIGNED'),
        c('product_weight_g', 'DECIMAL(12,4)'), c('product_length_cm', 'DECIMAL(10,4)'),
        c('product_height_cm', 'DECIMAL(10,4)'), c('product_width_cm', 'DECIMAL(10,4)'),
        c('is_listing_info_missing', FLAG), c('product_volume_cm3', 'DECIMAL(16,4)')],
    'orders': [c('order_id', ID), c('customer_id', ID), c('order_status', 'VARCHAR(20)'),
        c('order_purchase_timestamp', 'DATETIME'), c('order_approved_at', 'DATETIME', True),
        c('order_delivered_carrier_date', 'DATETIME', True),
        c('order_delivered_customer_date', 'DATETIME', True),
        c('order_estimated_delivery_date', 'DATE'), c('is_time_anomaly', FLAG),
        c('is_status_anomaly', FLAG), c('purchase_date', 'DATE'),
        c('purchase_year', 'SMALLINT UNSIGNED'), c('purchase_month', 'CHAR(7)'),
        c('purchase_dow', FLAG), c('purchase_hour', FLAG),
        c('approve_hours', 'DECIMAL(14,4)', True), c('delivery_days', 'DECIMAL(12,4)', True),
        c('estimated_days', 'DECIMAL(12,4)'), c('delay_days', 'DECIMAL(12,4)', True),
        c('is_late', FLAG, True), c('is_slow_approval', FLAG), c('is_full_period', FLAG)],
    'order_items': [c('order_id', ID), c('order_item_id', 'SMALLINT UNSIGNED'),
        c('product_id', ID), c('seller_id', ID), c('shipping_limit_date', 'DATETIME'),
        c('price', 'DECIMAL(12,2)'), c('freight_value', 'DECIMAL(12,2)'),
        c('item_total', 'DECIMAL(12,2)'), c('freight_ratio', 'DECIMAL(14,4)'),
        c('is_price_outlier', FLAG)],
    'order_payments': [c('order_id', ID), c('payment_sequential', 'SMALLINT UNSIGNED'),
        c('payment_type', 'VARCHAR(20)'), c('payment_installments', 'SMALLINT UNSIGNED'),
        c('payment_value', 'DECIMAL(12,2)')],
    'order_reviews': [c('review_id', ID), c('order_id', ID), c('review_score', FLAG),
        c('review_comment_title', 'VARCHAR(255)'), c('review_comment_message', 'TEXT'),
        c('review_creation_date', 'DATETIME'), c('review_answer_timestamp', 'DATETIME'),
        c('has_comment', FLAG), c('comment_length', 'INT UNSIGNED'),
        c('answer_hours', 'DECIMAL(14,4)'), c('sentiment_label', 'VARCHAR(10)')],
}

PRIMARY_KEYS = {
    'geolocation': ('zip_code_prefix',), 'customers': ('customer_id',),
    'sellers': ('seller_id',), 'product_category': ('product_category_name',),
    'products': ('product_id',), 'orders': ('order_id',),
    'order_items': ('order_id', 'order_item_id'),
    'order_payments': ('order_id', 'payment_sequential'),
    'order_reviews': ('review_id', 'order_id'),
}

# (child table, child column, parent table, parent column)
FOREIGN_KEYS = [
    ('customers', 'geo_zip_code_prefix', 'geolocation', 'zip_code_prefix'),
    ('sellers', 'geo_zip_code_prefix', 'geolocation', 'zip_code_prefix'),
    ('products', 'product_category_name', 'product_category', 'product_category_name'),
    ('orders', 'customer_id', 'customers', 'customer_id'),
    ('order_items', 'order_id', 'orders', 'order_id'),
    ('order_items', 'product_id', 'products', 'product_id'),
    ('order_items', 'seller_id', 'sellers', 'seller_id'),
    ('order_payments', 'order_id', 'orders', 'order_id'),
    ('order_reviews', 'order_id', 'orders', 'order_id'),
]

INDEXES = {
    'geolocation': [('state',)],
    'customers': [('customer_unique_id',), ('customer_state',), ('customer_zip_code_prefix',)],
    'sellers': [('seller_state',), ('seller_zip_code_prefix',)],
    'orders': [('order_purchase_timestamp',), ('order_status', 'purchase_month')],
    'order_reviews': [('order_id', 'review_answer_timestamp', 'review_id')],
}

CHECKS = {
    'geolocation': ['lat BETWEEN -90 AND 90', 'lng BETWEEN -180 AND 180', 'n_points > 0'],
    'customers': ['customer_total_orders > 0'],
    'products': ['product_weight_g > 0', 'product_length_cm > 0', 'product_height_cm > 0',
        'product_width_cm > 0', 'product_volume_cm3 > 0'],
    'orders': ['purchase_dow BETWEEN 0 AND 6', 'purchase_hour BETWEEN 0 AND 23',
        "order_status IN ('delivered','shipped','canceled','unavailable','invoiced','processing','created','approved')"],
    'order_items': ['order_item_id > 0', 'price > 0', 'freight_value >= 0',
        'item_total = price + freight_value', 'freight_ratio >= 0'],
    'order_payments': ['payment_sequential > 0', 'payment_installments > 0', 'payment_value >= 0',
        "payment_type IN ('credit_card','boleto','voucher','debit_card','not_defined')"],
    'order_reviews': ['review_score BETWEEN 1 AND 5', 'answer_hours >= 0',
        'comment_length = CHAR_LENGTH(review_comment_message)',
        "has_comment = (CHAR_LENGTH(review_comment_message) > 0)",
        "sentiment_label = CASE WHEN review_score <= 2 THEN 'negative' WHEN review_score = 3 THEN 'neutral' ELSE 'positive' END"],
}


def source_columns(table):
    return [col for col in TABLES[table] if not col.derived]


def convert(value, col):
    """No float conversion, trimming, truncation, NULL-string guessing, or silent rounding."""
    if value is None:
        if col.nullable:
            return None
        raise ValueError(f'{col.name}: NULL is not allowed')
    kind = col.base_type
    if value == '' and col.nullable:
        return None
    if kind.startswith(('char(', 'varchar(', 'text')):
        match = re.search(r'\((\d+)\)', kind)
        if match and len(value) > int(match[1]):
            raise ValueError(f'{col.name}: text exceeds declared length')
        if col.sql == ID and not re.fullmatch(r'[0-9a-f]{32}', value):
            raise ValueError(f'{col.name}: invalid 32-character identifier')
        if col.sql == ZIP and not re.fullmatch(r'\d{5}', value, flags=re.ASCII):
            raise ValueError(f'{col.name}: invalid five-digit postal prefix')
        return value
    if kind.startswith(('tinyint', 'smallint', 'int')):
        if not re.fullmatch(r'\d+', value, flags=re.ASCII):
            raise ValueError(f'{col.name}: expected an integer')
        result = int(value)
        upper = 255 if kind.startswith('tinyint') else 65535 if kind.startswith('smallint') else 4294967295
        if result > upper:
            raise ValueError(f'{col.name}: integer exceeds declared range')
        return result
    if kind.startswith('decimal'):
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f'{col.name}: invalid decimal') from exc
        precision, scale = map(int, re.findall(r'\d+', kind))
        if not result.is_finite() or abs(result) >= Decimal(10) ** (precision - scale):
            raise ValueError(f'{col.name}: decimal exceeds declared range')
        if result != result.quantize(Decimal(10) ** -scale):
            raise ValueError(f'{col.name}: decimal would be rounded')
        return result
    if kind == 'date':
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError(f'{col.name}: invalid date format')
        result = date.fromisoformat(value)
    elif kind == 'datetime':
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', value):
            raise ValueError(f'{col.name}: invalid datetime format')
        result = datetime.fromisoformat(value)
    else:
        raise ValueError(f'Unsupported type: {kind}')
    if result.year < 1000:
        raise ValueError(f'{col.name}: outside MySQL date range')
    return result


def checks_for(table):
    checks = list(CHECKS.get(table, []))
    checks += [f'{x.name} IN (0,1)' for x in TABLES[table]
               if x.name.startswith('is_') or x.name == 'has_comment']
    return checks


def schema_sql():
    statements = ['-- Generated by scripts/render_schema.py from scripts/catalog.py.\n'
                  '-- Select the database before executing. Exactly nine base tables.']
    for table, columns in TABLES.items():
        parts = [f'  `{x.name}` {x.sql} ' + ('NULL' if x.nullable else 'NOT NULL') for x in columns]
        parts += ['  PRIMARY KEY (' + ', '.join(f'`{x}`' for x in PRIMARY_KEYS[table]) + ')']
        for i, columns_ in enumerate(INDEXES.get(table, []), 1):
            parts += [f'  KEY `idx_{table}_{i}` (' + ', '.join(f'`{x}`' for x in columns_) + ')']
        for child, field, parent, target in FOREIGN_KEYS:
            if child == table:
                parts += [f'  CONSTRAINT `fk_{child}_{field}` FOREIGN KEY (`{field}`) '
                          f'REFERENCES `{parent}` (`{target}`) ON DELETE RESTRICT ON UPDATE RESTRICT']
        for i, expr in enumerate(checks_for(table), 1):
            parts += [f'  CONSTRAINT `ck_{table}_{i}` CHECK ({expr})']
        statements += [f'CREATE TABLE IF NOT EXISTS `{table}` (\n' + ',\n'.join(parts) +
                       '\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs;']
    return '\n\n'.join(statements) + '\n'

