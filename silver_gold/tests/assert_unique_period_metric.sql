-- Singular test: fails if any (period_date, metric_name) combination
-- appears more than once. This would mean either duplicate Bronze
-- ingestion or a many-to-one join gone wrong upstream -- either way,
-- the dashboard should never show two conflicting values for the same
-- metric in the same quarter.
--
-- Passes when this returns zero rows.

select
    period_date,
    metric_name,
    count(*) as occurrences
from {{ ref('mart_qlfs_time_series') }}
group by period_date, metric_name
having count(*) > 1
