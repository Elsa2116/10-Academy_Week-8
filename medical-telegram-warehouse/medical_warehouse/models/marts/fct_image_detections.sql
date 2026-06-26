{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Fact: fct_image_detections
    One row per image analysed by YOLOv8.
    Joined to fct_messages via message_id, and to dim_channels / dim_dates
    for time-series and channel-level visual content analysis.
*/

with yolo as (

    select * from {{ source('raw', 'yolo_detections') }}

),

channels as (

    select channel_key, channel_name from {{ ref('dim_channels') }}

),

messages as (

    select
        message_id,
        channel_name,
        date_key,
        view_count

    from {{ ref('fct_messages') }}

),

joined as (

    select
        y.message_id,
        c.channel_key,
        m.date_key,

        y.image_path,
        y.detected_objects,
        y.detected_classes,
        y.max_confidence::numeric(6,4)  as confidence_score,
        y.image_category,
        y.num_detections::integer       as num_detections,

        m.view_count

    from yolo y
    left join channels c on y.channel_name = c.channel_name
    left join messages m on y.message_id   = m.message_id
                        and y.channel_name = m.channel_name

)

select * from joined
