import pandas as pd
import os
import re  # for extracting quarter from filename

# Paths (relative to project root)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
BRONZE_DIR = os.path.join(BASE_DIR, "data", "bronze")
os.makedirs(BRONZE_DIR, exist_ok=True)

# List all your Excel files
excel_files = [f for f in os.listdir(RAW_DIR) if f.endswith('.xlsx') and f.startswith('QLFS_')]

for file_name in excel_files:
    file_path = os.path.join(RAW_DIR, file_name)
    
    # Extract quarter/year from filename, e.g. QLFS_Q3_2025.xlsx → 2025Q3
    match = re.search(r'Q(\d)_(\d{4})', file_name)
    if match:
        quarter_num, year = match.groups()
        quarter = f"{year}Q{quarter_num}"
    else:
        quarter = "Unknown"
        print(f"Could not parse quarter from {file_name}")
        continue
    
    print(f"Processing {file_name} as {quarter}...")
    
    xl = pd.ExcelFile(file_path)
    
    # TRY DIFFERENT SHEETS & SKIPROWS - open the Excel in Excel app to check exact sheet name & headers
    # Common starting points from Stats SA QLFS:
    # - Sheet: "Table E" or "Unemployment rate by province" or "Appendix 1" or main content sheet
    # - Often skiprows=3 to 10 to skip titles/headers
    
    # Example 1: Try province unemployment (adjust sheet_name and skiprows after testing)
    try:
        # CHANGE THESE TWO LINES BASED ON YOUR FILE:
        sheet_name = "Table E"          # ← Open Excel → look at sheet tabs → common: "Table E", "Table 2.3", or "Sheet1"
        skip = 5                        # ← Number of rows to skip (try 3,4,5,6,7 until headers look right like "Province", "Rate")
        
        df_prov = pd.read_excel(xl, sheet_name=sheet_name, skiprows=skip)
        
        # Clean up: assume first columns are Province, then rates/figures
        df_prov = df_prov.iloc[:, :10]  # keep first 10 cols for safety
        df_prov.columns = df_prov.columns.str.strip()  # clean column names
        
        # Add quarter
        df_prov['quarter'] = quarter
        
        # Save as parquet (efficient format)
        output_path = os.path.join(BRONZE_DIR, f"province_unemployment_{quarter}.parquet")
        df_prov.to_parquet(output_path, index=False)
        print(f"Saved: {output_path}")
    
    except Exception as e:
        print(f"Error on {file_name} sheet '{sheet_name}': {e}")
        print("→ Open the Excel file → find the sheet with unemployment by province → note exact sheet name and how many rows to skip (until you see 'Province', 'Unemployment rate' etc.)")
        print("Then edit sheet_name and skip above and re-run.\n")

print("\nAll files processed! Check data/bronze/ folder.")