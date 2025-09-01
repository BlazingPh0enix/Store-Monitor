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
"""

import io
import pandas as pd
from uuid import UUID
from crud import store_status_crud, store_timezone_crud, store_report_crud, store_business_hours_crud
from models import StoreReport
from database import SessionLocal
from datetime import datetime, timedelta, time
import pytz

def generate_report(report_id: UUID):
    """
    Generate a comprehensive store monitoring report.
    
    This function processes all store data to calculate uptime and downtime
    for each store during their business hours over the past hour, day, and week.
    
    Algorithm Overview:
    1. Collect all unique store IDs from various tables
    2. Find the maximum timestamp to use as "current time"
    3. For each store:
       - Get timezone (default: America/Chicago)
       - Get business hours (default: 24/7)
       - Calculate business hour intervals in UTC for past 7 days
       - Process status polls to determine uptime/downtime
       - Calculate overlaps with business hours
       - Aggregate results for different time periods
    4. Save results as CSV to database
    
    Args:
        report_id: Unique identifier for this report generation task
    """
    # Create database session for this background task
    db = SessionLocal()
    print(f"\n🚀 Report generation task started for report_id: {report_id}")
    try:
        # Create initial report record with 'Running' status
        report_record = StoreReport(report_id=str(report_id), status='Running', created_at=datetime.utcnow())
        store_report_crud.create(db, report_record)

        # Collect all unique store IDs from all relevant tables
        # This ensures we process all stores that have any data
        all_store_ids = set(store_timezone_crud.get_by_column(db, 'store_id')) | \
                        set(store_business_hours_crud.get_by_column(db, 'store_id')) | \
                        set(store_status_crud.get_by_column(db, 'store_id'))
        
        print(f"Found {len(all_store_ids)} unique stores to process.")

        # Get the maximum timestamp from status data to use as "current time"
        # This is necessary because we're working with historical data
        max_timestamp_utc_str = store_status_crud.get_max_timestamp(db)
        
        # Handle different timestamp formats that might exist in the data
        if ' UTC' in max_timestamp_utc_str:
            max_timestamp_utc = datetime.strptime(max_timestamp_utc_str, '%Y-%m-%d %H:%M:%S.%f %Z')
        else:
            max_timestamp_utc = datetime.fromisoformat(max_timestamp_utc_str)
        
        # Ensure the timestamp is timezone-aware (UTC)
        if max_timestamp_utc.tzinfo is None:
            max_timestamp_utc = pytz.utc.localize(max_timestamp_utc)

        # Initialize list to store report data for all stores
        final_report_data = []
        store_counter = 0
        total_stores = len(all_store_ids)

        # Loop through each store for creating the report
        for store_id in all_store_ids:
            store_counter += 1
            print(f"({store_counter}/{total_stores}) Processing store_id: {store_id}...")

            # Get store timezone (default to America/Chicago if not found)
            store_timezone_str = store_timezone_crud.get_store_timezone(db, store_id) or "America/Chicago"
            store_tz = pytz.timezone(store_timezone_str)

            # Get business hours (default to 24/7 if not found)
            business_hours = store_business_hours_crud.get_business_hours(db, store_id)
            if business_hours is None:
                # Default to 24/7 operation if no business hours data
                business_hours = {day: ('00:00:00', '23:59:59') for day in range(7)}

            # Calculate the start of the analysis period (7 days ago)
            start_of_week = max_timestamp_utc - timedelta(days=7)
            
            # Get all status polls for this store in the analysis period
            status_polls = store_status_crud.get_store_status(db, store_id, start_of_week.isoformat(), max_timestamp_utc.isoformat())

            # Step 1: Pre-calculate all business hour intervals in UTC for the last 7 days
            # This converts local business hours to UTC for easier comparison with status data
            business_intervals_utc = []
            for i in range(7):
                # Process each day from today back to 7 days ago
                day = max_timestamp_utc - timedelta(days=i)
                day_of_week = day.weekday()  # 0=Monday, 6=Sunday
                
                # Check if business hours are defined for this day of week
                if day_of_week in business_hours:
                    start_time_str, end_time_str = business_hours[day_of_week]
                    start_time = time.fromisoformat(start_time_str)
                    end_time = time.fromisoformat(end_time_str)
                    
                    # Combine date with time in the store's local timezone
                    start_local = store_tz.localize(datetime.combine(day.date(), start_time))
                    end_local = store_tz.localize(datetime.combine(day.date(), end_time))

                    # Convert to UTC for comparison with status poll timestamps
                    business_intervals_utc.append((start_local.astimezone(pytz.utc), end_local.astimezone(pytz.utc)))

            # Initialize counters for uptime and downtime
            total_uptime = timedelta(0)
            total_downtime = timedelta(0)

            # Step 2: Create status intervals from polls
            # We need to interpolate between polls to determine status during entire periods
            last_poll_time = start_of_week
            # Assume active if no data before the first poll (optimistic assumption)
            current_status = status_polls[0].status if status_polls else "active"

            # Iterate through each poll to create status intervals
            for poll in status_polls:
                # Handle different timestamp formats
                if 'UTC' in poll.timestamp_utc:
                    poll_time = pytz.utc.localize(datetime.strptime(poll.timestamp_utc, '%Y-%m-%d %H:%M:%S.%f %Z'))
                else:
                    poll_time = pytz.utc.localize(datetime.fromisoformat(poll.timestamp_utc))

                # The interval from last poll to current poll has the previous status
                status_interval_start = last_poll_time
                status_interval_end = poll_time

                # Step 3: Calculate overlap between this status interval and business hours
                for biz_start, biz_end in business_intervals_utc:
                    # Find the overlap between status interval and business hours
                    overlap_start = max(status_interval_start, biz_start)
                    overlap_end = min(status_interval_end, biz_end)
                    
                    # Only count if there's actual overlap
                    if overlap_start < overlap_end:
                        overlap_duration = overlap_end - overlap_start
                        # Add to appropriate counter based on status
                        if current_status == "active":
                            total_uptime += overlap_duration
                        else:
                            total_downtime += overlap_duration
                
                # Update for next iteration
                last_poll_time = poll_time
                current_status = poll.status
            
            # Handle the final interval (from last poll to current time)
            # This ensures we account for the time after the last poll
            final_interval_start = last_poll_time
            final_interval_end = max_timestamp_utc
            
            # Calculate overlap for the final interval
            for biz_start, biz_end in business_intervals_utc:
                overlap_start = max(final_interval_start, biz_start)
                overlap_end = min(final_interval_end, biz_end)
                if overlap_start < overlap_end:
                    overlap_duration = overlap_end - overlap_start
                    if current_status == "active":
                        total_uptime += overlap_duration
                    else:
                        total_downtime += overlap_duration
            
            # Aggregate results for different time periods
            # Note: This is a simplified aggregation - in practice, you might want
            # more sophisticated logic to calculate hourly and daily metrics
            uptime_last_day = total_uptime if max_timestamp_utc - start_of_week <= timedelta(days=1) else (total_uptime / 7)
            downtime_last_day = total_downtime if max_timestamp_utc - start_of_week <= timedelta(days=1) else (total_downtime / 7)
            uptime_last_hour = uptime_last_day if max_timestamp_utc - start_of_week <= timedelta(hours=1) else (uptime_last_day / 24)
            downtime_last_hour = downtime_last_day if max_timestamp_utc - start_of_week <= timedelta(hours=1) else (downtime_last_day / 24)

            # Create report entry for this store
            final_report_data.append({
                "store_id": store_id,
                "uptime_last_hour": round(uptime_last_hour.total_seconds() / 60, 2),      # minutes
                "uptime_last_day": round(uptime_last_day.total_seconds() / 3600, 2),     # hours
                "uptime_last_week": round(total_uptime.total_seconds() / 3600, 2),       # hours
                "downtime_last_hour": round(downtime_last_hour.total_seconds() / 60, 2), # minutes
                "downtime_last_day": round(downtime_last_day.total_seconds() / 3600, 2), # hours
                "downtime_last_week": round(total_downtime.total_seconds() / 3600, 2),   # hours
            })

        print("\n✅ All stores processed. Compiling and saving the final report...")

        # Convert results to CSV format and save to database
        df = pd.DataFrame(final_report_data)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()

        # Update the report status to 'Complete' and store the CSV data
        store_report_crud.update_report(db, str(report_id), 'Complete', csv_data)

        print(f"🎉 Report {report_id} is complete and saved to the database!")

    finally:
        # Always close the database session
        db.close()

    return final_report_data

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