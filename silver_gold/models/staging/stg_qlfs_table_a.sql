-- Silver layer: parses Bronze's raw text values into real typed numbers.
--
-- Two row shapes exist in Table A:
--   'rate'      -- exactly 5 tokens, all comma-decimal percentages
--   'thousands' -- 7+ tokens: 3 level values (each 1 or 2 tokens,
--                 depending on magnitude) + 2 absolute changes (1 token
--                 each) + 2 percent changes (1 token each, comma-decimal)
--
-- Rows that don't match either shape are marked parse_success = false
-- rather than guessed at -- see tests/assert_no_failed_parses.sql, which
-- turns this into an automated quality gate.

with source as (
    select * from {{ source('bronze', 'bronze_qlfs_table_a') }}
),

tokenized as (
    select
        year,
        quarter,
        row_label,
        raw_value_text,
        source_url,
        string_split(raw_value_text, ' ') as tokens,
        len(string_split(raw_value_text, ' ')) as token_count
    from source
),

classified as (
    select
        *,
        case
            when token_count = 5 then 'rate'
            when token_count >= 7 then 'thousands'
            else 'unrecognized'
        end as row_category
    from tokenized
),

-- Rate rows: 5 comma-decimal values, mapped 1:1 by position.
rate_rows as (
    select
        year, quarter, row_label, row_category, source_url,
        replace(tokens[1], ',', '.')::decimal(10,2) as current_value,
        replace(tokens[2], ',', '.')::decimal(10,2) as prior_qtr_value,
        replace(tokens[3], ',', '.')::decimal(10,2) as prior_year_value,
        replace(tokens[4], ',', '.')::decimal(10,2) as qtr_change,
        replace(tokens[5], ',', '.')::decimal(10,2) as yoy_change,
        true as parse_success
    from classified
    where row_category = 'rate'
),

-- Thousands rows: peel off the last 4 tokens (2 absolute changes,
-- 2 percent changes) from the right, since those are always exactly
-- 1 token each regardless of the row's overall length.
thousands_prep as (
    select
        *,
        token_count - 4 as level_token_count,
        tokens[token_count - 3]::integer as delta_qtr_abs,
        tokens[token_count - 2]::integer as delta_yoy_abs,
        replace(tokens[token_count - 1], ',', '.')::decimal(10,2) as qtr_change_pct,
        replace(tokens[token_count], ',', '.')::decimal(10,2) as yoy_change_pct
    from classified
    where row_category = 'thousands'
),

-- Whatever tokens remain after removing the last 4 are the 3 level
-- values. If there are 3 leftover tokens, each level is 1 token
-- (no thousand separator needed). If there are 6, each level is a
-- 2-token pair that needs to be joined back into one number.
thousands_rows as (
    select
        year, quarter, row_label, row_category, source_url,
        case
            when level_token_count = 3 then tokens[1]::integer
            when level_token_count = 6 then (tokens[1] || tokens[2])::integer
        end as current_value,
        case
            when level_token_count = 3 then tokens[2]::integer
            when level_token_count = 6 then (tokens[3] || tokens[4])::integer
        end as prior_qtr_value,
        case
            when level_token_count = 3 then tokens[3]::integer
            when level_token_count = 6 then (tokens[5] || tokens[6])::integer
        end as prior_year_value,
        delta_qtr_abs::decimal(10,2) as qtr_change,
        delta_yoy_abs::decimal(10,2) as yoy_change,
        (level_token_count in (3, 6)) as parse_success
    from thousands_prep
),

unrecognized_rows as (
    -- Anything that didn't fit either shape lands here, fully
    -- preserved with nulls for the numeric columns and a false flag --
    -- never silently dropped.
    select
        year, quarter, row_label, row_category, source_url,
        cast(null as integer) as current_value,
        cast(null as integer) as prior_qtr_value,
        cast(null as integer) as prior_year_value,
        cast(null as decimal(10,2)) as qtr_change,
        cast(null as decimal(10,2)) as yoy_change,
        false as parse_success
    from classified
    where row_category = 'unrecognized'
),

unioned as (
    select year, quarter, row_label, row_category, source_url,
           current_value, prior_qtr_value, prior_year_value,
           qtr_change, yoy_change, parse_success
    from rate_rows

    union all

    select year, quarter, row_label, row_category, source_url,
           current_value, prior_qtr_value, prior_year_value,
           qtr_change, yoy_change, parse_success
    from thousands_rows

    union all

    select * from unrecognized_rows
)

select * from unioned
