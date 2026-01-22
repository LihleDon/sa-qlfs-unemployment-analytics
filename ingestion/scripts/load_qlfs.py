import pandas as pd
import os

RAW_DIR = "data/raw"
BRONZE_DIR = "data/bronze"
os.makedirs(BRONZE_DIR, exist_ok=True)

# Example: process one file (repeat for multiple quarters)
file = "P0211Q3-2025.xlsx"  
xl = pd.ExcelFile(os.path.join(RAW_DIR, file))

# Typical tables: Unemployment by province, by age, etc.
df_prov = pd.read_excel(xl, sheet_name="Table 3.1", skiprows=3)  # adjust skiprows & sheet per file
df_prov['quarter'] = '2025Q3'  # add quarter identifier
df_prov.to_parquet(f"{BRONZE_DIR}/province_unemployment.parquet")

# Repeat for age, gender, population group tables
print("Bronze layer created!")