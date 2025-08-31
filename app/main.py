import io
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from uuid import uuid4
from report_logic import generate_report, get_report_status
from database import get_db
import uvicorn

app = FastAPI()

@app.post('/trigger-report')
async def trigger_report(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    report_id = uuid4()
    background_tasks.add_task(generate_report, report_id)
    return {"report_id": str(report_id)}

@app.get('/get-report/{report_id}')
def get_report(report_id: str):
    status, data = get_report_status(report_id)
    if status == "Not Found":
        raise HTTPException(status_code=404, detail="Report ID not found")

    if status == "Complete":
        return StreamingResponse(
            io.StringIO(data),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=report_{report_id}.csv"}
        )
    return {"status": status}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)