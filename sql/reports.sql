-- =====================================================================
-- Part 1, Task 3 — Reports (run against the RAW, uncleaned data)
-- Run:  sqlite3 mamaearth.db < sql/reports.sql
-- Each query's exact output (sqlite3 -header -column) is pasted above it.
-- Note: discount_pct is INT, so we divide by 100.0 — dividing by 100
-- would be integer division in SQLite and silently return 0.
-- =====================================================================

-- ---------------------------------------------------------------------
-- a) Order totals (NULL discount treated as 0% via COALESCE)
-- ---------------------------------------------------------------------
-- Output:
--   total_orders  total_revenue  avg_order_value
--   ------------  -------------  ---------------
--   180           99860.20       554.78
SELECT
    COUNT(*)                                                                 AS total_orders,
    printf('%.2f', SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)))  AS total_revenue,
    printf('%.2f', AVG(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)))  AS avg_order_value
FROM orders o
JOIN products p ON p.product_id = o.product_id;

-- ---------------------------------------------------------------------
-- b) COUNT(*) vs COUNT(column) — COUNT(rating) skips NULLs
-- ---------------------------------------------------------------------
-- Output:
--   total_orders  rated_orders  unrated_orders
--   ------------  ------------  --------------
--   180           165           15
SELECT
    COUNT(*)                   AS total_orders,
    COUNT(rating)              AS rated_orders,
    COUNT(*) - COUNT(rating)   AS unrated_orders
FROM orders;

-- ---------------------------------------------------------------------
-- c) Customers with zero orders — LEFT JOIN, then confirmed with NOT IN
-- ---------------------------------------------------------------------
-- Output:
--   customer_id  name    order_count
--   -----------  ------  -----------
--   C045         Vihaan  0
SELECT c.customer_id, c.name, COUNT(o.order_id) AS order_count
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
HAVING COUNT(o.order_id) = 0;

-- Output:
--   customer_id  name
--   -----------  ------
--   C045         Vihaan
SELECT customer_id, name
FROM customers
WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders);

-- ---------------------------------------------------------------------
-- d) Return rate by city, only cities above 20%
-- ---------------------------------------------------------------------
-- Output:
--   city       total_orders  returned_orders  return_rate_pct
--   ---------  ------------  ---------------  ---------------
--   Jaipur     19            8                42.1
--   Lucknow    49            15               30.6
--   Bangalore  33            8                24.2
SELECT
    c.city,
    COUNT(*)                                     AS total_orders,
    SUM(o.returned)                              AS returned_orders,
    ROUND(100.0 * SUM(o.returned) / COUNT(*), 1) AS return_rate_pct
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.city
HAVING return_rate_pct > 20
ORDER BY return_rate_pct DESC;

-- ---------------------------------------------------------------------
-- e) Top customers by spend — ORDER BY + LIMIT / OFFSET
-- Tie-break on customer_id ASC makes the ranking deterministic, so LIMIT/OFFSET
-- pages never shuffle or skip customers whose total_spend is equal.
-- ---------------------------------------------------------------------
-- Output:
--   customer_id  name     total_spend
--   -----------  -------  -----------
--   C043         Reyansh  12920.00
--   C026         Isha     8371.60
--   C008         Meera    4564.60
--   C011         Arjun    4111.00
--   C042         Sanya    3785.00
SELECT
    c.customer_id,
    c.name,
    printf('%.2f', SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0))) AS total_spend
FROM orders o
JOIN products  p ON p.product_id  = o.product_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
ORDER BY SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)) DESC, c.customer_id ASC
LIMIT 5;

-- Output:
--   customer_id  name   total_spend
--   -----------  -----  -----------
--   C008         Meera  4564.60
--   C011         Arjun  4111.00
--   C042         Sanya  3785.00
SELECT
    c.customer_id,
    c.name,
    printf('%.2f', SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0))) AS total_spend
FROM orders o
JOIN products  p ON p.product_id  = o.product_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
ORDER BY SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)) DESC, c.customer_id ASC
LIMIT 3 OFFSET 2;

-- ---------------------------------------------------------------------
-- f) Revenue by category — three-table JOIN + GROUP BY
-- ---------------------------------------------------------------------
-- Output:
--   category      order_count  category_revenue
--   ------------  -----------  ----------------
--   Haircare      54           44956.10
--   Skincare      60           27346.00
--   Babycare      30           16805.00
--   PersonalCare  36           10753.10
SELECT
    p.category,
    COUNT(*) AS order_count,
    printf('%.2f', SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0))) AS category_revenue
FROM orders o
JOIN products  p ON p.product_id  = o.product_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY p.category
ORDER BY SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)) DESC;

-- ---------------------------------------------------------------------
-- g) LIKE — customers whose name starts with 'A'
-- ---------------------------------------------------------------------
-- Output:
--   customer_id  name    city
--   -----------  ------  ---------
--   C001         Aarav   Mumbai
--   C003         Aditi   Mumbai
--   C004         Ananya  Lucknow
--   C011         Arjun   Bangalore
--   C021         Aryan   Bangalore
--   C030         Anika   Bangalore
--   C031         Aditya  Jaipur
--   C036         Aisha   Delhi
--   C041         Ayaan   Lucknow
--   C044         Aria    Bangalore
SELECT customer_id, name, city
FROM customers
WHERE name LIKE 'A%'
ORDER BY customer_id;

-- ---------------------------------------------------------------------
-- h) DISTINCT acquisition sources
-- ---------------------------------------------------------------------
-- Output:
--   acquisition_source
--   ------------------
--   Ad
--   Organic
--   Referral
--   Social
SELECT DISTINCT acquisition_source
FROM customers
ORDER BY acquisition_source;

-- ---------------------------------------------------------------------
-- i) ALTER TABLE + UPDATE with CASE — loyalty tier
-- (Rebuilding the schema drops this column again, so the whole pipeline
--  stays re-runnable.)
-- ---------------------------------------------------------------------
ALTER TABLE customers ADD COLUMN loyalty_tier VARCHAR(10);

UPDATE customers
SET loyalty_tier = CASE WHEN city_tier = 1 THEN 'Gold' ELSE 'Silver' END;

-- Output:
--   loyalty_tier  customers
--   ------------  ---------
--   Gold          28
--   Silver        17
SELECT loyalty_tier, COUNT(*) AS customers
FROM customers
GROUP BY loyalty_tier
ORDER BY loyalty_tier;
