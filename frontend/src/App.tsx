import { useCallback, useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8000";
const ROOM_NAME = "Room A-101";

type Reading = {
  id: number;
  room_name: string;
  recorded_at: string;
  temperature_c: number;
  humidity_percent: number;
  co2_ppm: number;
  pm25_ug_m3: number;
  occupancy: number;
  status: "good" | "warning" | "unhealthy";
};

type Alert = {
  id: number;
  room_name: string;
  severity: "warning" | "critical";
  message: string;
  created_at: string;
};

type AcState = {
  room_name: string;
  is_on: boolean;
  target_temperature_c: number;
  updated_at: string;
};

function MetricCard({ label, value, unit, tone = "neutral" }: { label: string; value: string | number; unit: string; tone?: string }) {
  return (
    <article className={`metric-card ${tone}`}>
      <p>{label}</p>
      <strong>{value}<span>{unit}</span></strong>
    </article>
  );
}

export default function App() {
  const [latest, setLatest] = useState<Reading | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [ac, setAc] = useState<AcState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [readingsResponse, alertsResponse, acResponse] = await Promise.all([
        fetch(`${API_URL}/api/readings?limit=1`),
        fetch(`${API_URL}/api/alerts?limit=5`),
        fetch(`${API_URL}/api/rooms/${encodeURIComponent(ROOM_NAME)}/ac`),
      ]);
      if (![readingsResponse, alertsResponse, acResponse].every((response) => response.ok)) {
        throw new Error("The API did not respond successfully.");
      }
      const readings: Reading[] = await readingsResponse.json();
      setLatest(readings[0] ?? null);
      setAlerts(await alertsResponse.json());
      setAc(await acResponse.json());
      setError("");
    } catch {
      setError("Cannot reach the backend. Start FastAPI on port 8000, then start the simulator.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 10_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  async function saveAc(next: AcState) {
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/api/rooms/${encodeURIComponent(ROOM_NAME)}/ac`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_on: next.is_on, target_temperature_c: next.target_temperature_c }),
      });
      if (!response.ok) throw new Error();
      setAc(await response.json());
    } catch {
      setError("Could not save the AC control. Check that the backend is running.");
    } finally {
      setSaving(false);
    }
  }

  const status = latest?.status ?? "waiting";
  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">Indoor air quality monitor</p>
          <h1>{ROOM_NAME}</h1>
          <p className="subtle">Academic Building A · Live Sensor Data</p>
        </div>
        <div className={`status ${status}`}><i /> {status === "waiting" ? "Waiting for data" : `Air quality: ${status}`}</div>
      </header>

      {error && <p className="error">{error}</p>}
      {loading ? <p className="loading">Loading dashboard…</p> : <>
        <section className="metrics" aria-label="Latest room measurements">
          <MetricCard label="Temperature" value={latest?.temperature_c ?? "—"} unit="°C" tone="blue" />
          <MetricCard label="Humidity" value={latest?.humidity_percent ?? "—"} unit="%" tone="teal" />
          <MetricCard label="CO₂" value={latest?.co2_ppm ?? "—"} unit="ppm" tone={latest && latest.co2_ppm > 1000 ? "amber" : "neutral"} />
          <MetricCard label="PM2.5" value={latest?.pm25_ug_m3 ?? "—"} unit="µg/m³" tone={latest && latest.pm25_ug_m3 > 35 ? "amber" : "neutral"} />
          <MetricCard label="Occupancy" value={latest?.occupancy ?? "—"} unit="people" tone="purple" />
        </section>

        <section className="grid">
          <article className="panel controls">
            <div className="panel-title"><div><p className="eyebrow">Virtual device control</p><h2>Air conditioner</h2></div><span className={ac?.is_on ? "on" : "off"}>{ac?.is_on ? "ON" : "OFF"}</span></div>
            <button
              className={`power ${ac?.is_on ? "active" : ""}`}
              disabled={!ac || saving}
              onClick={() => ac && void saveAc({ ...ac, is_on: !ac.is_on })}
            >{ac?.is_on ? "Turn AC off" : "Turn AC on"}</button>
            <label>Target temperature <strong>{ac?.target_temperature_c ?? 24}°C</strong>
              <input type="range" min="16" max="30" step="0.5" value={ac?.target_temperature_c ?? 24} disabled={!ac || saving}
                onChange={(event) => ac && setAc({ ...ac, target_temperature_c: Number(event.target.value) })}
                onMouseUp={() => ac && void saveAc(ac)} onTouchEnd={() => ac && void saveAc(ac)} />
            </label>
            <p className="subtle">The simulator adopts this setting on its next reading.</p>
          </article>

          <article className="panel">
            <div className="panel-title"><div><p className="eyebrow">Automatic rules</p><h2>Recent alerts</h2></div></div>
            {alerts.length === 0 ? <p className="empty">No alerts yet. The air currently looks fine.</p> : <ul className="alerts">{alerts.map((alert) => <li key={alert.id} className={alert.severity}><span>{alert.severity}</span><p>{alert.message}<small>{new Date(alert.created_at).toLocaleString()}</small></p></li>)}</ul>}
          </article>
        </section>
      </>}
    </main>
  );
}
