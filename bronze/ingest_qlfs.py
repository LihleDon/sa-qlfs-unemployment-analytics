"""
Bronze layer: Ingests Stats SA QLFS 'Table A' statistical releases.

Downloads the official quarterly P0211 PDF release, locates the page
containing Table A ('Key labour market indicators'), and extracts each
row's raw, unparsed text exactly as it appears in the source document.

Design principle: this script does NOT clean, split, or interpret the
numbers. It lands raw text into Bronze untouched. All parsing/cleaning
of the space-separated, comma-decimal numbers happens in Silver (dbt),
where it can be tested and validated properly.
"""
import logging
import re
from datetime import datetime, timezone

import duckdb
import pdfplumber
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    BASE_URL,
    DUCKDB_PATH,
    END_YEAR,
    QUARTER_ORDINALS,
    RAW_PDF_DIR,
    START_YEAR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

TABLE_MARKER = "Key labour market indicators"
STOP_MARKER = "Due to rounding"

# Some government/corporate servers silently block requests that don't
# look like they're coming from a real browser (default python-requests
# headers are an easy giveaway). We mimic a standard browser request here
# to avoid being served a block page instead of the real PDF.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def build_release_list():
    """Builds the (year, quarter, url) list for every release we want to ingest."""
    releases = []
    for year in range(START_YEAR, END_YEAR + 1):
        for quarter in range(1, 5):
            # Skip quarters that can't have been released yet.
            if year == END_YEAR and quarter > 2:
                continue
            ordinal = QUARTER_ORDINALS[quarter]
            filename = f"P0211{ordinal}Quarter{year}.pdf"
            url = f"{BASE_URL}/{filename}"
            releases.append({"year": year, "quarter": quarter, "url": url, "filename": filename})
    return releases


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def download_pdf(url: str, destination) -> bool:
    """
    Downloads a single PDF release with automatic retries.

    Returns True if downloaded successfully, False if the release doesn't
    exist yet (404) -- expected for future/unreleased quarters, not an
    error worth crashing the whole pipeline over.
    """
    if destination.exists():
        logger.info(f"Already downloaded, skipping: {destination.name}")
        return True

    response = requests.get(url, timeout=30, headers=REQUEST_HEADERS)
    if response.status_code == 404:
        logger.warning(f"Release not found (likely not published yet): {url}")
        return False
    response.raise_for_status()

    # Belt-and-braces check: some servers return 200 OK with an HTML
    # "not found" page instead of a real 404. A genuine PDF always starts
    # with the bytes %PDF -- if this one doesn't, treat it the same as a
    # missing release rather than saving corrupt data.
    if not response.content.startswith(b"%PDF"):
        logger.warning(
            f"Response for {url} was not a real PDF (likely not published yet) -- skipping"
        )
        return False

    destination.write_bytes(response.content)
    logger.info(f"Downloaded: {destination.name}")
    return True


def find_table_a_text(pdf_path):
    """
    Scans the PDF page by page and returns the raw text of the page
    containing Table A. Returns None if not found -- schema drift
    protection: we'd rather skip a release than silently ingest the
    wrong page.

    We require BOTH the table marker AND the word "Population" on the
    same page. The marker text alone isn't enough -- it also appears in
    the table of contents, which would otherwise be matched first.
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if TABLE_MARKER in text and "Population" in text:
                return text
    return None


# A token counts as a raw numeric value if it's purely digits, with an
# optional leading minus sign and/or a comma-decimal (Stats SA uses commas
# as decimal points, e.g. "32,9"). Anything else -- words, footnote
# markers, "LU1-", "15-64" -- is treated as part of the label.
NUMERIC_TOKEN = re.compile(r"^-?\d+(,\d+)?$")


def parse_table_a_rows(raw_text: str, year: int, quarter: int, source_url: str):
    """
    Splits Table A's raw text into one row per labour market indicator.

    Detects data rows STRUCTURALLY rather than by a fixed label list:
    for each line, tokens are walked backward from the end. Pure-number
    tokens are collected as the row's raw values; the moment a
    non-numeric token is hit, everything before it is treated as the
    row's label. Lines with no trailing numbers (headers, footnotes,
    section titles) are automatically discarded.

    Does NOT attempt to interpret the numbers themselves (e.g. splitting
    "41 691" into a single value) -- that's Silver's job, where it can
    be done with proper validation and test coverage.

    Known limitation: two rows in the post-Q3:2025 schema (LU2, LU3) wrap
    their labels across two lines with the numbers sandwiched in between,
    due to the PDF's column layout. They are intentionally excluded here
    rather than guessed at -- a documented scoping decision, not a bug.
    """
    # Only process the table itself, not the footnotes below it.
    stop_idx = raw_text.find(STOP_MARKER)
    table_only_text = raw_text[:stop_idx] if stop_idx != -1 else raw_text

    rows = []
    for line in table_only_text.split("\n"):
        tokens = line.strip().split()
        if not tokens:
            continue

        value_tokens = []
        boundary = len(tokens)
        for token in reversed(tokens):
            if NUMERIC_TOKEN.match(token):
                value_tokens.insert(0, token)
                boundary -= 1
            else:
                break

        label = " ".join(tokens[:boundary]).strip()
        raw_value_text = " ".join(value_tokens).strip()

        # Discard non-data lines: headers, section titles, footnotes --
        # anything missing either a label or a value isn't a real row.
        if not label or not raw_value_text:
            continue

        rows.append({
            "year": year,
            "quarter": quarter,
            "row_label": label,
            "raw_value_text": raw_value_text,
            "source_url": source_url,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })

    return rows


def load_to_bronze(all_rows):
    """Creates (if needed) and loads the bronze table in DuckDB."""
    con = duckdb.connect(str(DUCKDB_PATH))
    con.execute("""
        CREATE TABLE IF NOT EXISTS bronze_qlfs_table_a (
            year INTEGER,
            quarter INTEGER,
            row_label VARCHAR,
            raw_value_text VARCHAR,
            source_url VARCHAR,
            ingested_at VARCHAR
        )
    """)
    # Idempotency: wipe and reload rather than appending duplicates on
    # reruns. Re-running this script should always be safe.
    con.execute("DELETE FROM bronze_qlfs_table_a")
    con.executemany(
        """INSERT INTO bronze_qlfs_table_a
           (year, quarter, row_label, raw_value_text, source_url, ingested_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [(r["year"], r["quarter"], r["row_label"], r["raw_value_text"],
          r["source_url"], r["ingested_at"]) for r in all_rows]
    )
    count = con.execute("SELECT COUNT(*) FROM bronze_qlfs_table_a").fetchone()[0]
    logger.info(f"Loaded {count} rows into bronze_qlfs_table_a")
    con.close()


def run(test_single_release: bool = False):
    releases = build_release_list()

    if test_single_release:
        # Not every "expected" quarter is published yet, so search backwards
        # from most recent until we find one that actually exists.
        logger.info("TEST MODE: searching backwards for the most recent published release")
        releases = list(reversed(releases))

    all_rows = []
    for release in releases:
        destination = RAW_PDF_DIR / release["filename"]
        success = download_pdf(release["url"], destination)
        if not success:
            continue

        table_text = find_table_a_text(destination)
        if table_text is None:
            logger.warning(f"Table A not found in {release['filename']} -- skipping")
            continue

        rows = parse_table_a_rows(table_text, release["year"], release["quarter"], release["url"])
        all_rows.extend(rows)

        if test_single_release:
            logger.info(f"TEST MODE: successfully parsed {release['filename']}, stopping here")
            break

    if not all_rows:
        logger.error("No rows extracted across any release. Nothing loaded.")
        return

    load_to_bronze(all_rows)


if __name__ == "__main__":
    run(test_single_release=True)
