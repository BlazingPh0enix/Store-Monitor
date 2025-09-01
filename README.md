# Store Monitoring Service

This project is a backend service designed to monitor the uptime and downtime of retail stores based on periodic status polls and their specified business hours. It provides an asynchronous API to trigger report generation and retrieve the completed reports.

## Table of Contents

- [Problem Statement](#problem-statement)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup and Installation](#setup-and-installation)
- [Running the Application](#running-the-application)
- [API Usage](#api-usage)
- [Core Logic Explanation](#core-logic-explanation)
- [Sample CSV Output](#sample-csv-output)
- [Ideas for Improvement](#ideas-for-improvement)

## Problem Statement

Restaurant owners need to monitor the operational status of their stores. This service ingests data from three sources: store status polls (UTC timestamps), local business hours, and store timezones. It then calculates an extrapolated report detailing the uptime and downtime for each store over the last hour, day, and week, considering only their business hours.

## Features

- **Asynchronous Report Generation**: The API uses background tasks to generate comprehensive reports without blocking the user.
- **RESTful API**: Provides two simple endpoints to trigger and retrieve reports.
- **Timezone-Aware Calculations**: Correctly handles conversions between UTC poll data and local business hours.
- **Data Interpolation**: Extrapolates uptime/downtime for the entire business hour window from sparse hourly polls.
- **Optimized Performance**: Uses an efficient interval-overlap calculation method.
- **Handles Missing Data**: Gracefully manages stores with missing timezone or business hour information by applying sensible defaults (America/Chicago, 24/7 respectively).

## Tech Stack

- **Backend**: Python, FastAPI
- **Database**: SQLite (for simplicity), SQLAlchemy (as ORM)
- **Data Handling**: Pandas
- **Timezone Management**: Pytz

## Project Structure

The project is organized into a clean and modular structure:
```
├── app/
│   ├── __init__.py
│   ├── crud.py          # Database Create, Read, Update operations
│   ├── database.py      # Database session and engine management
│   ├── main.py          # FastAPI application and API endpoints
│   ├── models.py        # SQLAlchemy database models
│   └── report_logic.py  # Core business logic for report calculation
├── scripts/
│   ├── __init__.py
│   └── load_data.py     # Script to load initial CSV data into the database
└── stores.db            # SQLite database file
```

## Setup and Installation

Follow these steps to set up the project locally.

### 1. Prerequisites

- Python 3.10+
- A virtual environment tool (like venv)

### 2. Clone the Repository

```bash
git clone <your-repository-url>
cd <your-repository-name>
```

### 3. Set Up Virtual Environment

Create and activate a virtual environment.

**Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

Install all the required packages from the requirements.txt file.

```bash
pip install -r requirements.txt
```

## Running the Application

The application requires a two-step process to run: first, load the data, and second, start the API server.

### Step 1: Load Initial Data

The provided CSV data needs to be loaded into the SQLite database. This is a one-time operation.

**Important**: Before running, make sure the `store-monitoring-data` folder containing the CSVs is in the project's root directory.

Run the following command from the project root directory:

```bash
python -m scripts.load_data
```

This command executes the loading script as a module, which correctly creates all necessary tables and populates them with the initial data.

### Step 2: Start the Backend Server

Once the data is loaded, you can start the FastAPI server.

Run this command from the app directory:

```bash
cd app
uvicorn main:app
```

The server will start and be accessible at http://127.0.0.1:8000. You can view the interactive API documentation (Swagger UI) by navigating to http://127.0.0.1:8000/docs.

## API Usage

The service exposes two endpoints.

### 1. Trigger a Report

This endpoint kicks off the background task to generate a new report for all stores.

**Endpoint**: `POST /trigger-report`  
**Request Body**: None

**Success Response (200 OK)**:
```json
{
  "report_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```

### 2. Get Report Status and Data

This endpoint is used to check the status of a report. Once complete, it can return the data in either CSV or JSON format.

**Endpoint**: `GET /get-report/{report_id}`

**Query Parameters**:
- `format` (optional, default: csv): Can be set to `csv` for a file download or `json` to view the data in the API response.

**Response when "Running"**:
```json
{
  "status": "Running"
}
```

**Response when "Complete" (?format=csv)**:  
This triggers a direct download of the `report_{report_id}.csv` file.

**Response when "Complete" (?format=json)**:
```json
{
  "status": "Complete",
  "data": "store_id,uptime_last_hour,uptime_last_day,uptime_last_week,downtime_last_hour,downtime_last_day,downtime_last_week\n12345,15.0,2.25,10.5,45.0,1.75,5.25\n67890,60.0,24.0,168.0,0.0,0.0,0.0\n"
}
```

## Core Logic Explanation

The report calculation is designed to be both accurate and efficient.

- **"Current Time"**: The system uses the latest timestamp found in the entire store_status dataset as a fixed "current time" for all calculations, as specified in the problem statement.

- **Data Handling**: A master list of all unique store IDs is compiled from all three data sources to ensure no store is missed. Default values (24/7 business hours, America/Chicago timezone) are applied if specific data is missing for a store.

- **Optimized Calculation**: Instead of a slow, minute-by-minute check, the logic uses an efficient interval overlap algorithm. It creates time intervals for store activity (e.g., "active" from 10:15 to 11:30) and calculates their mathematical overlap with pre-calculated business hour intervals. This method is orders of magnitude faster.

## Sample CSV Output

A sample CSV file generated by the service can be found here:

[Sample Report](https://drive.google.com/file/d/1k-jRD-cP2N0NZCzD14VQ7Ikyn6Qb5PF7/view?usp=sharing)

## Ideas for Improvement

While this solution fulfills the assignment requirements, a production-grade system could be enhanced in several ways:

- **Use a Production Database**: Replace SQLite with a more robust database like PostgreSQL, which offers better concurrency, scalability, and timezone support.

- **Implement a Dedicated Task Queue**: For better reliability and scalability, replace FastAPI's simple BackgroundTasks with a dedicated task queue system like Celery backed by a message broker such as Redis or RabbitMQ. This would prevent task loss if the server restarts and allows for distributed workers.

- **Database Indexing**: Add a composite index to the store_status table on the (store_id, timestamp_utc) columns to significantly speed up data retrieval for each store.

- **Caching**: Store frequently accessed, static data like business hours and timezones in a caching layer like Redis to reduce database load.

- **Containerization**: Package the application and its dependencies into Docker containers and use Docker Compose to manage the service and its database, ensuring consistent environments and simplifying deployment.

- **Authentication**: Secure the API endpoints with an authentication mechanism, such as API keys or OAuth2, to control access.