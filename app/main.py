from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.database import get_connection, initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Indoor Air Quality Monitor API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SensorReadingCreate(BaseModel):
    room_name: str = Field(examples=["Room A-101"])
    temperature_c: float = Field(ge=0, le=50)
    humidity_percent: float = Field(ge=0, le=100)
    co2_ppm: int = Field(ge=0, le=10_000)
    pm25_ug_m3: float = Field(ge=0, le=1_000)
    occupancy: int = Field(ge=0, le=500)


class AcControlUpdate(BaseModel):
    is_on: bool
    target_temperature_c: float = Field(ge=16, le=30)


def air_quality_status(co2_ppm: int, pm25_ug_m3: float) -> str:
    if co2_ppm > 1_500 or pm25_ug_m3 > 55:
        return "unhealthy"
    if co2_ppm > 1_000 or pm25_ug_m3 > 35:
        return "warning"
    return "good"


def get_room_or_404(connection, room_name: str):
    room = connection.execute(
        "SELECT id, name FROM rooms WHERE name = ?", (room_name,)
    ).fetchone()
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


def alert_messages(reading: SensorReadingCreate) -> list[tuple[str, str]]:
    messages = []
    if reading.co2_ppm > 1_500:
        messages.append(("critical", "CO2 is above 1,500 ppm. Ventilate the room immediately."))
    elif reading.co2_ppm > 1_000:
        messages.append(("warning", "CO2 is above 1,000 ppm. Consider opening doors or windows."))
    if reading.pm25_ug_m3 > 55:
        messages.append(("critical", "PM2.5 is above 55 µg/m³. Reduce exposure and check ventilation."))
    elif reading.pm25_ug_m3 > 35:
        messages.append(("warning", "PM2.5 is above 35 µg/m³."))
    return messages


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/readings", status_code=status.HTTP_201_CREATED)
def create_reading(reading: SensorReadingCreate) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        room = get_room_or_404(connection, reading.room_name)

        cursor = connection.execute(
            """
            INSERT INTO readings (
                room_id, recorded_at, temperature_c, humidity_percent,
                co2_ppm, pm25_ug_m3, occupancy
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                room["id"], timestamp, reading.temperature_c, reading.humidity_percent,
                reading.co2_ppm, reading.pm25_ug_m3, reading.occupancy,
            ),
        )
        for severity, message in alert_messages(reading):
            connection.execute(
                """
                INSERT INTO alerts (room_id, reading_id, severity, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (room["id"], cursor.lastrowid, severity, message, timestamp),
            )

    return {
        "id": cursor.lastrowid,
        "recorded_at": timestamp,
        "status": air_quality_status(reading.co2_ppm, reading.pm25_ug_m3),
    }


@app.get("/api/readings")
def list_readings(limit: int = 20) -> list[dict]:
    safe_limit = min(max(limit, 1), 100)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT r.id, room.name AS room_name, r.recorded_at, r.temperature_c,
                   r.humidity_percent, r.co2_ppm, r.pm25_ug_m3, r.occupancy
            FROM readings AS r
            JOIN rooms AS room ON room.id = r.room_id
            ORDER BY r.recorded_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return [
        {**dict(row), "status": air_quality_status(row["co2_ppm"], row["pm25_ug_m3"])}
        for row in rows
    ]


@app.get("/api/rooms/{room_name}/ac")
def get_ac_state(room_name: str) -> dict:
    with get_connection() as connection:
        room = get_room_or_404(connection, room_name)
        state = connection.execute(
            """
            SELECT is_on, target_temperature_c, updated_at
            FROM ac_states WHERE room_id = ?
            """,
            (room["id"],),
        ).fetchone()
    return {
        "room_name": room["name"],
        "is_on": bool(state["is_on"]),
        "target_temperature_c": state["target_temperature_c"],
        "updated_at": state["updated_at"],
    }


@app.put("/api/rooms/{room_name}/ac")
def update_ac_state(room_name: str, update: AcControlUpdate) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        room = get_room_or_404(connection, room_name)
        connection.execute(
            """
            UPDATE ac_states
            SET is_on = ?, target_temperature_c = ?, updated_at = ?
            WHERE room_id = ?
            """,
            (int(update.is_on), update.target_temperature_c, timestamp, room["id"]),
        )
        connection.execute(
            """
            INSERT INTO control_commands (room_id, command_type, value, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (room["id"], "ac_update", f"on={update.is_on}; target={update.target_temperature_c}", timestamp),
        )
    return {
        "room_name": room["name"],
        "is_on": update.is_on,
        "target_temperature_c": update.target_temperature_c,
        "updated_at": timestamp,
    }


@app.get("/api/alerts")
def list_alerts(limit: int = 20) -> list[dict]:
    safe_limit = min(max(limit, 1), 100)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT a.id, room.name AS room_name, a.severity, a.message, a.created_at
            FROM alerts AS a
            JOIN rooms AS room ON room.id = a.room_id
            ORDER BY a.created_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]
