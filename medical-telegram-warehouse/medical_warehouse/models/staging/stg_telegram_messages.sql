{{
    config(
        materialized='view',
        schema='staging'
    )
}}

/*
    Staging model for raw Telegram messages.
    - Casts data types correctly
    - Renames columns to consistent snake_case conventions
    - Filters out completely empty / null messages
    - Adds derived helper fields (message_length, has_image)
*/

with source as (

    select * from {{ source('raw', 'telegram_messages') }}

),

cleaned as (

    select
        -- identifiers
        message_id::bigint                                  as message_id,
        trim(channel_name)                                  as channel_name,

        -- temporal
        message_date::timestamptz                           as message_date,
        message_date::date                                  as message_date_day,

        -- content
        coalesce(trim(message_text), '')                    as message_text,
        length(coalesce(trim(message_text), ''))            as message_length,

        -- media
        coalesce(has_media, false)::boolean                 as has_media,
        coalesce(is_photo, false)::boolean                  as has_image,
        image_path,

        -- engagement
        coalesce(views, 0)::integer                         as view_count,
        coalesce(forwards, 0)::integer                      as forward_count,

        -- metadata
        scraped_at::timestamptz                             as scraped_at,
        loaded_at::timestamptz                              as loaded_at

    from source

    where
        -- drop rows with no useful content or missing identifiers
        message_id is not null
        and channel_name is not null
        and channel_name <> ''
        and (
            length(coalesce(trim(message_text), '')) > 0
            or coalesce(is_photo, false) = true
        )
        -- no future-dated messages
        and message_date <= now()

)

select * from cleaned
