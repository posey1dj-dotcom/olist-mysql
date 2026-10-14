"""Run small, correctly grained analysis queries with the SELECT-only account."""
from db import connect

QUERY = '''
WITH item_totals AS (
  SELECT order_id, SUM(item_total) AS items_total FROM order_items GROUP BY order_id
), payment_totals AS (
  SELECT order_id, SUM(payment_value) AS payment_total FROM order_payments GROUP BY order_id
)
SELECT o.purchase_month, COUNT(*) AS n_orders,
       SUM(i.items_total) AS items_total_brl, SUM(p.payment_total) AS payments_brl,
       SUM(i.order_id IS NULL) AS orders_without_items,
       SUM(p.order_id IS NULL) AS orders_without_payments
FROM orders o
LEFT JOIN item_totals i ON i.order_id = o.order_id
LEFT JOIN payment_totals p ON p.order_id = o.order_id
WHERE o.is_full_period = 1
GROUP BY o.purchase_month ORDER BY o.purchase_month
'''

if __name__ == '__main__':
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(QUERY)
            print('\t'.join(x[0] for x in cur.description))
            for row in cur.fetchall():
                print('\t'.join('NULL' if x is None else str(x) for x in row))

