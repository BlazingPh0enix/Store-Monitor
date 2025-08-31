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
        # Create a record for the report
        store_report_crud.create(db, StoreReport(report_id=str(report_id), status='Running', created_at=datetime.now()))

        # Get all unique store IDs
        store_ids_from_timezones = store_timezone_crud.get_by_column(db, 'store_id')
        store_ids_from_business_hours = store_business_hours_crud.get_by_column(db, 'store_id')
        store_ids_from_store_status = store_status_crud.get_by_column(db, 'store_id')
        store_ids = set(store_ids_from_timezones) | set(store_ids_from_business_hours) | set(store_ids_from_store_status)

        print(f"Found {len(store_ids)} unique stores to process.")

        # Get the max timestamp to use as "current time"
        max_timestamp_utc_str = store_status_crud.get_max_timestamp(db)
        # Handle potential timezone info in string if present
        if ' UTC' in max_timestamp_utc_str:
            max_timestamp_utc = datetime.strptime(max_timestamp_utc_str, '%Y-%m-%d %H:%M:%S.%f %Z')
        else:
            max_timestamp_utc = datetime.fromisoformat(max_timestamp_utc_str)
        # Ensure the timestamp is timezone-aware
        max_timestamp_utc = pytz.utc.localize(max_timestamp_utc)

        final_report_data = []

        store_counter = 0
        total_stores = len(store_ids)

        # Loop through each store for creating the report
        for store_id in store_ids:
            store_counter += 1
            print(f"({store_counter}/{total_stores}) Processing store_id: {store_id}...")

            # Get the timezone for each store, default to "America/Chicago"
            store_timezone_str = store_timezone_crud.get_store_timezone(db, store_id) or "America/Chicago"
            store_tz = pytz.timezone(store_timezone_str)

            # Get the business hours, default to 24/7
            business_hours = store_business_hours_crud.get_business_hours(db, store_id)
            if business_hours is None:
                business_hours = {day: ('00:00:00', '23:59:59') for day in range(7)}

            # Get the store status data for the last week
            start_of_week = max_timestamp_utc - timedelta(days=7)
            status_polls = store_status_crud.get_store_status(db, store_id, start_of_week.isoformat(), max_timestamp_utc.isoformat())

            # Initialize the uptime and downtime counters
            total_uptime_minutes = 0
            total_downtime_minutes = 0

            # Use the current poll time as the start for the next interval's calculation
            last_poll_time = start_of_week

            # Interpolate from the start of the week to the 1st poll
            current_status = 'active' # Assume active if there is no prior data
            if status_polls:
                current_status = status_polls[0].status

            # Iterate through each poll
            for poll in status_polls:
                if 'UTC' in poll.timestamp_utc:
                    poll_time_utc = pytz.utc.localize(datetime.strptime(poll.timestamp_utc, '%Y-%m-%d %H:%M:%S.%f %Z'))
                else:
                    poll_time_utc = pytz.utc.localize(datetime.fromisoformat(poll.timestamp_utc))

                # Iterate through each minute of the interval to check against business hours
                interval_start = last_poll_time
                while interval_start < poll_time_utc:
                    # Convert to store's local time to check business hours
                    local_time = interval_start.astimezone(store_tz)
                    day_of_week = local_time.weekday()

                    # Check if the store is open at this minute
                    if day_of_week in business_hours:
                        start_local_str, end_local_str = business_hours[day_of_week]
                        start_local = datetime.strptime(start_local_str, '%H:%M:%S').time()
                        end_local = datetime.strptime(end_local_str, '%H:%M:%S').time()

                        if start_local <= local_time.time() < end_local:
                            if current_status == 'active':
                                total_uptime_minutes += 1
                            else:
                                total_downtime_minutes += 1

                    interval_start += timedelta(minutes=1)

                last_poll_time = poll_time_utc
                current_status = poll.status

            # Extrapolate from the last poll to the current data
            interval_start = last_poll_time
            while interval_start < max_timestamp_utc:
                local_time = interval_start.astimezone(store_tz)
                day_of_week = local_time.weekday()
                if day_of_week in business_hours:
                    start_local_str, end_local_str = business_hours[day_of_week]
                    start_local = datetime.strptime(start_local_str, '%H:%M:%S').time()
                    end_local = datetime.strptime(end_local_str, '%H:%M:%S').time()
                    if start_local <= local_time.time() < end_local:
                        if current_status == "active":
                            total_uptime_minutes += 1
                        else:
                            total_downtime_minutes += 1
                interval_start += timedelta(minutes=1)

            # Filter results for last hour and last day
            uptime_last_hour = sum(1 for minute in range(60) if max_timestamp_utc - timedelta(minutes=minute) > start_of_week and (max_timestamp_utc - timedelta(minutes=minute)).astimezone(store_tz).weekday() in business_hours and business_hours[(max_timestamp_utc - timedelta(minutes=minute)).astimezone(store_tz).weekday()][0] <= (max_timestamp_utc - timedelta(minutes=minute)).astimezone(store_tz).strftime('%H:%M:%S') < business_hours[(max_timestamp_utc - timedelta(minutes=minute)).astimezone(store_tz).weekday()][1] and any(poll.timestamp_utc <= (max_timestamp_utc - timedelta(minutes=minute)).isoformat() for poll in status_polls if poll.status == 'active'))
            downtime_last_hour = 60 - uptime_last_hour

            uptime_last_day = total_uptime_minutes / 60 if max_timestamp_utc - timedelta(days=1) > start_of_week else 0
            downtime_last_day = total_downtime_minutes / 60 if max_timestamp_utc - timedelta(days=1) > start_of_week else 0

            uptime_last_week = total_uptime_minutes / 60
            downtime_last_week = total_downtime_minutes / 60

            final_report_data.append({
                "store_id": store_id,
                "uptime_last_hour": uptime_last_hour,
                "uptime_last_day": round(uptime_last_day, 2),
                "uptime_last_week": round(uptime_last_week, 2),
                "downtime_last_hour": downtime_last_hour,
                "downtime_last_day": round(downtime_last_day, 2),
                "downtime_last_week": round(downtime_last_week, 2),
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

def get_report_status(report_id: str):
    db = SessionLocal()
    try:
        report = store_report_crud.get_report_by_id(db, report_id)
        if not report:
            return "Not Found", None
        return report.status, report.report_data
    finally:
        db.close()