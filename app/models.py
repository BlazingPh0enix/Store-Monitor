"""
SQLAlchemy ORM Models

This module defines the database schema for the store monitoring system.
It includes models for store status, business hours, timezones, and generated reports.
"""

from sqlalchemy import Column, DateTime, Integer, String, JSON
from sqlalchemy.orm import DeclarativeBase

# Base class for all SQLAlchemy ORM models
class Base(DeclarativeBase):
    """Base class for all database models using SQLAlchemy's DeclarativeBase."""
    pass

class StoreStatus(Base):
    """
    Model for store status polling data.
    
    This table stores the periodic polls (roughly every hour) indicating
    whether each store was active or inactive at a specific timestamp.
    All timestamps are stored in UTC format.
    """
    __tablename__ = "store_status"

    # Primary key - auto-incrementing ID
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Store identifier
    store_id = Column(String)
    
    # Status of the store: 'active' or 'inactive'
    status = Column(String, nullable=False)
    
    # Timestamp when the status was recorded (UTC format)
    timestamp_utc = Column(String, nullable=False)

class BusinessHours(Base):
    """
    Model for store business hours.
    
    This table defines the operating hours for each store on different days of the week.
    Times are stored in the store's local timezone.
    If no data exists for a store, it's assumed to be open 24/7.
    """
    __tablename__ = "business_hours"
    
    # Primary key - auto-incrementing ID
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Store identifier
    store_id = Column(String)
    
    # Day of week (0=Monday, 1=Tuesday, ..., 6=Sunday)
    day_of_week = Column(Integer, nullable=False)
    
    # Opening time in local timezone (HH:MM:SS format)
    start_time_local = Column(String, nullable=False)
    
    # Closing time in local timezone (HH:MM:SS format)
    end_time_local = Column(String, nullable=False)

class TimeZones(Base):
    """
    Model for store timezone information.
    
    This table maps each store to its local timezone for proper time calculations.
    If no data exists for a store, 'America/Chicago' is assumed as default.
    """
    __tablename__ = "timezones"

    # Store identifier - also serves as primary key
    store_id = Column(String, primary_key=True)
    
    # Timezone string (e.g., 'America/New_York', 'America/Chicago')
    timezone_str = Column(String, nullable=False)

class StoreReport(Base):
    """
    Model for storing generated reports and their status.
    
    This table tracks the status of report generation tasks and stores
    the final CSV data once reports are completed.
    """
    __tablename__ = "store_report"

    # Unique report identifier - serves as primary key
    report_id = Column(String, primary_key=True)
    
    # Report status: 'Running', 'Complete', or 'Failed'
    status = Column(String, nullable=False)
    
    # Generated report data stored as JSON (CSV content when complete)
    report_data = Column(JSON, nullable=True)
    
    # Timestamp when the report generation was initiated
    created_at = Column(DateTime, nullable=False)