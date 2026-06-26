/*
    Custom dbt test: assert_fk_messages_to_channels
    =================================================
    Every row in fct_messages must resolve to a channel in dim_channels.
    Orphaned facts prevent joins from working correctly in the API layer.
*/

select
    fm.message_id,
    fm.channel_key
from {{ ref('fct_messages') }} fm
left join {{ ref('dim_channels') }} dc on fm.channel_key = dc.channel_key
where dc.channel_key is null
