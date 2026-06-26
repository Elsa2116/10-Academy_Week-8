{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Dimension: dim_channels
    One row per unique Telegram channel with summary statistics.
    Includes a surrogate key and a manually-assigned channel_type.
*/

with channel_stats as (

    select
        channel_name,
        count(*)                                    as total_posts,
        min(message_date)                           as first_post_date,
        max(message_date)                           as last_post_date,
        avg(view_count)                             as avg_views

    from {{ ref('stg_telegram_messages') }}
    group by channel_name

),

with_type as (

    select
        {{ dbt_utils.generate_surrogate_key(['channel_name']) }}   as channel_key,
        channel_name,

        -- Assign channel type based on known handles
        case
            when lower(channel_name) like '%chemed%'    then 'Medical'
            when lower(channel_name) like '%lobelia%'   then 'Cosmetics'
            when lower(channel_name) like '%tikvah%'    then 'Pharmaceutical'
            when lower(channel_name) like '%pharma%'    then 'Pharmaceutical'
            else 'Other'
        end                                                         as channel_type,

        total_posts,
        round(avg_views::numeric, 2)                                as avg_views,
        first_post_date::date                                       as first_post_date,
        last_post_date::date                                        as last_post_date

    from channel_stats

)

select * from with_type
