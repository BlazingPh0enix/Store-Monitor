"""
Database Configuration

This module sets up the SQLAlchemy database engine and session management
for the store monitoring application using SQLite as the database backend.
"""

from sqlalchemy.engine import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path

# Get the root directory of the project (parent of the app directory)
ROOT = Path(__file__).parent.parent

# SQLite database URL pointing to stores.db in the project root
DATABASE_URL = f"sqlite:///{ROOT/'stores.db'}"

# Create database engine with SQLite-specific configuration
# check_same_thread=False allows multiple threads to use the same connection
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create session factory with recommended settings
# autocommit=False: transactions must be explicitly committed
# autoflush=False: changes aren't automatically flushed to database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Database dependency for FastAPI endpoints.
    
    This function creates a database session for each request and ensures
    proper cleanup after the request is completed. It's used as a dependency
    in FastAPI route handlers.
    
    Yields:
        Session: SQLAlchemy database session
    """
    # Create a new database session
    db = SessionLocal()
    try:
        # Yield the session to the requesting function
        yield db
    finally:
        # Ensure the session is closed even if an exception occurs
        db.close()