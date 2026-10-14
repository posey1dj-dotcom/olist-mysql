-- Run with the olist_analyst account after selecting the olist database.
-- Currency: BRL. Historical statuses are included unless a filter says otherwise.

SELECT order_status, COUNT(*) AS n_orders
FROM orders GROUP BY order_status ORDER BY n_orders DESC;

-- Aggregate each one-to-many relation BEFORE joining it to orders.
WITH items AS (
  SELECT order_id, SUM(price) AS items_price, SUM(freight_value) AS freight
  FROM order_items GROUP BY order_id
), payments AS (
  SELECT order_id, SUM(payment_value) AS payments
  FROM order_payments GROUP BY order_id
)
SELECT o.purchase_month, COUNT(*) AS n_orders,
       SUM(i.items_price) AS items_price_brl, SUM(i.freight) AS freight_brl,
       SUM(p.payments) AS payments_brl,
       SUM(i.order_id IS NULL) AS orders_without_items,
       SUM(p.order_id IS NULL) AS orders_without_payments
FROM orders o
LEFT JOIN items i ON o.order_id = i.order_id
LEFT JOIN payments p ON o.order_id = p.order_id
WHERE o.is_full_period = 1
GROUP BY o.purchase_month ORDER BY o.purchase_month;

-- Repeat-customer counts across all statuses in this historical snapshot.
WITH customer_orders AS (
  SELECT c.customer_unique_id, COUNT(o.order_id) AS n_orders
  FROM customers c JOIN orders o ON c.customer_id = o.customer_id
  GROUP BY c.customer_unique_id
)
SELECT COUNT(*) AS unique_customers,
       SUM(n_orders > 1) AS repeat_customers
FROM customer_orders;

-- Optional geography: unmatched customers remain visible in the result.
SELECT c.customer_state, COUNT(*) AS customers,
       SUM(g.zip_code_prefix IS NULL) AS without_geolocation
FROM customers c
LEFT JOIN geolocation g ON g.zip_code_prefix = c.geo_zip_code_prefix
GROUP BY c.customer_state ORDER BY customers DESC;

-- Deterministic latest review per order. review_id breaks timestamp ties.
WITH ranked_reviews AS (
  SELECT order_id, review_id, review_score, review_answer_timestamp,
         ROW_NUMBER() OVER (PARTITION BY order_id
             ORDER BY review_answer_timestamp DESC, review_id DESC) AS position
  FROM order_reviews
)
SELECT o.order_id, o.order_status, r.review_score
FROM orders o
LEFT JOIN ranked_reviews r ON r.order_id = o.order_id AND r.position = 1
ORDER BY o.order_id LIMIT 20;

