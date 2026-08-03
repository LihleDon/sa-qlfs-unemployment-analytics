"""
Silver layer, stage 1: parses Bronze's raw text values into real typed
numbers and writes the result to a new DuckDB table, silver_qlfs_parsed.

WHY PYTHON, NOT dbt SQL:
Stats SA uses a space as its thousands separator, so a single number
like 41,691 is stored as two whitespace tokens ("41" "691") -- and a
row's total token count varies depending on the magnitude of that
quarter's numbers. Reconstructing "how many tokens belong to each
value" requires a small stateful greedy algorithm that is far clearer
as a Python loop than as nested SQL CASE expressions. Everything
downstream of this (label conformance, Gold aggregation) goes back to
being dbt SQL, where it belongs.

TWO BUGS FIXED HERE (found via manual verification against the source
PDF -- see project notes):
1. Column order: the source table reads oldest -> newest, left to right
   (prior year, prior quarter, current). An earlier version of this
   pipeline had this backwards.
2. Absolute change values (not just levels) can also span 2 tokens when
   a metric moves by more than 1,000 (thousand) in a single quarter --
   this happened during the 2022 post-COVID recovery period.

KNOWN, DOCUMENTED LIMITATION:
"Formal sector*" / "Informal sector*" rows for 2025 Q3 - 2026 Q1 have
genuinely incomplete source data -- Stats SA only published partial
comparisons during their Q3:2025 methodology change (marked with '*'
in their own report). These are handled with explicit, narrow logic
below rather than guessed at generically.
"""
import re
import duckdb

DB_PATH = "data/warehouse.duckdb"

NUMERIC_TOKEN = re.compile(r"^-?\d+(,\d+)?$")
CONTINUATION_TOKEN = re.compile(r"^\d{3}$")


def reconstruct_fields(tokens: list[str], num_fields: int) -> list[str]:
    """
    Greedily reconstructs `num_fields` values from a flat list of
    whitespace-separated tokens, where a value may be split across
    multiple tokens by a thousands-separator space (e.g. "41" "691").

    A token is treated as a continuation of the current value only if
    it's exactly 3 digits AND merging it still leaves enough tokens to
    fill every remaining field with at least one token. This lookahead
    check is what prevents over-merging into a later field's tokens.
    """
    fields = []
    i = 0
    n = len(tokens)
    for field_idx in range(num_fields):
        remaining_after = num_fields - field_idx - 1
        current = tokens[i]
        i += 1
        while (
            i < n
            and CONTINUATION_TOKEN.match(tokens[i])
            and (n - i - 1) >= remaining_after
        ):
            current += tokens[i]
            i += 1
        fields.append(current)
    return fields


def to_decimal(token: str) -> float:
    return float(token.replace(",", "."))


def parse_row(row_label: str, raw_value_text: str) -> dict:
    tokens = raw_value_text.split()
    result = {
        "row_category": None,
        "prior_year_value": None,
        "prior_qtr_value": None,
        "current_value": None,
        "qtr_change_abs": None,
        "yoy_change_abs": None,
        "qtr_change_pct": None,
        "yoy_change_pct": None,
        "parse_success": False,
        "parse_note": None,
    }

    is_rate = len(tokens) == 5 and all(
        NUMERIC_TOKEN.match(t) and "," in t for t in tokens
    )

    if is_rate:
        result["row_category"] = "rate"
        result["prior_year_value"] = to_decimal(tokens[0])
        result["prior_qtr_value"] = to_decimal(tokens[1])
        result["current_value"] = to_decimal(tokens[2])
        result["qtr_change_pct"] = to_decimal(tokens[3])
        result["yoy_change_pct"] = to_decimal(tokens[4])
        result["parse_success"] = True
        return result

    if len(tokens) >= 7 and all(NUMERIC_TOKEN.match(t) for t in tokens):
        result["row_category"] = "thousands"
        pct_tokens = tokens[-2:]
        core_tokens = tokens[:-2]
        fields = reconstruct_fields(core_tokens, 5)
        result["prior_year_value"] = int(fields[0])
        result["prior_qtr_value"] = int(fields[1])
        result["current_value"] = int(fields[2])
        result["qtr_change_abs"] = int(fields[3])
        result["yoy_change_abs"] = int(fields[4])
        result["qtr_change_pct"] = to_decimal(pct_tokens[0])
        result["yoy_change_pct"] = to_decimal(pct_tokens[1])
        result["parse_success"] = True
        return result

    # Documented exception: transitional "sector*" rows with genuinely
    # incomplete source data (see module docstring).
    if "*" in row_label and all(NUMERIC_TOKEN.match(t) for t in tokens):
        result["row_category"] = "thousands_partial"
        if len(tokens) == 2:
            result["current_value"] = int(tokens[0] + tokens[1])
            result["parse_success"] = True
            result["parse_note"] = (
                "Only current-quarter value published; source gives no "
                "prior comparison during the Q3:2025 methodology change."
            )
        elif len(tokens) == 6:
            result["prior_qtr_value"] = int(tokens[0] + tokens[1])
            result["current_value"] = int(tokens[2] + tokens[3])
            result["qtr_change_abs"] = int(tokens[4])
            result["qtr_change_pct"] = to_decimal(tokens[5])
            result["parse_success"] = True
            result["parse_note"] = (
                "Only quarter-to-quarter comparison available; no "
                "year-on-year figures published during the methodology "
                "transition."
            )
        else:
            result["row_category"] = "unrecognized"
            result["parse_note"] = f"Unexpected token count for a '*' row: {len(tokens)}"
        return result

    result["row_category"] = "unrecognized"
    result["parse_note"] = f"Did not match any known row shape ({len(tokens)} tokens)"
    return result


def run():
    con = duckdb.connect(DB_PATH)
    bronze_rows = con.execute(
        "SELECT year, quarter, row_label, raw_value_text, source_url FROM bronze_qlfs_table_a"
    ).fetchall()

    parsed_rows = []
    for year, quarter, row_label, raw_value_text, source_url in bronze_rows:
        parsed = parse_row(row_label, raw_value_text)
        parsed_rows.append((
            year, quarter, row_label, source_url,
            parsed["row_category"],
            parsed["prior_year_value"], parsed["prior_qtr_value"], parsed["current_value"],
            parsed["qtr_change_abs"], parsed["yoy_change_abs"],
            parsed["qtr_change_pct"], parsed["yoy_change_pct"],
            parsed["parse_success"], parsed["parse_note"],
        ))

    con.execute("""
        CREATE TABLE IF NOT EXISTS silver_qlfs_parsed (
            year INTEGER, quarter INTEGER, row_label VARCHAR, source_url VARCHAR,
            row_category VARCHAR,
            prior_year_value DOUBLE, prior_qtr_value DOUBLE, current_value DOUBLE,
            qtr_change_abs DOUBLE, yoy_change_abs DOUBLE,
            qtr_change_pct DOUBLE, yoy_change_pct DOUBLE,
            parse_success BOOLEAN, parse_note VARCHAR
        )
    """)
    con.execute("DELETE FROM silver_qlfs_parsed")  # idempotent, same as Bronze
    con.executemany(
        """INSERT INTO silver_qlfs_parsed VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        parsed_rows,
    )

    total = len(parsed_rows)
    failed = sum(1 for r in parsed_rows if r[12] is False)
    print(f"Parsed {total} rows -- {total - failed} succeeded, {failed} failed/unrecognized")
    con.close()


if __name__ == "__main__":
    run()
