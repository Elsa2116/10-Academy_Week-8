{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Fact: fct_messages
    Central fact table of the star schema.
    One row per Telegram message, linked to dim_channels and dim_dates.
*/

with messages as (

    select * from {{ ref('stg_telegram_messages') }}

),

channels as (

    select channel_key, channel_name from {{ ref('dim_channels') }}

),

dates as (

    select date_key, full_date from {{ ref('dim_dates') }}

),

joined as (

    select
        m.message_id,
        c.channel_key,
        d.date_key,

        m.message_text,
        m.message_length,
        m.view_count,
        m.forward_count,
        m.has_image,

        m.message_date,
        m.scraped_at

    from messages m
    left join channels c on m.channel_name = c.channel_name
    left join dates    d on m.message_date_day = d.full_date

)

select * from joined
