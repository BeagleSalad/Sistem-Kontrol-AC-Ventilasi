"""Generate realistic-enough virtual readings for Room A-101."""

import json
import random
import time
from datetime import datetime
from urllib import error, request

API_URL = "http://127.0.0.1:8000/api/readings"
AC_STATE_URL = "http://127.0.0.1:8000/api/rooms/Room%20A-101/ac"
INTERVAL_SECONDS = 10


def get_ac_state() -> dict:
    with request.urlopen(AC_STATE_URL, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def build_reading(ac_state: dict) -> dict:
    hour = datetime.now().hour
    class_in_session = 7 <= hour < 18
    occupancy = random.randint(15, 42) if class_in_session else random.randint(0, 4)
    co2_baseline = 500 + occupancy * 20

    temperature = random.uniform(23.0, 28.5)
    if ac_state["is_on"]:
        temperature = random.uniform(
            ac_state["target_temperature_c"] - 0.8,
            ac_state["target_temperature_c"] + 0.8,
        )
    return {
        "room_name": "Room A-101",
        "temperature_c": round(temperature, 1),
        "humidity_percent": round(random.uniform(48.0, 72.0), 1),
        "co2_ppm": max(400, int(random.gauss(co2_baseline, 80))),
        "pm25_ug_m3": round(max(2, random.gauss(16, 7)), 1),
        "occupancy": occupancy,
    }


def send_reading(reading: dict) -> None:
    payload = json.dumps(reading).encode("utf-8")
    http_request = request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(http_request, timeout=5) as response:
        result = json.loads(response.read().decode("utf-8"))
    print(f"Sent reading: CO2 {reading['co2_ppm']} ppm, status {result['status']}")


if __name__ == "__main__":
    print("Indoor Air Quality simulator started. Press Ctrl+C to stop.")
    while True:
        try:
            ac_state = get_ac_state()
            send_reading(build_reading(ac_state))
        except error.URLError:
            print("Backend is unavailable. Start it with: uvicorn app.main:app --reload")
        time.sleep(INTERVAL_SECONDS)
