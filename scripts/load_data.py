"""
Data Loading Script

This script loads CSV data from the store-monitoring-data folder into the SQLite database.
It should be run only once to avoid duplicate data loading.

The script:
1. Creates all database tables based on SQLAlchemy models
2. Reads CSV files from the data folder
3. Performs necessary column renaming for business_hours.csv
4. Loads data into the corresponding database tables
"""

import pandas as pd
from sqlalchemy import create_engine
import os
from app.models import Base
from pathlib import Path

# Get project root directory and construct database URL
ROOT = Path(__file__).parent.parent
DATABASE_URL = f"sqlite:///{ROOT/'stores.db'}"

# NOTE: Run this file only once to avoid duplicate data loading

# Create SQLite database engine
engine = create_engine(DATABASE_URL)

# Create all tables defined in the Base metadata
# This reads the model definitions and creates corresponding database tables
print("Creating all tables...")
Base.metadata.create_all(engine)
print("Tables created.")

# Path to the folder containing CSV data files
data_folder_path = "./store-monitoring-data"

try:
    # Iterate through all files in the data folder
    for file_name in os.listdir(data_folder_path):
        if file_name.endswith(".csv"):
            print(f"Loading {file_name}...")
            
            # Read CSV file into pandas DataFrame
            df = pd.read_csv(os.path.join(data_folder_path, file_name))
            
            # Handle special case: business_hours.csv has 'dayOfWeek' column
            # but our model expects 'day_of_week' (snake_case)
            if file_name == "business_hours.csv":
                df.rename(columns={'dayOfWeek': 'day_of_week'}, inplace=True)
            
            # Extract table name from filename (remove .csv extension)
            table_name = file_name[:-4]
            
            # Load DataFrame into database table
            # 'append' mode ensures we don't delete existing data on re-run
            df.to_sql(table_name, con=engine, if_exists="append", index=False)

    print("\nData loading complete.")

except FileNotFoundError as e:
    print(f"\nERROR: Could not find a required CSV file. Make sure your data is in the '{data_folder_path}' folder.")
    print(f"File not found: {e.filename}")
except Exception as e:
    print(f"\nAn error occurred during data loading: {e}")