"""
Quick diagnostic queries against the Silver layer. Run with:
    python inspect_silver.py
"""
import duckdb

con = duckdb.connect("data/warehouse.duckdb")

print("\n=== Parse success/failure counts ===")
print(con.execute("""
    SELECT row_category, parse_success, COUNT(*) as row_count
    FROM silver_qlfs_parsed
    GROUP BY 1, 2
    ORDER BY 1, 2
""").fetchdf().to_string())

print("\n=== Remaining unrecognized rows (should be 0 now) ===")
print(con.execute("""
    SELECT year, quarter, row_label, parse_note
    FROM silver_qlfs_parsed
    WHERE row_category = 'unrecognized'
    ORDER BY year, quarter, row_label
""").fetchdf().to_string())

print("\n=== Population row across all quarters (sanity check) ===")
print(con.execute("""
    SELECT year, quarter, row_label, prior_year_value, prior_qtr_value,
           current_value, qtr_change_abs, yoy_change_abs
    FROM silver_qlfs_parsed
    WHERE row_label LIKE 'Population%'
    ORDER BY year, quarter
""").fetchdf().to_string())

print("\n=== Unemployment rate across all quarters (cross-check vs known public figures) ===")
print(con.execute("""
    SELECT year, quarter, row_label, prior_year_value, prior_qtr_value,
           current_value, qtr_change_pct, yoy_change_pct
    FROM silver_qlfs_parsed
    WHERE row_label LIKE '%Unemployment rate%'
    ORDER BY year, quarter
""").fetchdf().to_string())

print("\n=== Rows with NO metric_name match (should be empty) ===")
print(con.execute("""
    SELECT DISTINCT raw_row_label
    FROM main_silver.stg_qlfs_conformed
    WHERE metric_name IS NULL
""").fetchdf().to_string())

print("\n=== Metric coverage: quarters per metric_name (spot the gaps) ===")
print(con.execute("""
    SELECT metric_name, metric_group, COUNT(*) as quarters_present
    FROM main_silver.stg_qlfs_conformed
    GROUP BY 1, 2
    ORDER BY 2, 1
""").fetchdf().to_string())

print("\n=== Gold layer: unemployment_rate time series (final dashboard-ready shape) ===")
print(con.execute("""
    SELECT period_date, value, qtr_change_pct, yoy_change_pct
    FROM main_gold.mart_qlfs_time_series
    WHERE metric_name = 'unemployment_rate'
    ORDER BY period_date
""").fetchdf().to_string())

con.close()
