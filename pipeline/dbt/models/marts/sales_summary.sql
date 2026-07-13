-- demo_sales_etl
{{ config(
    materialized='table',
    tags=['demo_sales_etl']
) }}

select
    user_id,
    sum(qty) as total_qty,
    max(sale_date) as last_sale
from {{ source('demo', 'raw_sales') }}
group by user_id
