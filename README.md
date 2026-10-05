# Indoor Air Quality Monitor

A simulated IoT system for monitoring the air quality of a university classroom.

## Included

- FastAPI backend with a health check, readings, alerts, and AC-control APIs
- SQLite storage for rooms and sensor readings
- Python simulator that posts a reading every 10 seconds

## Setup

In PowerShell, from this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the backend

```powershell
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation. The health check is `GET /health`.

## Run the simulator

With the backend still running, open a second PowerShell window:

```powershell
.\.venv\Scripts\Activate.ps1
py simulator.py
```

The simulator posts a reading for `Room A-101` every 10 seconds. View stored readings at `GET /api/readings`.

## Run the dashboard

In a third PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open the local address Vite displays (normally `http://localhost:5173`). Keep the backend and simulator running while using the dashboard.

## Controls and alerts

The virtual AC starts off with a 24°C target. Use the interactive documentation to call `PUT /api/rooms/{room_name}/ac` with, for example:

```json
{"is_on": true, "target_temperature_c": 23}
```

The simulator uses this state for subsequent temperature readings. CO₂ above 1,000 ppm or PM2.5 above 35 µg/m³ creates a stored alert, available at `GET /api/alerts`.
