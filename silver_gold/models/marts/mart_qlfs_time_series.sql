-- Gold layer: business-ready QLFS time series, one row per
-- (quarter, metric). This is the table the Streamlit dashboard queries
-- directly -- no further transformation needed downstream.

with conformed as (
    select * from {{ ref('stg_qlfs_conformed') }}
),

final as (
    select
        make_date(
            year,
            case quarter
                when 1 then 1
                when 2 then 4
                when 3 then 7
                when 4 then 10
            end,
            1
        ) as period_date,
        year,
        quarter,
        metric_name,
        metric_group,
        row_category,
        current_value as value,
        qtr_change_abs,
        yoy_change_abs,
        qtr_change_pct,
        yoy_change_pct
    from conformed
)

select * from final
order by metric_name, period_date
