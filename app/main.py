import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, Field

from app.database import get_connection

app = FastAPI(title="Indoor Air Quality Monitor API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
password_hash = PasswordHash.recommended()
bearer = HTTPBearer()
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-demo-secret-before-deployment")

class Login(BaseModel): username: str; password: str
class Reading(BaseModel):
    temperature_c: float = Field(ge=0, le=50); humidity_percent: float = Field(ge=0, le=100)
    co2_ppm: int = Field(ge=0, le=10000); pm25_ug_m3: float = Field(ge=0, le=1000); occupancy: int = Field(ge=0, le=500)
class AcUpdate(BaseModel): is_on: bool; target_temperature_c: float = Field(ge=16, le=30)

def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        data = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as error: raise HTTPException(401, "Invalid or expired access token") from error
    with get_connection() as db:
        user = db.execute("SELECT id, username, role, assigned_room_id FROM users WHERE id=%s AND is_active=TRUE", (data["sub"],)).fetchone()
    if not user: raise HTTPException(401, "User is not active")
    return user

def room_for_user(room_name, user):
    with get_connection() as db:
        room = db.execute("SELECT id,name FROM rooms WHERE name=%s", (room_name,)).fetchone()
    if not room: raise HTTPException(404, "Room not found")
    if user["role"] != "admin" and user["assigned_room_id"] != room["id"]: raise HTTPException(403, "You are not authorized for this room")
    return room

def quality(co2, pm25): return "unhealthy" if co2 > 1500 or pm25 > 55 else "warning" if co2 > 1000 or pm25 > 35 else "good"

@app.get("/health")
def health(): return {"status": "ok", "database": "postgresql"}

@app.post("/api/auth/login")
def login(body: Login):
    with get_connection() as db:
        user = db.execute("SELECT id, username, password_hash, role, assigned_room_id FROM users WHERE username=%s AND is_active=TRUE", (body.username,)).fetchone()
    if not user or not password_hash.verify(body.password, user["password_hash"]): raise HTTPException(401, "Incorrect username or password")
    token = jwt.encode({"sub": str(user["id"]), "exp": datetime.now(timezone.utc)+timedelta(hours=8)}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "role": user["role"], "username": user["username"]}

@app.get("/api/auth/me")
def me(user=Depends(current_user)): return user

@app.post("/api/readings", status_code=201)
def create_reading(reading: Reading, x_device_id: str = Header(), x_api_key: str = Header()):
    with get_connection() as db:
        device = db.execute("SELECT id,room_id,api_key_hash FROM devices WHERE device_name=%s AND is_active=TRUE", (x_device_id,)).fetchone()
        if not device or not password_hash.verify(x_api_key, device["api_key_hash"]): raise HTTPException(401, "Invalid device credentials")
        now = datetime.now(timezone.utc)
        row = db.execute("INSERT INTO readings (device_id,room_id,recorded_at,temperature_c,humidity_percent,co2_ppm,pm25_ug_m3,occupancy) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id", (device["id"],device["room_id"],now,reading.temperature_c,reading.humidity_percent,reading.co2_ppm,reading.pm25_ug_m3,reading.occupancy)).fetchone()
        alerts = []
        if reading.co2_ppm > 1500: alerts.append(("critical", "CO2 above 1,500 ppm. Ventilate immediately."))
        elif reading.co2_ppm > 1000: alerts.append(("warning", "CO2 above 1,000 ppm."))
        if reading.pm25_ug_m3 > 55: alerts.append(("critical", "PM2.5 above 55 µg/m³."))
        elif reading.pm25_ug_m3 > 35: alerts.append(("warning", "PM2.5 above 35 µg/m³."))
        for severity, message in alerts:
            db.execute("INSERT INTO alerts(room_id,reading_id,severity,message) VALUES(%s,%s,%s,%s)", (device["room_id"],row["id"],severity,message))
    return {"id": row["id"], "status": quality(reading.co2_ppm, reading.pm25_ug_m3)}

@app.get("/api/readings")
def readings(limit: int=20, user=Depends(current_user)):
    sql = "SELECT r.*, rooms.name room_name FROM readings r JOIN rooms ON rooms.id=r.room_id" + (" WHERE r.room_id=%s" if user["role"] != "admin" else "") + " ORDER BY recorded_at DESC LIMIT %s"
    args = (user["assigned_room_id"], min(max(limit,1),100)) if user["role"] != "admin" else (min(max(limit,1),100),)
    with get_connection() as db: rows = db.execute(sql,args).fetchall()
    return [{**row, "status": quality(row["co2_ppm"],row["pm25_ug_m3"])} for row in rows]

@app.get("/api/alerts")
def alerts(limit: int=20, user=Depends(current_user)):
    sql = "SELECT alerts.*, rooms.name room_name FROM alerts JOIN rooms ON rooms.id=alerts.room_id" + (" WHERE alerts.room_id=%s" if user["role"] != "admin" else "") + " ORDER BY created_at DESC LIMIT %s"
    args = (user["assigned_room_id"], min(max(limit,1),100)) if user["role"] != "admin" else (min(max(limit,1),100),)
    with get_connection() as db: return db.execute(sql,args).fetchall()

@app.get("/api/rooms/{room_name}/ac")
def get_ac(room_name: str, user=Depends(current_user)):
    room=room_for_user(room_name,user)
    with get_connection() as db: state=db.execute("SELECT is_on,target_temperature_c,updated_at FROM ac_states WHERE room_id=%s",(room["id"],)).fetchone()
    return {"room_name":room["name"], **state}

@app.get("/api/device/ac")
def device_ac(x_device_id: str = Header(), x_api_key: str = Header()):
    with get_connection() as db:
        device = db.execute("SELECT id,room_id,api_key_hash FROM devices WHERE device_name=%s AND is_active=TRUE", (x_device_id,)).fetchone()
        if not device or not password_hash.verify(x_api_key, device["api_key_hash"]): raise HTTPException(401, "Invalid device credentials")
        state = db.execute("SELECT is_on,target_temperature_c,updated_at FROM ac_states WHERE room_id=%s", (device["room_id"],)).fetchone()
    return state

@app.put("/api/rooms/{room_name}/ac")
def put_ac(room_name: str, update: AcUpdate, user=Depends(current_user)):
    room=room_for_user(room_name,user); now=datetime.now(timezone.utc)
    with get_connection() as db:
        db.execute("UPDATE ac_states SET is_on=%s,target_temperature_c=%s,updated_at=%s WHERE room_id=%s",(update.is_on,update.target_temperature_c,now,room["id"]))
        db.execute("INSERT INTO control_commands(room_id,issued_by_user_id,command_type,value) VALUES(%s,%s,'ac_update',%s)",(room["id"],user["id"],f"on={update.is_on}; target={update.target_temperature_c}"))
    return {"room_name":room["name"], **update.model_dump(), "updated_at":now}
