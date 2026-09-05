# PowerStep Grid — Backend API Specification

> This document defines the exact contract between the **backend** (FastAPI / simulator) and the **dashboard frontend**. The frontend is fully built and expects these endpoints and schemas. Any mismatch will break the dashboard.

---

## 1. WebSocket — Live Telemetry

- **Path:** `/ws/live`
- **Protocol:** WebSocket
- **Frequency:** one JSON message every ~1 second (real-time)

### Message Schema (JSON)

```json
{
  "day": 1,
  "sim_time": "10:30:00",
  "generation_w": 5.2,
  "consumption_w": 3.8,
  "forecast_w": 5.5,
  "self_sufficiency_pct": 72,
  "storage_soc_pct": 78,
  "power_source": "harvested",
  "footfall": 12,
  "voltage_v": 12.4,
  "current_a": 0.4,
  "system_uptime": "00:15:30",
  "battery_temperature": 24.5,
  "cumulative_gen_wh": 12.3450,
  "cumulative_con_wh": 9.8760,
  "co2_saved_grams": 4.94,
  "cost_saved": 0.0021,
  "exported_wh": 1.2340,
  "ai_status": {
    "forecast_model": "Online",
    "anomaly_model": "Online"
  },
  "loads": {
    "load_1": { "name": "إضاءة A", "state": "ON" },
    "load_2": { "name": "إضاءة B", "state": "OFF" },
    "load_3": { "name": "مكيف", "state": "Standby" }
  },
  "alerts": [
    { "level": "warning", "text": "بلاطة رقم 4 كفاءتها منخفضة" }
  ],
  "tiles": [
    { "id": 1, "stepped_on": true, "efficiency_pct": 92 },
    { "id": 2, "stepped_on": false, "efficiency_pct": 85 }
  ]
}
```

### Field Reference

| Field | Type | Description |
|---|---|---|
| `day` | int | Simulation day number |
| `sim_time` | string | Simulation clock `HH:MM:SS` |
| `generation_w` | float | Instantaneous generation (watts) |
| `consumption_w` | float | Instantaneous consumption (watts) |
| `forecast_w` | float | AI-predicted generation (watts) |
| `self_sufficiency_pct` | float [0-100] | Self-sufficiency percentage |
| `storage_soc_pct` | float [0-100] | Battery state of charge |
| `power_source` | string | `"harvested"` OR `"grid"` (anything else = grid) |
| `footfall` | float | Steps per minute |
| `voltage_v` | float | System voltage |
| `current_a` | float | System current |
| `system_uptime` | string | Uptime `HH:MM:SS` |
| `battery_temperature` | float | Battery temp (°C) |
| `cumulative_gen_wh` | float | Total generated (Wh), 4 decimal places |
| `cumulative_con_wh` | float | Total consumed (Wh), 4 decimal places |
| `co2_saved_grams` | float | CO2 saved (grams) — if omitted, frontend computes as `cumulative_gen_wh * 0.4` |
| `cost_saved` | float | Money saved ($) |
| `exported_wh` | float | Exported energy (Wh) |
| `ai_status.forecast_model` | string | `"Online"` or anything else | + `"Offline"` |
| `ai_status.anomaly_model` | string | `"Online"` or anything else |
| `loads` | object | Each key is a load: `{ name: string, state: "ON"\|"Standby"\|"OFF" }` |
| `alerts` | array | Each item: `{ level: "warning"\|"danger"\|"info"\|"success", text: string }` |
| `tiles` | array | Each item: `{ id: int, stepped_on: bool, efficiency_pct: float }` |

> **Note on AI status:** the frontend checks if the value equals `"Online"` exactly. Use exactly `"Online"` string, otherwise the model will show as offline.

> **Note on tiles:** the frontend heats up 16 tiles (8×4). If `efficiency_pct` is below the user-set threshold (default 80%), the tile turns red (faulty). If `stepped_on` is true, it glows green.

> **Note on alerts:** when a new alert appears, the frontend plays the alert sound and shows a toast notification.

---

## 2. Energy History — Line Chart + Footfall Strip

- **Path:** `/api/history`
- **Method:** GET
- **Frequency:** polled by the frontend every 4s

### Response Schema (JSON)

```json
{
  "t": [10.0, 10.25, 10.5, 10.75],
  "gen_wh": [5.1, 5.3, 5.0, 5.2],
  "con_wh": [3.2, 3.4, 3.1, 3.3],
  "footfall": [14, 12, 18, 15]
}
```

### Field Reference

| Field | Type | Description |
|---|---|---|
| `t` | array of float | Time in hours (e.g. `10.5` = 10:30), same length as gen/con |
| `gen_wh` | array of float | Generated energy (Wh) per time point |
| `con_wh` | array of float | Consumed energy (Wh) per time point |
| `footfall` | array of float | Steps/min per time point (frontend uses the last 40 values for the strip) |

> All arrays must be the **same length**.

---

## 3. Analytics Summary — Stats + 3 Charts

- **Path:** `/api/analytics/summary`
- **Method:** GET
- **Frequency:** polled every 10s

### Response Schema (JSON)

```json
{
  "total_records": 1500,
  "peak_generation_wh": 7.2,
  "peak_consumption_wh": 6.1,
  "avg_footfall": 11.4,
  "recent_data": [
    { "sim_hour": 10.0, "gen_wh": 5.1, "con_wh": 3.2, "soc_wh": 4.1, "footfall": 14 }
  ]
}
```

### Field Reference

| Field | Type | Description |
|---|---|---|
| `total_records` | int | Total stored records |
| `peak_generation_wh` | float | Peak generation (Wh) |
| `peak_consumption_wh` | float | Peak consumption (Wh) |
| `avg_footfall` | float | Average footfall (steps/min) |
| `recent_data` | array | Each item: `{ sim_hour: float, gen_wh: float, con_wh: float, soc_wh: float, footfall: float }` |

> `sim_hour` is in hours (10.5 = 10:30). `soc_wh` is battery level. `recent_data` powers all three charts (generation/consumption, battery, footfall).

---

## 4. CSV Export

- **Path:** `/api/export/csv`
- **Method:** GET
- **Response:** downloadable CSV file containing all stored records.

Nothing specific is parsed client-side — the user just downloads the file.

---

## Suggested Request Mapping (FastAPI)

| Endpoint | Method | Purpose |
|---|---|---|
| `/ws/live` | WebSocket | Live telemetry (1 msg/sec) |
| `/api/history` | GET | Line chart + footfall (polled 4s) |
| `/api/analytics/summary` | GET | Analytics page (polled 10s) |
| `/api/export/csv` | GET | CSV download |

---

## Common Rules (IMPORTANT)

1. **Same schema in every message** — the frontend parses directly, no defensive error handling for missing fields.
2. **Use exactly these JSON key names** (snake_case) — the frontend reads them literally.
3. **`power_source`:** use exactly `"harvested"` for clean energy, anything else shows as grid emergency.
4. **AI models:** use exactly `"Online"` string for online status.
5. **Numbers:** floats are fine; the frontend formats decimals itself.

---

*Questions? Contact the dashboard owner before changing any field name.*