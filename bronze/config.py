"""
Configuration for the Bronze ingestion layer.

Centralizes file paths and pipeline parameters so nothing is hardcoded
inside the ingestion logic itself. Reads from .env.
"""
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / os.getenv("DATA_DIR", "data")
RAW_PDF_DIR = DATA_DIR / "raw_pdfs"
DUCKDB_PATH = DATA_DIR / os.getenv("DUCKDB_FILE", "warehouse.duckdb")

# Create folders automatically so a fresh clone of this repo works
# without the user having to manually set up directories first.
RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.statssa.gov.za/publications/P0211"
START_YEAR = 2022
END_YEAR = 2026

QUARTER_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}

# NOTE ON SCHEMA DRIFT:
# Stats SA revised the QLFS questionnaire in Q3:2025, changing several row
# labels in Table A ("Not economically active" -> "Outside the Labour Force",
# "Private households" -> "Household sector", new LU2-LU4 indicators added,
# etc). A fixed list of expected labels breaks the moment the source
# changes wording. Instead, Bronze detects data rows STRUCTURALLY (any
# line ending in a run of numbers), so it doesn't care what the label text
# says. Reconciling old vs new label names into one consistent metric set
# happens later, in Silver.
