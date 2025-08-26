import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session
import os

# NOTE: Run this file only once to avoid duplicate data loading

class Base(DeclarativeBase):
    pass

# Create SQLite database engine
engine = create_engine("sqlite:///stores.db")

# Create all tables defined in the Base metadata
Base.metadata.create_all(engine)

data_folder_path = "./store-monitoring-data"

with Session(engine) as session:
    # Iterate through all files in the data folder
    for file_name in os.listdir(data_folder_path):
        if file_name.endswith(".csv"):
            file_path = os.path.join(data_folder_path, file_name)
            df = pd.read_csv(file_path)
            
            # Load CSV data into database table (table name = filename without .csv)
            df.to_sql(file_name[:-4], con=engine, if_exists="replace", index=False)

            print(f"Loaded {file_name} into database.")
            session.commit()