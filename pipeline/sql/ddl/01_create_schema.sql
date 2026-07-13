CREATE DATABASE IF NOT EXISTS DEMO_DB;
USE DATABASE DEMO_DB;
CREATE SCHEMA IF NOT EXISTS DEMO_SCHEMA;
USE SCHEMA DEMO_SCHEMA;

CREATE TABLE IF NOT EXISTS raw_sales (
    sale_id INT,
    user_id INT,
    product_id INT,
    qty INT,
    sale_date DATE
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id INT,
    name STRING,
    category STRING
);

-- sales_summary is built by dbt (models/marts/sales_summary.sql)
