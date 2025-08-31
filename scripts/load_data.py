import pandas as pd
from sqlalchemy import create_engine
import os
from app.models import Base
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATABASE_URL = f"sqlite:///{ROOT/'stores.db'}"

# NOTE: Run this file only once to avoid duplicate data loading

# Create SQLite database engine
engine = create_engine(DATABASE_URL)

# Create all tables defined in the Base metadata
print("Creating all tables...")
Base.metadata.create_all(engine)
print("Tables created.")

data_folder_path = "./store-monitoring-data"

try:
    # Iterate through all files in the data folder
    for file_name in os.listdir(data_folder_path):
        if file_name.endswith(".csv"):
            df = pd.read_csv(os.path.join(data_folder_path, file_name))
            if file_name == "business_hours.csv":
                df.rename(columns={'dayOfWeek': 'day_of_week'}, inplace=True)
            # Use 'append' to avoid deleting data on re-run
            df.to_sql(file_name[:-4], con=engine, if_exists="append", index=False)

    print("\nData loading complete.")

except FileNotFoundError as e:
    print(f"\nERROR: Could not find a required CSV file. Make sure your data is in the '{data_folder_path}' folder.")
    print(f"File not found: {e.filename}")
except Exception as e:
    print(f"\nAn error occurred during data loading: {e}")