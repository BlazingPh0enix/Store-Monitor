from sqlalchemy import func
from sqlalchemy.orm import Session
from models import StoreStatus, TimeZones, StoreReport, BusinessHours

class CRUDBase:
    def __init__(self, model):
        self.model = model

    def create(self, db: Session, obj_in):
        db.add(obj_in)
        db.commit()
        db.refresh(obj_in)
        return obj_in

    def get_all(self, db: Session):
        return db.query(self.model).all()

    def get_by_column(self, db: Session, column_name: str) -> list:
        results = db.query(getattr(self.model, column_name)).distinct().all()
        return [item[0] for item in results]

class StoreReportCRUD(CRUDBase):

    def get_report_by_id(self, db: Session, report_id: str) -> StoreReport | None:
        return db.query(self.model).filter(self.model.report_id == report_id).first()
    
    def update_report(self, db: Session, report_id: str, status: str, data: str):
        report = self.get_report_by_id(db, report_id)
        if report:
            setattr(report, 'status', status)
            setattr(report, 'report_data', data)
            db.commit()
            db.refresh(report)
        return report

class StoreStatusCRUD(CRUDBase):

    def get_store_status(self, db: Session, store_id: int, start_time: str, end_time: str):
        return db.query(self.model).filter(
            self.model.store_id == store_id,
            self.model.timestamp_utc >= start_time,
            self.model.timestamp_utc <= end_time
        ).order_by(self.model.timestamp_utc).all()

    def get_max_timestamp(self, db: Session) -> str:
        result = db.query(func.max(self.model.timestamp_utc)).scalar()
        return result

class StoreTimezoneCRUD(CRUDBase):

    def get_store_timezone(self, db: Session, store_id: int) -> str | None:
        result = db.query(self.model).filter(self.model.store_id == store_id).first()
        return result.timezone_str if result else None

class StoreBusinessHoursCRUD(CRUDBase):

    def get_business_hours(self, db: Session, store_id: int) -> dict[int, tuple] | None:
        results = db.query(self.model).filter(self.model.store_id == store_id).all()
        if not results:
            return None
        return {result.day_of_week: (result.start_time_local, result.end_time_local) for result in results}

store_status_crud = StoreStatusCRUD(StoreStatus)
store_timezone_crud = StoreTimezoneCRUD(TimeZones)
store_report_crud = StoreReportCRUD(StoreReport)
store_business_hours_crud = StoreBusinessHoursCRUD(BusinessHours)