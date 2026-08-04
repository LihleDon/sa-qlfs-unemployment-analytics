-- Silver layer: conforms every historical row-label variant (39 of them,
-- spanning wording drift and the Q3:2025 methodology revision) onto one
-- consistent metric_name, using the seed mapping in
-- seeds/metric_label_map.csv.
--
-- Rows whose raw label isn't found in the mapping are kept (not
-- dropped) with metric_name = null, so a dbt test can catch any future
-- Stats SA release that introduces yet another new label variant we
-- haven't seen before, rather than silently losing that row.

with parsed as (
    select * from {{ source('python_silver', 'silver_qlfs_parsed') }}
),

label_map as (
    select * from {{ ref('metric_label_map') }}
),

conformed as (
    select
        parsed.year,
        parsed.quarter,
        parsed.row_label as raw_row_label,
        label_map.metric_name,
        label_map.metric_group,
        parsed.row_category,
        parsed.prior_year_value,
        parsed.prior_qtr_value,
        parsed.current_value,
        parsed.qtr_change_abs,
        parsed.yoy_change_abs,
        parsed.qtr_change_pct,
        parsed.yoy_change_pct,
        parsed.parse_success,
        parsed.parse_note,
        parsed.source_url
    from parsed
    left join label_map
        on parsed.row_label = label_map.raw_label
)

select * from conformed
