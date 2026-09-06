"""
database_manager.py
====================
Initializes and manages a lightweight SQLite database that continuously and
systematically stores:
  - every piezo reading (+ the AI's step-detection verdict)
  - every WiFi occupancy reading (+ the AI's occupancy/count verdict and the
    time-based forecast it was compared against)
  - every alert that was ever triggered

SQLite (stdlib `sqlite3`, no server, no extra dependency) is used because this
is a single-box hackathon deployment; WAL mode is enabled so the Flask
request thread and the piezo serial-reader thread can read/write concurrently
without locking each other out.

Uses a fresh connection per call rather than one long-lived shared
connection. This keeps the thread-safety story simple (sqlite3 connections
are not safe to share across threads without care) at a small, acceptable
performance cost for this system's data rates (a handful of readings/sec).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS piezo_readings (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at          TEXT NOT NULL,
    device_day           INTEGER,
    device_sim_time      TEXT,
    device_uptime        TEXT,
    voltage_v            REAL,
    current_a            REAL,
    generation_w         REAL,
    cumulative_gen_wh    REAL,
    storage_soc_pct      REAL,
    power_source         TEXT,
    footfall             INTEGER,
    ai_step_detected     INTEGER,
    ai_step_confidence   REAL,
    tile_id              INTEGER,
    tile_efficiency_pct  REAL,
    tile_total_steps     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_piezo_received_at ON piezo_readings (received_at);

CREATE TABLE IF NOT EXISTS wifi_readings (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at                 TEXT NOT NULL,
    node_id                     TEXT,
    device_count_raw            REAL,
    csi_variance                REAL,
    csi_people_estimate         INTEGER,
    firmware_people_count       INTEGER,
    ai_is_occupied              INTEGER,
    ai_occupancy_confidence     REAL,
    ai_people_estimate          INTEGER,
    final_people_count          INTEGER,
    expected_occupancy_level    INTEGER,
    expected_occupancy_label    TEXT,
    mismatch_flag               INTEGER
);

CREATE INDEX IF NOT EXISTS idx_wifi_received_at ON wifi_readings (received_at);

CREATE TABLE IF NOT EXISTS alerts_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    triggered_at  TEXT NOT NULL,
    alert_type    TEXT NOT NULL,
    severity      TEXT,
    message       TEXT,
    channels      TEXT,
    delivered     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_alerts_triggered_at ON alerts_log (triggered_at);
"""


class DatabaseManager:
    def __init__(self, db_path: Path = config.DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # ------------------------------------------------------------------
    # Inserts
    # ------------------------------------------------------------------
    def insert_piezo_reading(self, record: dict[str, Any]) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO piezo_readings (
                    received_at, device_day, device_sim_time, device_uptime,
                    voltage_v, current_a, generation_w, cumulative_gen_wh,
                    storage_soc_pct, power_source, footfall,
                    ai_step_detected, ai_step_confidence,
                    tile_id, tile_efficiency_pct, tile_total_steps
                ) VALUES (
                    :received_at, :device_day, :device_sim_time, :device_uptime,
                    :voltage_v, :current_a, :generation_w, :cumulative_gen_wh,
                    :storage_soc_pct, :power_source, :footfall,
                    :ai_step_detected, :ai_step_confidence,
                    :tile_id, :tile_efficiency_pct, :tile_total_steps
                )
                """,
                record,
            )
            return cur.lastrowid

    def insert_wifi_reading(self, record: dict[str, Any]) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO wifi_readings (
                    received_at, node_id, device_count_raw, csi_variance,
                    csi_people_estimate, firmware_people_count,
                    ai_is_occupied, ai_occupancy_confidence, ai_people_estimate,
                    final_people_count, expected_occupancy_level,
                    expected_occupancy_label, mismatch_flag
                ) VALUES (
                    :received_at, :node_id, :device_count_raw, :csi_variance,
                    :csi_people_estimate, :firmware_people_count,
                    :ai_is_occupied, :ai_occupancy_confidence, :ai_people_estimate,
                    :final_people_count, :expected_occupancy_level,
                    :expected_occupancy_label, :mismatch_flag
                )
                """,
                record,
            )
            return cur.lastrowid

    def insert_alert(
        self,
        triggered_at: str,
        alert_type: str,
        severity: str,
        message: str,
        channels: str,
        delivered: bool,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO alerts_log (triggered_at, alert_type, severity, message, channels, delivered)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (triggered_at, alert_type, severity, message, channels, int(delivered)),
            )
            return cur.lastrowid

    # ------------------------------------------------------------------
    # Reads (used by alert_manager.py for trend checks, and for status APIs)
    # ------------------------------------------------------------------
    def get_latest_piezo(self, n: int = 1) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM piezo_readings ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_wifi(self, n: int = 1) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM wifi_readings ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent_piezo(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM piezo_readings ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM alerts_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Analytics & History Reads (from static file / historical DB)
    # ------------------------------------------------------------------
    def get_available_days(self, limit: int = 5) -> list[str]:
        """Returns the last distinct dates (YYYY-MM-DD) available in the DB."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT DATE(received_at) as day FROM piezo_readings ORDER BY day DESC LIMIT ?", (limit,)
            ).fetchall()
            return [r["day"] for r in rows if r["day"]]

    def get_daily_chart_data(self, date_str: str) -> dict[str, list[float]]:
        """Aggregates data by hour (00-23) for the given date."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT 
                    strftime('%H', received_at) as hour,
                    AVG(generation_w) * 10000.0 as avg_gen,
                    AVG(storage_soc_pct) as avg_soc,
                    AVG(footfall) as avg_footfall
                FROM piezo_readings 
                WHERE DATE(received_at) = ?
                GROUP BY hour
                ORDER BY hour ASC
                """,
                (date_str,)
            ).fetchall()
            
            # Initialize 24 hours with 0
            hours = [f"{i:02d}:00" for i in range(24)]
            gen = [0.0] * 24
            con = [0.0] * 24  # Will be mocked based on footfall
            soc = [0.0] * 24
            foot = [0.0] * 24
            
            for r in rows:
                if not r["hour"]: continue
                h = int(r["hour"])
                gen_val = round(r["avg_gen"] or 0.0, 4)
                foot_val = round(r["avg_footfall"] or 0.0, 1)
                
                gen[h] = gen_val
                soc[h] = round(r["avg_soc"] or 0.0, 1)
                foot[h] = foot_val
                # Realistic mock consumption: base load 5W + 1.5W per person footfall
                con[h] = round(5.0 + (foot_val * 1.5), 2) if foot_val > 0 else 5.0
                
            return {
                "hours": hours,
                "gen_wh": gen,
                "con_wh": con,
                "soc_wh": soc,
                "footfall": foot
            }

    def get_analytics_summary_from_db(self) -> dict[str, Any]:
        """Calculates total records, peaks, and recent history points from the DB."""
        with self._connect() as conn:
            stats = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_records,
                    MAX(generation_w) * 10000.0 as peak_gen,
                    SUM(generation_w) * 10000.0 as total_gen,
                    MAX(footfall) as peak_footfall,
                    AVG(footfall) as avg_footfall
                FROM piezo_readings
                """
            ).fetchone()
            
            # For recent_data, fetch data across the ENTIRE recorded history grouped by hour (or every few hours)
            recent_rows = conn.execute(
                """
                SELECT 
                    strftime('%Y-%m-%d %H', received_at) as time_bucket,
                    MAX(received_at) as received_at,
                    AVG(generation_w) * 10000.0 as generation_w,
                    AVG(storage_soc_pct) as storage_soc_pct,
                    SUM(footfall) as footfall
                FROM piezo_readings
                GROUP BY time_bucket
                ORDER BY time_bucket ASC
                """
            ).fetchall()
            
            recent_data = []
            for r in recent_rows:
                try:
                    dt = r["received_at"]
                    time_part = dt.split('T')[1] if 'T' in dt else dt.split(' ')[1]
                    h, m, _ = map(int, time_part.split(':'))
                    sim_hour = h + (m / 60.0)
                except Exception:
                    sim_hour = 0.0
                    
                foot_val = int(r["footfall"] or 0)
                # Realistic mock consumption: base load 5W + 1.5W per person
                mock_con = round(5.0 + (foot_val * 1.5), 2) if foot_val > 0 else 5.0

                recent_data.append({
                    "sim_hour": round(sim_hour, 2),
                    "gen_wh": round(r["generation_w"] or 0.0, 4),
                    "con_wh": mock_con,
                    "soc_wh": round(r["storage_soc_pct"] or 0.0, 1),
                    "footfall": foot_val
                })
                
            peak_footfall = stats["peak_footfall"] or 0
            peak_con = round(5.0 + (peak_footfall * 1.5), 2)
            
            # Fetch Heatmap Data (grouped by day of week [0=Sun, 6=Sat] and hour)
            heatmap_rows = conn.execute(
                """
                SELECT 
                    strftime('%w', received_at) as day_of_week, 
                    strftime('%H', received_at) as hour, 
                    SUM(footfall) as total_footfall
                FROM piezo_readings
                WHERE received_at IS NOT NULL
                GROUP BY day_of_week, hour
                """
            ).fetchall()
            
            # Initialize 7x24 matrix with 0
            heatmap_data = [[0 for _ in range(24)] for _ in range(7)]
            for hr in heatmap_rows:
                if hr["day_of_week"] is not None and hr["hour"] is not None:
                    d = int(hr["day_of_week"])
                    h = int(hr["hour"])
                    heatmap_data[d][h] = int(hr["total_footfall"] or 0)
                
            return {
                "total_records": stats["total_records"] or 0,
                "peak_generation_wh": round(stats["peak_gen"] or 0.0, 2),
                "total_generation_wh": round(stats["total_gen"] or 0.0, 2),
                "peak_consumption_wh": peak_con,
                "avg_footfall": round(stats["avg_footfall"] or 0.0, 2),
                "recent_data": recent_data,
                "heatmap_data": heatmap_data
            }
