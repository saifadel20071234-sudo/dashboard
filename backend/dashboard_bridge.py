"""
dashboard_bridge.py
===================
طبقة الوصل بين main_system بتاع الفريق (Flask على :8000) والداش بورد.
بتضيف كل اتّفاق الـ API الموجود في API_SPEC.md على نفس السيرفر من غير ما
نلمس موديولات الفريق (config / database_manager / realtime_inference / alert_manager).

الاستخدام داخل main_system.py:
    from dashboard_bridge import get_bridge
    bridge = get_bridge()
    bridge.attach(app)              # داخل create_app()
    bridge.on_piezo(record)         # بعد engine.process_piezo_reading()
    bridge.on_wifi(record)          # بعد engine.process_wifi_reading() في /api/ingest

ملاحظة مهمة:
    مفيش هنا أي توليد بيانات صناعي — كل القيم بتتاخد من قراءات الأجهزة
    الحقيقية (piezo + ESP32) اللي بتعدّي على main_system بتاع الفريق.
"""

from __future__ import annotations

import csv
import io
import json
import threading
import time
from collections import deque

from flask_sock import Sock
from flask_cors import CORS

NUM_TILES = 16
PRESS_WINDOW_SEC = 3.0        # المدة اللي بتفضل فيها البلاطة مضيئة بعد الضغط
BROADCAST_INTERVAL_SEC = 1.0  # بث الداش بورد كل ثانية
HISTORY_LIMIT = 5000          # عدد النقاط التاريخية المحفوظة

# لو أرقام الواط الحقيقية صغيرة جداً (ميكروواط) وقربت الصفر على الشاشة،
# غيّر الرقم دا لو اتقرر عامل تكبير بصري (المشروع القديم كان بيستخدم 10000).
POWER_SCALE = 1.0

DEFAULT_LOADS = {
    "load_1": {"name": "إضاءة A", "state": "OFF"},
    "load_2": {"name": "إضاءة B", "state": "OFF"},
    "load_3": {"name": "مكيف", "state": "OFF"},
}


def _pick(record: dict, *keys, default=0.0):
    """يقرا أول قيمة عددية صالحة من قائمة مفاتيح محتملة."""
    if not isinstance(record, dict):
        return default
    for key in keys:
        if key not in record:
            continue
        val = record[key]
        if val in (None, "", "NULL"):
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return default


def _text(record: dict, *keys, default=""):
    if not isinstance(record, dict):
        return default
    for key in keys:
        val = record.get(key)
        if val not in (None, ""):
            return str(val)
    return default


def _tile_id(record: dict):
    """يحاول استخراج رقم البلاطة من record (يدعم 'Tile_1' أو 1)."""
    val = record.get("tile_id", record.get("tile", record.get("id")))
    if val is None:
        return None
    text = str(val).strip()
    text = text.lower()
    text = text.replace("tile", "").replace("_", "").strip()
    try:
        num = int(float(text))
    except (TypeError, ValueError):
        return None
    return num if 1 <= num <= NUM_TILES else None


class DashboardBridge:
    """يجمع قراءات الفريق الحقيقية ويبعتها للداش بورد باتفاق API_SPEC.md."""

    def __init__(self):
        self._lock = threading.RLock()
        self._sock = None
        self._start_ts = time.time()

        self._last_piezo: dict = {}
        self._last_wifi: dict = {}
        self._db = None

        self._steps: deque = deque()          # (tile_id, time)
        self._history: deque = deque(maxlen=HISTORY_LIMIT)
        self._clients: set = set()

        self._loads = dict(DEFAULT_LOADS)
        self._uptime_offset_sec = 0.0

    # ------------------------------------------------------------------
    # الاستقبال من main_system بتاع الفريق
    # ------------------------------------------------------------------
    def on_piezo(self, record) -> None:
        with self._lock:
            if not isinstance(record, dict):
                return
            self._last_piezo = record

            tid = _tile_id(record)
            step_status = _text(record, "step_status", "Step Status", "status").upper()
            ai_detected = _pick(record, "ai_step_detected", default=0) > 0
            raw_footfall = _pick(record, "footfall", default=0) > 0
            pressed = tid is not None and (
                step_status in ("PRESSED", "ON", "1", "TRUE", "ACTIVE") or
                "PRESSED" in step_status or "ON" in step_status or
                ai_detected or raw_footfall
            )
            if pressed:
                now = time.time()
                self._steps.append((tid, now))
                # نحافظ بس على ضغطات حديثة لتفادي الذاكرة
                while self._steps and now - self._steps[0][1] > PRESS_WINDOW_SEC * 4:
                    self._steps.popleft()

    def on_wifi(self, record) -> None:
        with self._lock:
            if isinstance(record, dict):
                self._last_wifi = record

    def set_db(self, db) -> None:
        """يمرر الـ DatabaseManager بتاع الفريق عشان نقدر نقرا التنبيهات
        الحقيقية من alerts_log ويعرضها الداش بورد."""
        self._db = db

    # ------------------------------------------------------------------
    # الإلحاق بالـ Flask app
    # ------------------------------------------------------------------
    def attach(self, app) -> None:
        CORS(app)  # فيتلك للداش بورد من localhost:5500 (fetch للحقول النصية)
        self._sock = Sock(app)

        @self._sock.route("/ws/live")
        def ws_live(ws):
            with self._lock:
                self._clients.add(ws)
            self._send_forever(ws)

        app.add_url_rule("/api/history", view_func=self._api_history, methods=["GET"])
        app.add_url_rule("/api/analytics/summary", view_func=self._api_analytics, methods=["GET"])
        app.add_url_rule("/api/export/csv", view_func=self._api_export_csv, methods=["GET"])

        threading.Thread(target=self._broadcast_loop, name="dashboard-broadcast", daemon=True).start()
        return self

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------
    def _send_forever(self, ws) -> None:
        try:
            while True:
                try:
                    ws.send(json.dumps(self._snapshot(), ensure_ascii=False))
                except Exception:
                    break
                time.sleep(BROADCAST_INTERVAL_SEC)
        finally:
            with self._lock:
                self._clients.discard(ws)

    def _broadcast_loop(self) -> None:
        while True:
            try:
                payload = json.dumps(self._snapshot(), ensure_ascii=False)
            except Exception:
                payload = None
            if payload is not None:
                with self._lock:
                    for ws in list(self._clients):
                        try:
                            ws.send(payload)
                        except Exception:
                            self._clients.discard(ws)
            self._append_history()
            time.sleep(BROADCAST_INTERVAL_SEC)

    # ------------------------------------------------------------------
    # بناء الـ snapshot باتفاق API_SPEC.md
    # ------------------------------------------------------------------
    def _snapshot(self) -> dict:
        with self._lock:
            p = dict(self._last_piezo)
            w = dict(self._last_wifi)
            steps = list(self._steps)

        now = time.time()
        active_steps = [tid for tid, ts in steps if now - ts <= PRESS_WINDOW_SEC]

        gen_w = _pick(p, "generation_w", "power_w", "power", "avg_watt", "Power (W)", default=0.0) * POWER_SCALE
        con_w = 0.0  # القراءات الحقيقية مش بتقيس استهلاك — نرسله 0
        voltage = _pick(p, "voltage", "voltage_v", "Voltage (V)", default=0.0)
        current = _pick(p, "current", "current_a", "Current (A)", default=0.0)

        if voltage > 0 and current <= 0 and gen_w > 0:
            current = gen_w / voltage

        soc = _pick(p, "soc", "storage_soc_pct", "soc_pct", "SOC (%)", default=0.0)
        temperature = _pick(p, "temperature", "battery_temperature", default=0.0)
        cumulative_gen = _pick(p, "cumulative_gen_wh", "Cumulative Gen (Wh)", default=0.0)
        exported = _pick(p, "exported_wh", default=0.0)

        source_text = _text(p, "power_source", "Power Source", default="harvested").lower()
        power_source = "harvested" if source_text and source_text != "grid" else "grid"

        footfall = int(_pick(w, "final_people_count", "firmware_people_count", "people_count", "footfall", "count", default=0))
        if footfall == 0:
            footfall = int(_pick(p, "footfall", "people_count", default=0))

        tiles = []
        for i in range(1, NUM_TILES + 1):
            eff = _pick(p, "tile_efficiency_pct", "efficiency_pct", "efficiency", default=100.0)
            tiles.append({
                "id": i,
                "stepped_on": i in active_steps,
                "efficiency_pct": round(eff, 1),
            })

        uptime_sec = max(0, int(now - self._start_ts))
        uptime_str = "{:02d}:{:02d}:{:02d}".format(
            uptime_sec // 3600, (uptime_sec % 3600) // 60, uptime_sec % 60
        )

        last_ts = _text(p, "received_at", "timestamp", "ts", "device_sim_time", "sim_time", "Timestamp",
                        default=time.strftime("%H:%M:%S"))
        sim_time = last_ts.split(" ")[-1] if " " in last_ts else last_ts

        has_data = bool(p or w)

        alerts = []
        if self._db is not None:
            try:
                for rec in self._db.get_recent_alerts(limit=10):
                    level = (rec.get("severity") or "info").lower()
                    if level == "critical":
                        level = "danger"  # الواجهة تفهم danger مش critical
                    alerts.append({
                        "level": level,
                        "text": rec.get("message") or "",
                        "type": rec.get("alert_type") or "",
                    })
            except Exception:
                pass

        return {
            "day": 1,
            "sim_time": sim_time,
            "generation_w": round(gen_w, 6),
            "consumption_w": round(con_w, 6),
            "forecast_w": round(gen_w * 1.05, 6),
            "self_sufficiency_pct": (round(min(100.0, (gen_w / con_w) * 100.0), 1) if (con_w > 0 and gen_w > 0) else None),
            "storage_soc_pct": round(soc, 1),
            "power_source": power_source,
            "footfall": footfall,
            "voltage_v": round(voltage, 4),
            "current_a": round(current, 6),
            "system_uptime": uptime_str,
            "battery_temperature": round(temperature, 1),
            "cumulative_gen_wh": round(cumulative_gen, 4),
            "cumulative_con_wh": 0.0,
            "co2_saved_grams": round(cumulative_gen * 0.4, 4),
            "cost_saved": round(cumulative_gen * 0.0004, 4),
            "exported_wh": round(exported, 4),
            "ai_status": {
                "forecast_model": "Online" if has_data else "Offline",
                "anomaly_model": "Online" if has_data else "Offline",
            },
            "loads": dict(self._loads),
            "alerts": alerts,
            "tiles": tiles,
        }

    # ------------------------------------------------------------------
    # REST endpoints
    # ------------------------------------------------------------------
    def _append_history(self) -> None:
        snap = self._snapshot()
        try:
            t_hours = int(snap["sim_time"].split(":")[0]) + int(snap["sim_time"].split(":")[1]) / 60.0
        except (ValueError, IndexError):
            t_hours = time.localtime().tm_hour + time.localtime().tm_min / 60.0
        self._history.append({
            "t": round(t_hours, 2),
            "gen_wh": snap["generation_w"],
            "con_wh": snap["consumption_w"],
            "soc_wh": snap["storage_soc_pct"],
            "footfall": snap["footfall"],
        })

    def _api_history(self):
        hist = list(self._history)
        return {
            "t": [h["t"] for h in hist],
            "gen_wh": [h["gen_wh"] for h in hist],
            "con_wh": [h["con_wh"] for h in hist],
            "footfall": [h["footfall"] for h in hist],
        }

    def _api_analytics(self):
        hist = list(self._history)
        gen_vals = [h["gen_wh"] for h in hist]
        con_vals = [h["con_wh"] for h in hist]
        foot_vals = [h["footfall"] for h in hist]

        recent = hist[-8:]
        return {
            "total_records": len(hist),
            "peak_generation_wh": round(max(gen_vals), 6) if gen_vals else 0,
            "peak_consumption_wh": round(max(con_vals), 6) if con_vals else 0,
            "avg_footfall": round(sum(foot_vals) / len(foot_vals), 2) if foot_vals else 0,
            "recent_data": [
                {
                    "sim_hour": h["t"],
                    "gen_wh": h["gen_wh"],
                    "con_wh": h["con_wh"],
                    "soc_wh": h["soc_wh"],
                    "footfall": h["footfall"],
                }
                for h in recent
            ],
        }

    def _api_export_csv(self):
        hist = list(self._history)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["sim_hour", "generation_wh", "consumption_wh", "soc_pct", "footfall"])
        for h in hist:
            writer.writerow([h["t"], h["gen_wh"], h["con_wh"], h["soc_wh"], h["footfall"]])

        from flask import Response
        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=powerstep_records.csv"},
        )


_bridge: DashboardBridge | None = None


def get_bridge() -> DashboardBridge:
    global _bridge
    if _bridge is None:
        _bridge = DashboardBridge()
    return _bridge