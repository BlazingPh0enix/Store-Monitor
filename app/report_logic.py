"""
Report Generation Logic

This module contains the core business logic for generating store monitoring reports.
It calculates uptime and downtime for stores based on polling data, business hours,
and timezone information for the past hour, day, and week.

The main algorithm:
1. Get all unique store IDs from the database
2. For each store, determine timezone and business hours
3. Calculate business hour intervals in UTC for the past 7 days
4. Process status polls to create status intervals
5. Calculate overlap between status intervals and business hours
6. Aggregate uptime/downtime for different time periods

Functions:
    process_single_store: Worker function to calculate metrics for a single store
    generate_report_parallel: Orchestrator function to manage parallel report generation
    get_report_status: Retrieve current status and data of a report
"""

import io
import pandas as pd
from uuid import UUID
from crud import store_status_crud, store_timezone_crud, store_report_crud, store_business_hours_crud
from models import StoreReport
from database import SessionLocal
from datetime import datetime, timedelta, time
import pytz
import concurrent.futures
import time as timer

# --- WORKER FUNCTION ---
# This function contains the logic to process exactly ONE store.
# It's designed to be run in a separate process.
def process_single_store(args: tuple):
    """
    Calculates uptime and downtime metrics for a single store.
    
    This worker function is designed to run in parallel processes and calculates
    store metrics based on business hours, timezone, and status polling data.
    
    Args:
        args: Tuple containing (store_id, max_timestamp_utc)
            - store_id: Unique identifier for the store
            - max_timestamp_utc: Maximum timestamp to calculate metrics up to
    
    Returns:
        dict: Store metrics containing:
            - store_id: Store identifier
            - uptime_last_hour: Minutes of uptime in the last hour
            - uptime_last_day: Hours of uptime in the last day
            - uptime_last_week: Hours of uptime in the last week
            - downtime_last_hour: Minutes of downtime in the last hour
            - downtime_last_day: Hours of downtime in the last day
            - downtime_last_week: Hours of downtime in the last week
    """
    store_id, max_timestamp_utc = args
    
    # Each parallel process must create its own database session.
    db = SessionLocal()
    try:
        store_timezone_str = store_timezone_crud.get_store_timezone(db, store_id) or "America/Chicago"
        store_tz = pytz.timezone(store_timezone_str)

        business_hours = store_business_hours_crud.get_business_hours(db, store_id)
        if business_hours is None:
            business_hours = {day: ('00:00:00', '23:59:59') for day in range(7)}

        start_of_week = max_timestamp_utc - timedelta(days=7)
        status_polls = store_status_crud.get_store_status(db, store_id, start_of_week.isoformat(), max_timestamp_utc.isoformat())

        business_intervals_utc = []
        for i in range(7):
            day = max_timestamp_utc - timedelta(days=i)
            day_of_week = day.weekday()
            if day_of_week in business_hours:
                start_time_str, end_time_str = business_hours[day_of_week]
                start_time = time.fromisoformat(start_time_str)
                end_time = time.fromisoformat(end_time_str)
                start_local = store_tz.localize(datetime.combine(day.date(), start_time))
                end_local = store_tz.localize(datetime.combine(day.date(), end_time))
                business_intervals_utc.append((start_local.astimezone(pytz.utc), end_local.astimezone(pytz.utc)))

        total_uptime = timedelta(0)
        total_downtime = timedelta(0)

        last_poll_time = start_of_week
        current_status = status_polls[0].status if status_polls else "active"

        for poll in status_polls:
            if ' UTC' in poll.timestamp_utc:
                poll_time = datetime.strptime(poll.timestamp_utc, '%Y-%m-%d %H:%M:%S.%f %Z')
            else:
                poll_time = datetime.fromisoformat(poll.timestamp_utc)
            if poll_time.tzinfo is None:
                poll_time = pytz.utc.localize(poll_time)

            status_interval_start = last_poll_time
            status_interval_end = poll_time

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
        
        for biz_start, biz_end in business_intervals_utc:
            overlap_start = max(last_poll_time, biz_start)
            overlap_end = min(max_timestamp_utc, biz_end)
            if overlap_start < overlap_end:
                overlap_duration = overlap_end - overlap_start
                if current_status == "active":
                    total_uptime += overlap_duration
                else:
                    total_downtime += overlap_duration

        uptime_last_day = total_uptime if max_timestamp_utc - start_of_week <= timedelta(days=1) else (total_uptime / 7)
        downtime_last_day = total_downtime if max_timestamp_utc - start_of_week <= timedelta(days=1) else (total_downtime / 7)
        uptime_last_hour = uptime_last_day if max_timestamp_utc - start_of_week <= timedelta(hours=1) else (uptime_last_day / 24)
        downtime_last_hour = downtime_last_day if max_timestamp_utc - start_of_week <= timedelta(hours=1) else (downtime_last_day / 24)

        return {
            "store_id": store_id,
            "uptime_last_hour": round(uptime_last_hour.total_seconds() / 60, 2),
            "uptime_last_day": round(uptime_last_day.total_seconds() / 3600, 2),
            "uptime_last_week": round(total_uptime.total_seconds() / 3600, 2),
            "downtime_last_hour": round(downtime_last_hour.total_seconds() / 60, 2),
            "downtime_last_day": round(downtime_last_day.total_seconds() / 3600, 2),
            "downtime_last_week": round(total_downtime.total_seconds() / 3600, 2),
        }
    finally:
        db.close()

# --- ORCHESTRATOR FUNCTION ---
# This function replaces the old generate_report function.
def generate_report_parallel(report_id: UUID):
    """
    Orchestrates parallel report generation for all stores.
    
    This function manages the entire report generation process by:
    1. Creating a report record with 'Running' status
    2. Collecting all unique store IDs from the database
    3. Distributing store processing across multiple processes
    4. Compiling results into a CSV report
    5. Updating the report status to 'Complete' or 'Error'
    
    Args:
        report_id: Unique identifier for the report being generated
        
    Note:
        This function runs asynchronously and updates the database with
        progress and final results. It uses ProcessPoolExecutor for
        parallel processing of individual stores.
    """

    start_time = timer.time() # Start timer for performance measurement

    db = SessionLocal()
    print(f"\n🚀 Parallel report generation task started for report_id: {report_id}")
    try:
        report_record = StoreReport(report_id=str(report_id), status='Running', created_at=datetime.utcnow())
        store_report_crud.create(db, report_record)

        all_store_ids = list(set(store_timezone_crud.get_by_column(db, 'store_id')) | \
                        set(store_business_hours_crud.get_by_column(db, 'store_id')) | \
                        set(store_status_crud.get_by_column(db, 'store_id')))
        print(f"Found {len(all_store_ids)} unique stores to process.")

        max_timestamp_utc_str = store_status_crud.get_max_timestamp(db)
        if ' UTC' in max_timestamp_utc_str:
            max_timestamp_utc = datetime.strptime(max_timestamp_utc_str, '%Y-%m-%d %H:%M:%S.%f %Z')
        else:
            max_timestamp_utc = datetime.fromisoformat(max_timestamp_utc_str)
        if max_timestamp_utc.tzinfo is None:
            max_timestamp_utc = pytz.utc.localize(max_timestamp_utc)

        tasks = [(store_id, max_timestamp_utc) for store_id in all_store_ids]

        results = []
        with concurrent.futures.ProcessPoolExecutor() as executor:
            for i, result in enumerate(executor.map(process_single_store, tasks), start=1):
                print(f"({i}/{len(tasks)}) Processing store id: {tasks[i-1][0]}")
                results.append(result)

        final_report_data = [res for res in results if res is not None]

        print("\n✅ All stores processed. Compiling and saving the final report...")
        total_time = timer.time() - start_time
        print(f"🕒 Report generation completed in {total_time:.2f} seconds.")
        df = pd.DataFrame(final_report_data)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()

        store_report_crud.update_report(db, str(report_id), 'Complete', csv_data)
        print(f"🎉 Report {report_id} is complete and saved to the database!")
        
    except Exception as e:
        print(f"\n❌ An error occurred during report generation: {e}")
        store_report_crud.update_report(db, str(report_id), 'Error', str(e))
    finally:
        db.close()

def get_report_status(report_id: str) -> tuple[str, str | None]:
    """
    Retrieve the current status and data of a report.
    
    This function checks the database for a report's current status
    and returns the data if the report is complete.
    
    Args:
        report_id: Unique identifier for the report
        
    Returns:
        tuple: (status, data) where:
            - status: 'Running', 'Complete', or 'Not Found'
            - data: CSV content if complete, None otherwise
    """
    # Create a new database session for this query
    db = SessionLocal()
    try:
        # Look up the report by ID
        report = store_report_crud.get_report_by_id(db, report_id)
        if not report:
            return "Not Found", None
        
        # Return status and data (data will be None if not complete)
        return str(report.status), str(report.report_data)
    finally:
        # Always close the database session
        db.close()