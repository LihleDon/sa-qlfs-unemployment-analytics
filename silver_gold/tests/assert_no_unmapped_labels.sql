-- Singular test: fails if any row's raw label isn't found in
-- seeds/metric_label_map.csv. This is the explicit, purpose-built
-- version of the not_null test on metric_name -- kept separate because
-- if this ever fails, the fix is obvious and specific: add the new
-- label variant to the seed CSV. A future Stats SA release changing
-- wording again (as they did for Q3:2025) should be caught here, not
-- discovered downstream in a broken dashboard chart.
--
-- Passes when this returns zero rows (dbt's rule for all singular tests).

select
    raw_row_label,
    count(*) as occurrences
from {{ ref('stg_qlfs_conformed') }}
where metric_name is null
group by raw_row_label
