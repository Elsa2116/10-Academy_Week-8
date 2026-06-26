/*
    Custom dbt test: assert_positive_views
    =======================================
    Fails (returns > 0 rows) if any message has a negative view count.
    Telegram view counts are always >= 0; negative values indicate
    a data loading or casting error.
*/

select
    message_id,
    channel_name,
    view_count
from {{ ref('fct_messages') }}
where view_count < 0
