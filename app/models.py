from sqlalchemy import Column, DateTime, Integer, String, JSON
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class StoreStatus(Base):
    __tablename__ = "store_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String)
    status = Column(String, nullable=False)
    timestamp_utc = Column(String, nullable=False)

class BusinessHours(Base):
    __tablename__ = "business_hours"
    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String)
    day_of_week = Column(Integer, nullable=False)
    start_time_local = Column(String, nullable=False)
    end_time_local = Column(String, nullable=False)

class TimeZones(Base):
    __tablename__ = "timezones"

    store_id = Column(String, primary_key=True)
    timezone_str = Column(String, nullable=False)

class StoreReport(Base):
    __tablename__ = "store_report"

    report_id = Column(String, primary_key=True)
    status = Column(String, nullable=False)
    report_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)