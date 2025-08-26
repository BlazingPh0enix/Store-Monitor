from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class StoreStatus(Base):
    __tablename__ = "store_status"

    store_id = Column(String, primary_key=True)
    status = Column(String, nullable=False)
    timestamp_utc = Column(DateTime, nullable=False)

class BusinessHours(Base):
    __tablename__ = "business_hours"

    store_id = Column(String, primary_key=True)
    day_of_week = Column(Integer, nullable=False)
    start_time_local = Column(DateTime, nullable=False)
    end_time_local = Column(DateTime, nullable=False)

class TimeZones(Base):
    __tablename__ = "time_zones"

    store_id = Column(String, primary_key=True)
    time_zone = Column(String, nullable=False)