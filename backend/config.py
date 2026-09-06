"""
config.py
=========
Centralized configuration for the PowerStep integration layer
(realtime_inference.py, database_manager.py, alert_manager.py, main_system.py).

This is a NEW file. It does not modify, wrap, or import-and-override anything
inside the original team folders — it only *points at* files that already
exist there (model artifacts, in read-only fashion).

All values can be overridden with environment variables (or a `.env` file in
the project root — see `.env.example`), so nobody needs to edit this file to
run the system with different hardware/ports/credentials.
"""

import os
from pathlib import Path

# Load a .env file if python-dotenv is available and a .env exists.
# This is optional convenience only — the system works fine with plain
# environment variables if python-dotenv isn't installed.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# --------------------------------------------------------------------------
# Paths — everything is resolved relative to this file, so the system can be
# run from any working directory.
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# Original, untouched team folders (read-only from our perspective).
MODELS_DIR = Path(_env_str("MODELS_DIR", str(BASE_DIR / "data cleaning and AI models")))
PIEZO_FIRMWARE_DIR = BASE_DIR / "powerstep-nyrh"
WIFI_FIRMWARE_DIR = BASE_DIR / "wifi_hag"

# Pre-trained models that already exist in the repo (created by the team's
# own training scripts). We only ever *load* these, never overwrite them.
PIEZO_STEP_MODEL_PATH = MODELS_DIR / "piezo_step_model.joblib"
WIFI_OCCUPANCY_MODEL_PATH = MODELS_DIR / "wifi_occupancy_model.joblib"
WIFI_COUNT_MODEL_PATH = MODELS_DIR / "wifi_count_model.joblib"

# Our new forecast model, trained exclusively on university_simulated_week_1st.csv
# by train_peak_forecast_model.py (a new file). Saved under a NEW filename so
# the team's original xgboost_peak_predictor(.joblib/_new.joblib) are left
# completely untouched.
PEAK_FORECAST_MODEL_PATH = MODELS_DIR / "peak_forecast_model_1st.joblib"

# The single authoritative training reference mandated for this task.
PRIMARY_TRAINING_CSV = MODELS_DIR / "university_simulated_week_1st.csv"

# Runtime data created BY this integration layer (new directories/files only).
RUNTIME_DIR = BASE_DIR / "runtime_data"
DB_PATH = Path(_env_str("DB_PATH", str(RUNTIME_DIR / "powerstep_system.db")))
LOG_DIR = Path(_env_str("LOG_DIR", str(BASE_DIR / "logs")))

# --------------------------------------------------------------------------
# WiFi ingestion server
# --------------------------------------------------------------------------
# NOTE: esp32_probe_csi_combined__1_.ino hardcodes SERVER_PORT = 8000 and
# POSTs to "/api/ingest". Since the firmware cannot be modified, this port
# and route are FIXED and must match exactly.
WIFI_INGEST_HOST = _env_str("WIFI_INGEST_HOST", "0.0.0.0")
WIFI_INGEST_PORT = _env_int("WIFI_INGEST_PORT", 8000)
WIFI_NODE_ID = _env_str("WIFI_NODE_ID", "corridor_node_1")

# --------------------------------------------------------------------------
# Piezo serial connection
# --------------------------------------------------------------------------
# ae8.ino streams one JSON object per loop over Serial at 115200 baud.
# python.py (the team's existing logger) hardcodes PORT='COM6' for Windows;
# on Linux/macOS this is typically something like /dev/ttyUSB0 or /dev/ttyACM0.
PIEZO_SERIAL_PORT = _env_str("PIEZO_SERIAL_PORT", "COM6")
PIEZO_BAUD_RATE = _env_int("PIEZO_BAUD_RATE", 115200)
PIEZO_RECONNECT_INTERVAL_SEC = _env_float("PIEZO_RECONNECT_INTERVAL_SEC", 5.0)
PIEZO_READ_TIMEOUT_SEC = _env_float("PIEZO_READ_TIMEOUT_SEC", 1.0)

# --------------------------------------------------------------------------
# Device liveness / "is a stream still coming in" watchdog
# --------------------------------------------------------------------------
WATCHDOG_INTERVAL_SEC = _env_float("WATCHDOG_INTERVAL_SEC", 15.0)
PIEZO_OFFLINE_TIMEOUT_SEC = _env_float("PIEZO_OFFLINE_TIMEOUT_SEC", 20.0)
WIFI_OFFLINE_TIMEOUT_SEC = _env_float("WIFI_OFFLINE_TIMEOUT_SEC", 30.0)

# --------------------------------------------------------------------------
# Alert thresholds
# --------------------------------------------------------------------------
# Occupancy: alert when the decided people count exceeds this.
OCCUPANCY_ALERT_THRESHOLD = _env_int("OCCUPANCY_ALERT_THRESHOLD", 6)

# Battery / storage: alert when state of charge drops below this percentage.
LOW_BATTERY_SOC_THRESHOLD = _env_float("LOW_BATTERY_SOC_THRESHOLD", 15.0)

# Power generation drop: alert if generation falls by more than this ratio
# vs. the recent rolling average while footfall is still being detected
# (suggests a tile/sensor fault rather than genuine idleness).
POWER_DROP_RATIO_THRESHOLD = _env_float("POWER_DROP_RATIO_THRESHOLD", 0.8)
POWER_TREND_WINDOW = _env_int("POWER_TREND_WINDOW", 20)

# AI-vs-firmware / AI-vs-forecast mismatch: alert only after this many
# consecutive mismatched readings, to avoid flagging single noisy samples.
MISMATCH_STREAK_THRESHOLD = _env_int("MISMATCH_STREAK_THRESHOLD", 3)

# Minimum seconds between two alerts of the *same type*, to avoid flooding
# Telegram/Email/buzzer with repeats of an ongoing condition.
ALERT_COOLDOWN_SECONDS = _env_float("ALERT_COOLDOWN_SECONDS", 300.0)

# --------------------------------------------------------------------------
# Alert channels
# --------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = _env_str("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _env_str("TELEGRAM_CHAT_ID", "")

SMTP_HOST = _env_str("SMTP_HOST", "")
SMTP_PORT = _env_int("SMTP_PORT", 587)
SMTP_USER = _env_str("SMTP_USER", "")
SMTP_PASSWORD = _env_str("SMTP_PASSWORD", "")
ALERT_EMAIL_TO = _env_str("ALERT_EMAIL_TO", "")

ENABLE_LOCAL_BUZZER = _env_bool("ENABLE_LOCAL_BUZZER", True)

# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------
LOG_LEVEL = _env_str("LOG_LEVEL", "INFO")
