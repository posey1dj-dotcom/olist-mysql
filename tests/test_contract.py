import csv
from datetime import datetime
from decimal import Decimal
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from catalog import c, convert, ID, ZIP, PRIMARY_KEYS, schema_sql
from data_contract import ROOT, read_rows, expected_rows


class ConversionTests(unittest.TestCase):
    def test_postal_leading_zero(self):
        self.assertEqual(convert('01001', c('zip', ZIP)), '01001')
        for value in ['1001', '01001.0', ' 01001', '０１００１']:
            with self.assertRaises(ValueError):
                convert(value, c('zip', ZIP))

    def test_decimal_exactness_and_no_rounding(self):
        col = c('price', 'DECIMAL(12,2)')
        self.assertEqual(convert('0.10', col) + convert('0.20', col), Decimal('0.30'))
        for value in ['0.001', 'NaN', 'Infinity', '10000000000']:
            with self.assertRaises(ValueError):
                convert(value, col)

    def test_empty_is_not_always_null(self):
        self.assertIsNone(convert('', c('date', 'DATETIME', True)))
        self.assertEqual(convert('', c('message', 'TEXT')), '')
        self.assertEqual(convert('NULL', c('message', 'TEXT')), 'NULL')

    def test_datetime_is_not_timezone_converted(self):
        self.assertEqual(convert('2018-01-01 13:24:15', c('created', 'DATETIME')),
                         datetime(2018, 1, 1, 13, 24, 15))
        for value in ['0000-00-00 00:00:00', '2018-01-01T13:24:15+00:00']:
            with self.assertRaises(ValueError):
                convert(value, c('created', 'DATETIME'))

    def test_csv_quotes_commas_and_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'product_category.csv'
            with path.open('w', encoding='utf-8-sig', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['product_category_name', 'product_category_name_english'])
                writer.writerow(['ação', 'a "quoted", category\nsecond line'])
            row = next(read_rows('product_category', Path(directory)))
            self.assertEqual(row['product_category_name_english'], 'a "quoted", category\nsecond line')
            self.assertEqual(row['product_category_name'], 'ação')

    def test_missing_geo_preserves_source(self):
        rows = list(expected_rows('sellers', set()))
        self.assertEqual(len(rows), 3095)
        self.assertTrue(all(row[1] and row[-1] is None for row in rows))

    def test_review_composite_key_and_sql_contract(self):
        rows = list(read_rows('order_reviews'))
        self.assertLess(len({x['review_id'] for x in rows}), len(rows))
        self.assertEqual(len({(x['review_id'], x['order_id']) for x in rows}), len(rows))
        self.assertEqual(PRIMARY_KEYS['order_reviews'], ('review_id', 'order_id'))
        self.assertEqual((ROOT / 'sql' / 'schema.sql').read_text(), schema_sql())


@unittest.skipUnless(os.environ.get('OLIST_RUN_DB_TESTS') == '1', 'Set OLIST_RUN_DB_TESTS=1 for MySQL tests')
class MySQLConstraintTests(unittest.TestCase):
    def setUp(self):
        from db import connect
        self.conn = connect('loader')

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def assert_mysql_rejects(self, code, sql, args=None):
        import pymysql
        with self.conn.cursor() as cur:
            with self.assertRaises(pymysql.MySQLError) as raised:
                cur.execute(sql, args)
        self.assertEqual(raised.exception.args[0], code)

    def test_rejects_orphan_order(self):
        with self.conn.cursor() as cur:
            cur.execute('SELECT order_id FROM orders LIMIT 1')
            order = cur.fetchone()[0]
        self.assert_mysql_rejects(1452, 'UPDATE orders SET customer_id=%s WHERE order_id=%s', ('0'*32, order))

    def test_rejects_negative_price(self):
        self.assert_mysql_rejects(3819, 'UPDATE order_items SET price=-1 LIMIT 1')

    def test_rejects_invalid_flag(self):
        self.assert_mysql_rejects(3819, 'UPDATE orders SET is_late=2 LIMIT 1')

    def test_rejects_duplicate_key(self):
        self.assert_mysql_rejects(1062, 'INSERT INTO product_category SELECT * FROM product_category LIMIT 1')

    def test_analyst_cannot_write(self):
        from manage import verify_readonly
        self.assertTrue(verify_readonly()['update_denied'])


if __name__ == '__main__':
    unittest.main()

