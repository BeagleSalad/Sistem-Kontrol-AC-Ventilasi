"""Small SQLite data-access layer for the first project milestone."""

import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent.parent / "air_quality.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                location TEXT
            );

            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                recorded_at TEXT NOT NULL,
                temperature_c REAL NOT NULL,
                humidity_percent REAL NOT NULL,
                co2_ppm INTEGER NOT NULL,
                pm25_ug_m3 REAL NOT NULL,
                occupancy INTEGER NOT NULL,
                FOREIGN KEY (room_id) REFERENCES rooms(id)
            );

            CREATE TABLE IF NOT EXISTS ac_states (
                room_id INTEGER PRIMARY KEY,
                is_on INTEGER NOT NULL DEFAULT 0,
                target_temperature_c REAL NOT NULL DEFAULT 24.0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (room_id) REFERENCES rooms(id)
            );

            CREATE TABLE IF NOT EXISTS control_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                command_type TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (room_id) REFERENCES rooms(id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                reading_id INTEGER,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (room_id) REFERENCES rooms(id),
                FOREIGN KEY (reading_id) REFERENCES readings(id)
            );
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO rooms (name, location) VALUES (?, ?)",
            ("Room A-101", "Academic Building A"),
        )
        room = connection.execute(
            "SELECT id FROM rooms WHERE name = ?", ("Room A-101",)
        ).fetchone()
        connection.execute(
            """
            INSERT OR IGNORE INTO ac_states (room_id, is_on, target_temperature_c, updated_at)
            VALUES (?, 0, 24.0, ?)
            """,
            (room["id"], "1970-01-01T00:00:00+00:00"),
        )
