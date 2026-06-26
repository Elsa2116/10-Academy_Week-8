/*
    Custom dbt test: assert_no_future_messages
    ============================================
    Fails (returns > 0 rows) if any message has a date in the future.
    This guards against clock-skew or data corruption in the scraper.
*/

select
    message_id,
    channel_name,
    message_date
from {{ ref('stg_telegram_messages') }}
where message_date > now()
