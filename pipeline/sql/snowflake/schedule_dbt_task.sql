-- Schedule periodic dbt runs for a deployed Snowflake dbt project object.
-- Replace placeholders with your actual object names from: SHOW DBT PROJECTS IN SCHEMA DEMO_DB.DEMO_SCHEMA;

USE DATABASE DEMO_DB;
USE SCHEMA DEMO_SCHEMA;

-- Example: run sales_summary every 6 hours
CREATE OR ALTER TASK run_sales_dbt
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = '6 HOUR'
  COMMENT = 'demo_sales_etl scheduled dbt run'
AS
  EXECUTE DBT PROJECT DEMO_DB.DEMO_SCHEMA.SNOWFLAKES_SALES
    ARGS = 'run --select sales_summary --target dev';

-- Tasks are created suspended — must resume
ALTER TASK run_sales_dbt RESUME;

-- Manual one-off test
-- EXECUTE TASK run_sales_dbt;

-- Monitor task runs
-- SELECT * FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
--   SCHEDULED_TIME_RANGE_START => DATEADD('day', -7, CURRENT_TIMESTAMP()),
--   TASK_NAME => 'RUN_SALES_DBT'
-- )) ORDER BY SCHEDULED_TIME DESC;
