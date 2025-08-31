import io
import pandas as pd
from uuid import UUID
from crud import store_status_crud, store_timezone_crud, store_report_crud, store_business_hours_crud
from models import StoreReport
from database import SessionLocal
from datetime import datetime, timedelta, time
import pytz

def generate_report(report_id: UUID):
    db = SessionLocal()
    print(f"\n🚀 Report generation task started for report_id: {report_id}")
    try:
        report_record = StoreReport(report_id=str(report_id), status='Running', created_at=datetime.utcnow())
        store_report_crud.create(db, report_record)

        all_store_ids = set(store_timezone_crud.get_by_column(db, 'store_id')) | \
                        set(store_business_hours_crud.get_by_column(db, 'store_id')) | \
                        set(store_status_crud.get_by_column(db, 'store_id'))
        
        print(f"Found {len(all_store_ids)} unique stores to process.")

        max_timestamp_utc_str = store_status_crud.get_max_timestamp(db)
        if ' UTC' in max_timestamp_utc_str:
            max_timestamp_utc = datetime.strptime(max_timestamp_utc_str, '%Y-%m-%d %H:%M:%S.%f %Z')
        else:
            max_timestamp_utc = datetime.fromisoformat(max_timestamp_utc_str)
        
        if max_timestamp_utc.tzinfo is None:
            max_timestamp_utc = pytz.utc.localize(max_timestamp_utc)

        final_report_data = []
        store_counter = 0
        total_stores = len(all_store_ids)

        # Loop through each store for creating the report
        for store_id in all_store_ids:
            store_counter += 1
            print(f"({store_counter}/{total_stores}) Processing store_id: {store_id}...")

            store_timezone_str = store_timezone_crud.get_store_timezone(db, store_id) or "America/Chicago"
            store_tz = pytz.timezone(store_timezone_str)

            business_hours = store_business_hours_crud.get_business_hours(db, store_id)
            if business_hours is None:
                business_hours = {day: ('00:00:00', '23:59:59') for day in range(7)}

            start_of_week = max_timestamp_utc - timedelta(days=7)
            status_polls = store_status_crud.get_store_status(db, store_id, start_of_week.isoformat(), max_timestamp_utc.isoformat())

            # Step 1: Pre-calculate all business hour intervals in UTC for the last 7 days
            business_intervals_utc = []
            for i in range(7):
                day = max_timestamp_utc - timedelta(days=i)
                day_of_week = day.weekday()
                if day_of_week in business_hours:
                    start_time_str, end_time_str = business_hours[day_of_week]
                    start_time = time.fromisoformat(start_time_str)
                    end_time = time.fromisoformat(end_time_str)
                    
                    # Combine date with time in the store's local timezone
                    start_local = store_tz.localize(datetime.combine(day.date(), start_time))
                    end_local = store_tz.localize(datetime.combine(day.date(), end_time))

                    # Convert to UTC for comparison
                    business_intervals_utc.append((start_local.astimezone(pytz.utc), end_local.astimezone(pytz.utc)))

            total_uptime = timedelta(0)
            total_downtime = timedelta(0)

            # Step 2: Create status intervals from polls
            last_poll_time = start_of_week
            # Assume active if no data before the first poll
            current_status = status_polls[0].status if status_polls else "active"

            # Iterate through each poll
            for poll in status_polls:
                if 'UTC' in poll.timestamp_utc:
                    poll_time = pytz.utc.localize(datetime.strptime(poll.timestamp_utc, '%Y-%m-%d %H:%M:%S.%f %Z'))
                else:
                    poll_time = pytz.utc.localize(datetime.fromisoformat(poll.timestamp_utc))

                # Iterate through each minute of the interval to check against business hours
                status_interval_start = last_poll_time
                status_interval_end = poll_time

                # Step 3: Calculate overlap for this interval
                for biz_start, biz_end in business_intervals_utc:
                    overlap_start = max(status_interval_start, biz_start)
                    overlap_end = min(status_interval_end, biz_end)
                    
                    if overlap_start < overlap_end:
                        overlap_duration = overlap_end - overlap_start
                        if current_status == "active":
                            total_uptime += overlap_duration
                        else:
                            total_downtime += overlap_duration
                
                last_poll_time = poll_time
                current_status = poll.status
            
            # Handle the final interval (from last poll to current time)
            final_interval_start = last_poll_time
            final_interval_end = max_timestamp_utc
            for biz_start, biz_end in business_intervals_utc:
                overlap_start = max(final_interval_start, biz_start)
                overlap_end = min(final_interval_end, biz_end)
                if overlap_start < overlap_end:
                    overlap_duration = overlap_end - overlap_start
                    if current_status == "active":
                        total_uptime += overlap_duration
                    else:
                        total_downtime += overlap_duration
            
            # Aggregate results
            uptime_last_day = total_uptime if max_timestamp_utc - start_of_week <= timedelta(days=1) else (total_uptime / 7)
            downtime_last_day = total_downtime if max_timestamp_utc - start_of_week <= timedelta(days=1) else (total_downtime / 7)
            uptime_last_hour = uptime_last_day if max_timestamp_utc - start_of_week <= timedelta(hours=1) else (uptime_last_day / 24)
            downtime_last_hour = downtime_last_day if max_timestamp_utc - start_of_week <= timedelta(hours=1) else (downtime_last_day / 24)

            final_report_data.append({
                "store_id": store_id,
                "uptime_last_hour": round(uptime_last_hour.total_seconds() / 60, 2),
                "uptime_last_day": round(uptime_last_day.total_seconds() / 3600, 2),
                "uptime_last_week": round(total_uptime.total_seconds() / 3600, 2),
                "downtime_last_hour": round(downtime_last_hour.total_seconds() / 60, 2),
                "downtime_last_day": round(downtime_last_day.total_seconds() / 3600, 2),
                "downtime_last_week": round(total_downtime.total_seconds() / 3600, 2),
            })

        print("\n✅ All stores processed. Compiling and saving the final report...")

        # Convert to CSV and update the report status
        df = pd.DataFrame(final_report_data)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()

        store_report_crud.update_report(db, str(report_id), 'Complete', csv_data)

        print(f"🎉 Report {report_id} is complete and saved to the database!")

    finally:
        db.close()

    return final_report_data

def get_report_status(report_id: str) -> tuple[str, str | None]:
    db = SessionLocal()
    try:
        report = store_report_crud.get_report_by_id(db, report_id)
        if not report:
            return "Not Found", None
        return str(report.status), str(report.report_data)
    finally:
        db.close()