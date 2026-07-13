-- Scenario 1: Schema drift - rename qty to quantity
ALTER TABLE DEMO_SCHEMA.raw_sales RENAME COLUMN qty TO quantity;
