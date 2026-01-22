import pandas as pd
from pathlib import Path
import re

RAW_DATA_PATH = Path("data/raw")
BRONZE_DATA_PATH = Path("data/bronze")

BRONZE_DATA_PATH.mkdir(parents=True, exist_ok=True)

def extract_year_quarter(filename: str):
    """
    Handles filenames like:
    QLFS_Q1_2025.xlsx
    QLFS_Q4_2024.xlsx
    QLFS_Q4 _2024.xlsx
    QLFS_Q4 2024.xlsx
    """
    cleaned = filename.replace(" ", "")
    match = re.search(r"Q([1-4])_(\d{4})", cleaned)

    if not match:
        raise ValueError(f"Cannot extract quarter/year from filename: {filename}")

    quarter, year = match.groups()
    return int(year), f"Q{quarter}"


def load_excel(file_path: Path):
    df = pd.read_excel(file_path)

    # Clean column names
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    # Drop junk unnamed columns from Excel
    df = df.loc[:, ~df.columns.str.startswith("unnamed")]

    # Force object columns to string (Arrow-safe)
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str)

    return df


def main():
    all_dfs = []

    for file in RAW_DATA_PATH.glob("*.xlsx"):
        print(f"Processing: {file.name}")
        year, quarter = extract_year_quarter(file.name)

        df = load_excel(file)
        df["year"] = year
        df["quarter"] = quarter
        df["source_file"] = file.name

        all_dfs.append(df)

    final_df = pd.concat(all_dfs, ignore_index=True)

    output_file = BRONZE_DATA_PATH / "qlfs_bronze.parquet"
    final_df.to_parquet(output_file, engine="pyarrow", index=False)

    print("===================================")
    print("Bronze ingestion complete")
    print(f"Rows: {len(final_df):,}")
    print(f"Saved to: {output_file}")
    print("===================================")

if __name__ == "__main__":
    main()
