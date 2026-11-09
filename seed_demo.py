from app.database import get_connection
from app.main import password_hash

with get_connection() as db:
    room = db.execute("INSERT INTO rooms(name,location) VALUES(%s,%s) ON CONFLICT(name) DO UPDATE SET location=EXCLUDED.location RETURNING id", ("Room A-101", "Academic Building A")).fetchone()
    db.execute("INSERT INTO ac_states(room_id) VALUES(%s) ON CONFLICT DO NOTHING", (room["id"],))
    db.execute("INSERT INTO users(username,password_hash,role) VALUES(%s,%s,'admin') ON CONFLICT(username) DO NOTHING", ("campus-admin", password_hash.hash("AdminDemo123!")))
    db.execute("INSERT INTO users(username,password_hash,role,assigned_room_id) VALUES(%s,%s,'room_operator',%s) ON CONFLICT(username) DO NOTHING", ("room-a101-operator", password_hash.hash("RoomA101Demo123!"), room["id"]))
    db.execute("INSERT INTO devices(device_name,api_key_hash,room_id) VALUES(%s,%s,%s) ON CONFLICT(device_name) DO NOTHING", ("iaq-a101-01", password_hash.hash("iaq-a101-demo-key-change-me"), room["id"]))
print("Seeded: campus-admin / AdminDemo123!; room-a101-operator / RoomA101Demo123!; device iaq-a101-01")
