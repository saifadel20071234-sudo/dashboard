"""
main_system.py
===============
The Bridge: the single entry point that wires the ESP devices' outputs to
the AI inference engine, the database, and the alert manager, and runs the
whole thing as one long-lived process.

Two live ingestion channels, both dictated by the existing (unmodified)
firmware:

  1. WiFi occupancy — esp32_probe_csi_combined__1_.ino POSTs JSON to
     http://<this host>:8000/api/ingest every 5s. We run a Flask server on
     that exact host/route to receive it (host/port are configurable, but
     default to what the firmware hardcodes).

  2. Piezo footsteps — ae8.ino streams one JSON object per loop over
     Serial/USB at 115200 baud (no network). We open that serial port in a
     background thread and parse each line, exactly like the team's own
     python.py does for its CSV logger — but we feed the pipeline instead of
     just writing a CSV.

Each reading flows: parse -> realtime_inference.py -> database_manager.py
-> alert_manager.py. A watchdog thread periodically checks that both
channels are still alive.

Run with:
    python main_system.py
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import signal
import sys
import threading
import time
from typing import Optional

from flask import Flask, jsonify, request

import config
from alert_manager import AlertManager
from database_manager import DatabaseManager
from realtime_inference import InferenceEngine
from dashboard_bridge import get_bridge

logger = logging.getLogger("main_system")


def setup_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = config.LOG_DIR / "powerstep_system.log"

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3),
    ]
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    # Keep Flask's own request logging from drowning out our messages.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


class LivenessTracker:
    """Tiny thread-safe holder for "last time we heard from each channel"."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_seen: dict[str, Optional[float]] = {"piezo": None, "wifi": None}

    def mark(self, channel: str) -> None:
        with self._lock:
            self._last_seen[channel] = time.monotonic()

    def snapshot(self) -> dict[str, Optional[float]]:
        with self._lock:
            return dict(self._last_seen)


class PiezoSerialWorker(threading.Thread):
    """Reads ae8.ino's JSON-per-line stream over Serial and feeds it through
    the inference -> database -> alert pipeline. Never modifies or imports
    from python.py / ae8.ino — it independently re-implements only the
    parsing convention (JSON lines) that ae8.ino already documents, since
    python.py is a standalone script rather than an importable module.
    """

    def __init__(
        self,
        engine: InferenceEngine,
        db: DatabaseManager,
        alerts: AlertManager,
        liveness: LivenessTracker,
        stop_event: threading.Event,
    ):
        super().__init__(name="PiezoSerialWorker", daemon=True)
        self.engine = engine
        self.db = db
        self.alerts = alerts
        self.liveness = liveness
        self.stop_event = stop_event

    def run(self) -> None:
        try:
            import serial  # pyserial; imported lazily so the WiFi-only path
            # of this system can still run on a machine without a piezo
            # board attached / pyserial installed for testing.
        except ImportError:
            logger.error(
                "pyserial is not installed; the piezo channel cannot run. "
                "Install it with 'pip install pyserial' (see requirements.txt)."
            )
            return

        while not self.stop_event.is_set():
            try:
                logger.info(
                    "Opening piezo serial port %s @ %d baud ...",
                    config.PIEZO_SERIAL_PORT,
                    config.PIEZO_BAUD_RATE,
                )
                with serial.Serial(
                    config.PIEZO_SERIAL_PORT,
                    config.PIEZO_BAUD_RATE,
                    timeout=config.PIEZO_READ_TIMEOUT_SEC,
                ) as ser:
                    time.sleep(2)  # let the board finish resetting, same as python.py
                    logger.info("Piezo serial connected.")
                    self._read_loop(ser)
            except Exception as exc:
                logger.warning(
                    "Piezo serial unavailable (%s). Retrying in %.0fs.",
                    exc,
                    config.PIEZO_RECONNECT_INTERVAL_SEC,
                )
                self.stop_event.wait(config.PIEZO_RECONNECT_INTERVAL_SEC)

    def _read_loop(self, ser) -> None:
        while not self.stop_event.is_set():
            try:
                raw_line = ser.readline()
            except Exception as exc:
                logger.warning("Piezo serial read error: %s", exc)
                return  # fall back to run()'s reconnect loop

            if not raw_line:
                continue

            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not (line.startswith("{") and line.endswith("}")):
                continue

            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue

            try:
                record = self.engine.process_piezo_reading(raw)
                self.db.insert_piezo_reading(record)
                self.alerts.evaluate_piezo(record)
                get_bridge().on_piezo(record)
                self.liveness.mark("piezo")
            except Exception:
                logger.exception("Failed to process a piezo reading.")


class LivenessWatchdog(threading.Thread):
    def __init__(self, alerts: AlertManager, liveness: LivenessTracker, stop_event: threading.Event):
        super().__init__(name="LivenessWatchdog", daemon=True)
        self.alerts = alerts
        self.liveness = liveness
        self.stop_event = stop_event

    def run(self) -> None:
        while not self.stop_event.is_set():
            self.stop_event.wait(config.WATCHDOG_INTERVAL_SEC)
            if self.stop_event.is_set():
                break
            try:
                self.alerts.check_device_liveness(self.liveness.snapshot())
            except Exception:
                logger.exception("Liveness watchdog check failed.")


def create_app(engine: InferenceEngine, db: DatabaseManager, alerts: AlertManager, liveness: LivenessTracker) -> Flask:
    app = Flask(__name__)
    get_bridge().attach(app).set_db(db)

    @app.route("/", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "powerstep-main-system"})

    @app.route("/api/ingest", methods=["POST"])
    def ingest_wifi():
        """Matches esp32_probe_csi_combined__1_.ino's sendDataToServer():
        POST http://<host>:8000/api/ingest
        body: {"people_count", "device_count_raw", "csi_variance", "csi_people_estimate"}
        """
        raw = request.get_json(force=True, silent=True)
        if raw is None:
            return jsonify({"status": "error", "message": "invalid or missing JSON body"}), 400

        try:
            record = engine.process_wifi_reading(raw)
            db.insert_wifi_reading(record)
            alerts.evaluate_wifi(record)
            get_bridge().on_wifi(record)
            liveness.mark("wifi")
        except Exception:
            logger.exception("Failed to process a wifi reading.")
            return jsonify({"status": "error", "message": "internal processing error"}), 500

        return jsonify({"status": "ok"}), 200

    @app.route("/api/status", methods=["GET"])
    def status():
        """Convenience endpoint (not required by any firmware) to verify the
        end-to-end pipeline is alive without needing direct DB access."""
        return jsonify(
            {
                "latest_piezo": db.get_latest_piezo(1),
                "latest_wifi": db.get_latest_wifi(1),
                "recent_alerts": db.get_recent_alerts(5),
                "last_seen": liveness.snapshot(),
            }
        )

    return app


def main() -> None:
    setup_logging()
    logger.info("Starting PowerStep main system ...")

    db = DatabaseManager()
    engine = InferenceEngine()
    alerts = AlertManager(db)
    liveness = LivenessTracker()
    stop_event = threading.Event()

    piezo_worker = PiezoSerialWorker(engine, db, alerts, liveness, stop_event)
    piezo_worker.start()

    watchdog = LivenessWatchdog(alerts, liveness, stop_event)
    watchdog.start()

    app = create_app(engine, db, alerts, liveness)

    def handle_shutdown(signum, frame):
        logger.info("Shutdown signal received, stopping background workers ...")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info(
        "WiFi ingestion listening on http://%s:%d/api/ingest",
        config.WIFI_INGEST_HOST,
        config.WIFI_INGEST_PORT,
    )
    # threaded=True lets Flask handle a new POST from the ESP32 every 5s
    # without blocking on slow alert channels (Telegram/SMTP network calls).
    app.run(host=config.WIFI_INGEST_HOST, port=config.WIFI_INGEST_PORT, threaded=True)


if __name__ == "__main__":
    main()
