-- Scenario 1: rename qty so the baseline model (sum(qty)) fails with an invalid identifier.
ALTER TABLE DEMO_SCHEMA.raw_sales RENAME COLUMN qty TO quantity;
