"""
Store Monitoring API

This FastAPI application provides endpoints for generating and retrieving store monitoring reports.
The reports analyze store uptime/downtime based on polling data, business hours, and timezone information.
"""

import io
from typing import Literal
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from uuid import uuid4
from report_logic import generate_report, get_report_status
from database import get_db
import uvicorn

# Initialize FastAPI application
app = FastAPI(
    title="Store Monitoring API",
    description="API for generating store uptime/downtime monitoring reports",
    version="1.0.0"
)

@app.post('/trigger-report')
async def trigger_report(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Trigger the generation of a store monitoring report.
    
    This endpoint initiates the background task to generate a comprehensive report
    analyzing store uptime and downtime for the past hour, day, and week.
    
    Args:
        background_tasks: FastAPI background tasks handler
        db: Database session dependency
        
    Returns:
        dict: Contains the unique report_id for tracking report status
    """
    # Generate a unique report identifier
    report_id = uuid4()
    
    # Add the report generation task to background queue
    background_tasks.add_task(generate_report, report_id)
    
    return {"report_id": str(report_id)}

@app.get('/get-report/{report_id}')
def get_report(
    report_id: str,
    format: Literal['csv', 'json'] = 'csv'
    ):
    """
    Retrieve the status and data of a previously triggered report.
    
    This endpoint allows users to check the status of their report and download
    the results once the report generation is complete.
    
    Args:
        report_id: Unique identifier for the report
        format: Output format - 'csv' for downloadable file, 'json' for API response
        
    Returns:
        StreamingResponse: CSV file download when format='csv' and report is complete
        dict: JSON response with status and data when format='json'
        
    Raises:
        HTTPException: 404 if report_id is not found
    """
    # Get the current status and data for the requested report
    status, data = get_report_status(report_id)

    # Return 404 if the report ID doesn't exist
    if status == "Not Found":
        raise HTTPException(status_code=404, detail="Report ID not found.")
    
    # If report generation is complete, return the data in requested format
    if status == "Complete":
        # If the user wants a downloadable CSV file
        if format == 'csv':
            return StreamingResponse(
                io.StringIO(data),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=report_{report_id}.csv"}
            )
        # If the user wants to view the data as JSON
        elif format == 'json':
            return {"status": status, "data": data}
    
    # If report is still running, return status only
    return {"status": status}

if __name__ == "__main__":
    # Run the application with uvicorn server
    # host="0.0.0.0" makes it accessible from all network interfaces
    # port=8000 is the default development port
    # reload=True enables auto-restart on code changes during development
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)