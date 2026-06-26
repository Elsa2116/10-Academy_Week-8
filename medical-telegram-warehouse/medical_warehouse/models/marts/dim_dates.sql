{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Dimension: dim_dates
    Spine of all calendar dates present in the message data.
    Generates rich date attributes for time-intelligence queries.
*/

with date_spine as (

    {{
        dbt_utils.date_spine(
            datepart="day",
            start_date="cast('2020-01-01' as date)",
            end_date="cast(current_date + interval '1 year' as date)"
        )
    }}

),

enriched as (

    select
        to_char(date_day, 'YYYYMMDD')::integer          as date_key,
        date_day                                         as full_date,

        extract(isodow from date_day)::integer           as day_of_week,   -- 1=Mon … 7=Sun
        to_char(date_day, 'Day')                         as day_name,
        extract(day from date_day)::integer              as day_of_month,

        extract(week from date_day)::integer             as week_of_year,
        extract(month from date_day)::integer            as month,
        to_char(date_day, 'Month')                       as month_name,
        extract(quarter from date_day)::integer          as quarter,
        extract(year from date_day)::integer             as year,

        case
            when extract(isodow from date_day) in (6, 7) then true
            else false
        end                                              as is_weekend

    from date_spine

)

select * from enriched
