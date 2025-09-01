"""
CRUD Operations

This module provides Create, Read, Update operations for all database models.
It implements a base CRUD class with common operations and specialized classes
for each model with their specific query methods.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session
from models import StoreStatus, TimeZones, StoreReport, BusinessHours

class CRUDBase:
    """
    Base CRUD class providing common database operations.
    
    This class implements generic CRUD operations that can be used
    for any SQLAlchemy model. Specific model classes can inherit
    from this class and add their own specialized methods.
    """
    
    def __init__(self, model):
        """
        Initialize CRUD operations for a specific model.
        
        Args:
            model: SQLAlchemy model class
        """
        self.model = model

    def create(self, db: Session, obj_in):
        """
        Create a new record in the database.
        
        Args:
            db: Database session
            obj_in: Model instance to create
            
        Returns:
            Created model instance with database-generated fields
        """
        db.add(obj_in)
        db.commit()
        db.refresh(obj_in)
        return obj_in

    def get_all(self, db: Session):
        """
        Retrieve all records for this model.
        
        Args:
            db: Database session
            
        Returns:
            List of all model instances
        """
        return db.query(self.model).all()

    def get_by_column(self, db: Session, column_name: str) -> list:
        """
        Get all unique values from a specific column.
        
        This method is useful for getting lists of unique store IDs,
        timezones, etc.
        
        Args:
            db: Database session
            column_name: Name of the column to retrieve values from
            
        Returns:
            List of unique values from the specified column
        """
        results = db.query(getattr(self.model, column_name)).distinct().all()
        return [item[0] for item in results]

class StoreReportCRUD(CRUDBase):
    """
    CRUD operations specific to StoreReport model.
    
    This class handles operations related to report generation tracking,
    including retrieving reports by ID and updating report status and data.
    """

    def get_report_by_id(self, db: Session, report_id: str) -> StoreReport | None:
        """
        Retrieve a specific report by its ID.
        
        Args:
            db: Database session
            report_id: Unique report identifier
            
        Returns:
            StoreReport instance if found, None otherwise
        """
        return db.query(self.model).filter(self.model.report_id == report_id).first()
    
    def update_report(self, db: Session, report_id: str, status: str, data: str):
        """
        Update the status and data of an existing report.
        
        This method is used to mark reports as complete and store the
        generated CSV data.
        
        Args:
            db: Database session
            report_id: Unique report identifier
            status: New status ('Running', 'Complete', 'Failed')
            data: Report data (CSV content when complete)
            
        Returns:
            Updated StoreReport instance if found, None otherwise
        """
        report = self.get_report_by_id(db, report_id)
        if report:
            setattr(report, 'status', status)
            setattr(report, 'report_data', data)
            db.commit()
            db.refresh(report)
        return report

class StoreStatusCRUD(CRUDBase):
    """
    CRUD operations specific to StoreStatus model.
    
    This class handles operations related to store status polling data,
    including retrieving status records within time ranges and finding
    the latest timestamp in the dataset.
    """

    def get_store_status(self, db: Session, store_id: int, start_time: str, end_time: str):
        """
        Retrieve store status records within a specific time range.
        
        This method is used to get all status polls for a store between
        two timestamps, ordered chronologically.
        
        Args:
            db: Database session
            store_id: Store identifier
            start_time: Start timestamp (ISO format)
            end_time: End timestamp (ISO format)
            
        Returns:
            List of StoreStatus records ordered by timestamp
        """
        return db.query(self.model).filter(
            self.model.store_id == store_id,
            self.model.timestamp_utc >= start_time,
            self.model.timestamp_utc <= end_time
        ).order_by(self.model.timestamp_utc).all()

    def get_max_timestamp(self, db: Session) -> str:
        """
        Get the latest timestamp from all store status records.
        
        This is used to determine the "current time" for report generation
        since we're working with historical data.
        
        Args:
            db: Database session
            
        Returns:
            Latest timestamp string from the dataset
        """
        result = db.query(func.max(self.model.timestamp_utc)).scalar()
        return result

class StoreTimezoneCRUD(CRUDBase):
    """
    CRUD operations specific to TimeZones model.
    
    This class handles operations related to store timezone information,
    used for converting between UTC and local times.
    """

    def get_store_timezone(self, db: Session, store_id: int) -> str | None:
        """
        Retrieve the timezone string for a specific store.
        
        Args:
            db: Database session
            store_id: Store identifier
            
        Returns:
            Timezone string if found, None if no timezone data exists
            (caller should default to 'America/Chicago')
        """
        result = db.query(self.model).filter(self.model.store_id == store_id).first()
        return result.timezone_str if result else None

class StoreBusinessHoursCRUD(CRUDBase):
    """
    CRUD operations specific to BusinessHours model.
    
    This class handles operations related to store business hours,
    used for determining when stores should be operational.
    """

    def get_business_hours(self, db: Session, store_id: int) -> dict[int, tuple] | None:
        """
        Retrieve business hours for a specific store.
        
        Args:
            db: Database session
            store_id: Store identifier
            
        Returns:
            Dictionary mapping day_of_week (0-6) to (start_time, end_time) tuples
            Returns None if no business hours data exists for the store
            (caller should default to 24/7 operation)
        """
        results = db.query(self.model).filter(self.model.store_id == store_id).all()
        if not results:
            return None
        return {result.day_of_week: (result.start_time_local, result.end_time_local) for result in results}

# Create instances of CRUD classes for use throughout the application
store_status_crud = StoreStatusCRUD(StoreStatus)
store_timezone_crud = StoreTimezoneCRUD(TimeZones)
store_report_crud = StoreReportCRUD(StoreReport)
store_business_hours_crud = StoreBusinessHoursCRUD(BusinessHours)