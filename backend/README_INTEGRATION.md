# PowerStep — Integration Layer (Bridge, AI, DB, Alerts)

This document explains the files added on top of the team's existing code,
why each one exists, and how to run the whole system end-to-end.

## Golden Rule compliance

**Nothing in `data cleaning and AI models/`, `powerstep-nyrh/`, or `wifi_hag/`
was modified, renamed, or deleted.** Every file listed below is new. The one
exception worth calling out explicitly: `train_peak_forecast_model.py`
*reads* `university_simulated_week_1st.csv` (read-only) and writes its
output to a brand-new file, `peak_forecast_model_1st.joblib`, inside
`data cleaning and AI models/` — it does not touch
`xgboost_peak_predictor.joblib` or `xgboost_peak_predictor_new.joblib`.

## What the existing code actually does (the part that shaped every design decision here)

- **`powerstep-nyrh/ae8.ino`** streams one JSON object per loop over
  **Serial/USB** at 115200 baud (voltage, current, generated power, SOC,
  footfall, tile status). It has no WiFi and no actuator/buzzer of its own.
- **`wifi_hag/esp32_probe_csi_combined__1_.ino`** is on WiFi and **POSTs JSON
  to `http://<SERVER_IP>:8000/api/ingest`** every 5 seconds with
  `{people_count, device_count_raw, csi_variance, csi_people_estimate}`.
  Port `8000` and the `/api/ingest` route are hardcoded in the firmware, so
  `main_system.py`'s HTTP server has to match them exactly.
- Three models already exist, trained by the team's own scripts:
  `piezo_step_model.joblib` (features: `Voltage (V)`, `Power (W)`),
  `wifi_occupancy_model.joblib` (feature: `csi_variance`), and
  `wifi_count_model.joblib` (feature: `device_count_raw`). A fourth,
  time-based model (`xgboost_peak_predictor*.joblib`) existed but was trained
  on the wrong file for this task — hence `peak_forecast_model_1st.joblib`.

## New files

| File | Purpose |
|---|---|
| `config.py` | Every path/port/threshold/credential in one place, overridable via env vars or `.env`. |
| `train_peak_forecast_model.py` | Trains the mandated forecast model on `university_simulated_week_1st.csv` only. **Already run** — `peak_forecast_model_1st.joblib` is included. |
| `realtime_inference.py` | Loads all 4 models once; turns one raw device reading into a fully-scored record. |
| `database_manager.py` | SQLite (stdlib, WAL mode) — `piezo_readings`, `wifi_readings`, `alerts_log` tables. |
| `alert_manager.py` | Telegram / Email / local buzzer, with per-alert-type cooldowns so an ongoing condition doesn't spam you. |
| `main_system.py` | The Bridge: Flask server for the WiFi channel, a background thread for the Serial/piezo channel, a liveness watchdog, wired to the three files above. |
| `requirements.txt` | Exact, tested versions for the whole pipeline (training + runtime). |
| `.env.example` | Copy to `.env` and fill in your serial port / bot token / SMTP creds. |
| `simulate_wifi_traffic.py` | Optional — replays real rows from `wifi_dataset (2/3).csv` at the WiFi board's endpoint, so you can test/demo before the physical board is wired up. |

## How the three AI models combine into one decision (`realtime_inference.py`)

- **Piezo channel:** `voltage_v`/`generation_w` → `piezo_step_model` →
  `ai_step_detected`, stored alongside the firmware's own `footfall` flag so
  you can see where the simple analog threshold and the trained model agree
  or disagree.
- **WiFi channel:** `csi_variance` → `wifi_occupancy_model` → occupied
  yes/no. If occupied, `device_count_raw` → `wifi_count_model` →
  `ai_people_estimate`. This is compared against the firmware's own fused
  `people_count` (it already blends probe-request counting with its own CSI
  heuristic onboard) to get `final_people_count`, and any disagreement
  between the two is recorded as `mismatch_flag`.
- **Forecast:** current time → `peak_forecast_model_1st` →
  `expected_occupancy_level` (idle/medium/peak). This gives `alert_manager.py`
  a baseline to catch things like "5 people showed up during a slot the
  model expects to be empty."

## Alerts (`alert_manager.py`)

Fires on: occupancy over threshold, SOC below threshold, a sudden power-
generation drop while footfall is still active (possible tile fault), a
persistent (not single-sample) mismatch between the AI and the firmware/
forecast, and either sensing channel going silent. Every alert is logged to
`alerts_log` regardless of whether any channel was configured to actually
deliver it.

The buzzer is a local software tone on whatever machine runs
`main_system.py` (`winsound` on Windows, terminal bell elsewhere) — neither
ESP32 sketch exposes an actuator, and the Golden Rule forbids adding one to
the firmware. `AlertManager.set_hardware_buzzer_callback()` lets you swap in
a real GPIO/serial-triggered buzzer later without touching this file.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env        # edit PIEZO_SERIAL_PORT and any alert credentials
python train_peak_forecast_model.py   # optional — already run, artifact included
python main_system.py
```

This starts the WiFi ingestion server on `:8000` and opens the piezo serial
port in the background. If either device isn't physically connected yet,
that channel logs a warning and keeps retrying — it won't crash the other
channel.

**Point the WiFi ESP32's `SERVER_IP`** (in the .ino, already set) at the
machine running `main_system.py`. **Set `PIEZO_SERIAL_PORT`** in `.env` to
wherever `ae8.ino`'s board actually enumerates (e.g. `COM6` on Windows,
`/dev/ttyUSB0` on Linux).

To verify it's alive without hardware:
```bash
python simulate_wifi_traffic.py --interval 2
curl http://localhost:8000/api/status
```

## Testing notes (what was actually verified while building this)

- All four `.joblib` models load cleanly with the pinned `requirements.txt`
  versions (no `InconsistentVersionWarning`).
- `realtime_inference.py` was checked against sklearn's strict column-order
  validation: passing a DataFrame with correctly-named but *reordered*
  columns raises an error, not a silent bad prediction — every prediction
  call here builds its input frame from the model's own
  `feature_names_in_` to guard against that.
- The piezo Serial path was exercised against a real pseudo-terminal pair
  emitting `ae8.ino`'s exact JSON shape — readings flowed through inference
  into SQLite correctly.
- The WiFi path was exercised with real HTTP POSTs (including a malformed-
  body request, correctly returning 400) and with `simulate_wifi_traffic.py`
  replaying genuine rows from `wifi_dataset (2/3).csv`.
- A full `main_system.py` boot was run standalone: models load, Flask starts
  on `:8000`, and a missing serial port is handled with a warning + retry
  loop rather than a crash.

## One thing worth knowing, not a bug in this integration layer

`wifi_occupancy_model.joblib`, as trained by the team on `wifi_dataset
(2).csv` / `(3).csv`, leans toward predicting "occupied" even at fairly low
`csi_variance` — both source files are dominated by rows where people were
actually present. This is a property of that model's training data, not
something this integration layer changes. It's why `final_people_count`
still falls back sensibly to the firmware's own count when the model's
occupancy call and its own count model don't line up — and why
`mismatch_flag` exists, so this kind of disagreement is visible in the data
rather than silently masked.
