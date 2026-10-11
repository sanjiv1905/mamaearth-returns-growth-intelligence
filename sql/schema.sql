-- =====================================================================
-- Part 1, Task 1 — Schema
-- Mamaearth Returns & Growth Intelligence Pipeline (SQLite)
-- Re-runnable: drops the tables first (child table before parents).
-- =====================================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS products;

CREATE TABLE customers (
    customer_id        VARCHAR(10) PRIMARY KEY,
    name               VARCHAR(50) NOT NULL,
    city               VARCHAR(50) NOT NULL,
    city_tier          INT         NOT NULL,
    signup_date        DATE        NOT NULL,
    acquisition_source VARCHAR(20) NOT NULL
);

CREATE TABLE products (
    product_id   VARCHAR(10)   PRIMARY KEY,
    product_name VARCHAR(100)  NOT NULL,
    category     VARCHAR(30)   NOT NULL,
    price        DECIMAL(10,2) NOT NULL
);

-- discount_pct and rating are deliberately nullable: an order can be
-- un-rated or have no promo code, and NULL is the honest representation.
CREATE TABLE orders (
    order_id       VARCHAR(10) PRIMARY KEY,
    customer_id    VARCHAR(10) NOT NULL,
    product_id     VARCHAR(10) NOT NULL,
    order_date     DATE        NOT NULL,
    quantity       INT         NOT NULL,
    discount_pct   INT,
    payment_method VARCHAR(10) NOT NULL,
    rating         INT,
    returned       INT         NOT NULL DEFAULT 0,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id)  REFERENCES products(product_id)
);
