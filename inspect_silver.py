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

con.close()
