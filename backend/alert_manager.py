"""
alert_manager.py
=================
Watches incoming readings/predictions and fires multi-channel alerts
(Telegram / Email / on-device buzzer) when specific conditions are met:

  - Occupancy threshold exceeded (too many people detected)
  - Critical changes in power generation (sudden drop while footfall
    is still being detected -> likely tile/sensor fault) or low battery
  - Persistent mismatch between the AI's live sensor readings and either
    the firmware's own estimate or the time-based forecast model
    (genuine anomaly, not a single noisy sample)
  - A sensing channel going silent (offline watchdog)

Every alert is deduplicated with a per-alert-type cooldown so an ongoing
condition doesn't flood the channels, and every alert (delivered or not) is
logged to the database via database_manager.py.

Note on the buzzer: neither ae8.ino nor the WiFi ESP32 firmware expose any
actuator/GPIO-controlled buzzer, and the Golden Rule forbids adding one to
those files. So "on-device" here means the machine running main_system.py
sounds a local alert tone. `set_hardware_buzzer_callback()` is provided so a
real GPIO/serial-attached buzzer can be wired in later without touching this
file's internals.
"""

from __future__ import annotations

import logging
import smtplib
import time
from collections import defaultdict
from email.mime.text import MIMEText
from typing import Any, Callable, Optional

import requests

import config
from database_manager import DatabaseManager

logger = logging.getLogger("alert_manager")


def _local_buzzer_beep() -> None:
    """Best-effort, dependency-free local alert tone. Never raises."""
    try:
        import winsound  # type: ignore

        winsound.Beep(1500, 400)
    except ImportError:
        try:
            # Terminal bell fallback for non-Windows systems.
            print("\a", end="", flush=True)
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Local buzzer failed: %s", exc)


class AlertManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self._last_sent: dict[str, float] = {}
        self._mismatch_streak: dict[str, int] = defaultdict(int)
        self._hardware_buzzer: Optional[Callable[[], None]] = None

    def set_hardware_buzzer_callback(self, callback: Callable[[], None]) -> None:
        """Allows swapping in a real GPIO/serial-triggered buzzer later
        without editing this file."""
        self._hardware_buzzer = callback

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------
    def _send_telegram(self, message: str) -> bool:
        if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
            logger.debug("Telegram not configured; skipping.")
            return False
        try:
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
            resp = requests.post(
                url,
                json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message},
                timeout=5,
            )
            if resp.status_code != 200:
                logger.warning("Telegram alert failed (%s): %s", resp.status_code, resp.text)
                return False
            return True
        except requests.RequestException as exc:
            logger.warning("Telegram alert failed: %s", exc)
            return False

    def _send_email(self, subject: str, message: str) -> bool:
        if not (config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASSWORD and config.ALERT_EMAIL_TO):
            logger.debug("Email not configured; skipping.")
            return False
        try:
            msg = MIMEText(message)
            msg["Subject"] = subject
            msg["From"] = config.SMTP_USER
            msg["To"] = config.ALERT_EMAIL_TO

            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_USER, [config.ALERT_EMAIL_TO], msg.as_string())
            return True
        except Exception as exc:
            logger.warning("Email alert failed: %s", exc)
            return False

    def _trigger_buzzer(self) -> bool:
        if not config.ENABLE_LOCAL_BUZZER:
            return False
        try:
            if self._hardware_buzzer is not None:
                self._hardware_buzzer()
            else:
                _local_buzzer_beep()
            return True
        except Exception as exc:
            logger.warning("Buzzer trigger failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Dispatch with cooldown + logging
    # ------------------------------------------------------------------
    def _dispatch(self, alert_type: str, severity: str, message: str) -> None:
        now = time.monotonic()
        last = self._last_sent.get(alert_type)
        if last is not None and (now - last) < config.ALERT_COOLDOWN_SECONDS:
            logger.debug("Alert '%s' suppressed (cooldown active).", alert_type)
            return

        telegram_ok = self._send_telegram(f"[{severity.upper()}] {message}")
        email_ok = self._send_email(f"PowerStep alert: {alert_type}", message)
        buzzer_ok = self._trigger_buzzer()

        delivered_channels = [
            name
            for name, ok in (("telegram", telegram_ok), ("email", email_ok), ("buzzer", buzzer_ok))
            if ok
        ]
        delivered = len(delivered_channels) > 0

        logger.warning("ALERT [%s/%s]: %s (channels: %s)", alert_type, severity, message, delivered_channels or "none")

        self.db.insert_alert(
            triggered_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            alert_type=alert_type,
            severity=severity,
            message=message,
            channels=",".join(delivered_channels),
            delivered=delivered,
        )
        self._last_sent[alert_type] = now

    # ------------------------------------------------------------------
    # Evaluators — called by main_system.py after each processed reading
    # ------------------------------------------------------------------
    def evaluate_piezo(self, record: dict[str, Any]) -> None:
        soc = record.get("storage_soc_pct")
        if soc is not None and soc < config.LOW_BATTERY_SOC_THRESHOLD:
            self._dispatch(
                "low_battery",
                "warning",
                f"Piezo storage SOC is low: {soc:.1f}% (threshold {config.LOW_BATTERY_SOC_THRESHOLD}%).",
            )

        recent = self.db.get_recent_piezo(limit=config.POWER_TREND_WINDOW)
        if len(recent) >= config.POWER_TREND_WINDOW:
            history = recent[1:]  # exclude the just-inserted current record
            avg_gen = sum(r["generation_w"] or 0.0 for r in history) / max(len(history), 1)
            current_gen = record.get("generation_w") or 0.0
            footfall_active = bool(record.get("footfall")) or bool(record.get("ai_step_detected"))

            if avg_gen > 0 and footfall_active:
                drop_ratio = 1.0 - (current_gen / avg_gen)
                if drop_ratio >= config.POWER_DROP_RATIO_THRESHOLD:
                    self._dispatch(
                        "power_drop",
                        "critical",
                        f"Generated power dropped {drop_ratio * 100:.0f}% below the recent "
                        f"average ({current_gen:.2e}W vs ~{avg_gen:.2e}W) while footfall is "
                        "still being detected — possible tile fault.",
                    )

    def evaluate_wifi(self, record: dict[str, Any]) -> None:
        node_id = record.get("node_id", "unknown")
        final_count = record.get("final_people_count") or 0

        if final_count > config.OCCUPANCY_ALERT_THRESHOLD:
            self._dispatch(
                "occupancy_exceeded",
                "warning",
                f"[{node_id}] Occupancy of {final_count} exceeds the alert "
                f"threshold of {config.OCCUPANCY_ALERT_THRESHOLD}.",
            )

        if record.get("mismatch_flag"):
            self._mismatch_streak[node_id] += 1
        else:
            self._mismatch_streak[node_id] = 0

        if self._mismatch_streak[node_id] >= config.MISMATCH_STREAK_THRESHOLD:
            self._dispatch(
                "sensor_ai_mismatch",
                "warning",
                f"[{node_id}] AI occupancy model has disagreed with the firmware's "
                f"own estimate for {self._mismatch_streak[node_id]} consecutive readings "
                "— sensor or model may need attention.",
            )
            self._mismatch_streak[node_id] = 0  # avoid re-alerting every single reading after

        expected_level = record.get("expected_occupancy_level")
        if expected_level == 0 and final_count >= 3:
            self._dispatch(
                "unexpected_occupancy",
                "info",
                f"[{node_id}] {final_count} people detected during a time slot the "
                "forecast model expects to be idle.",
            )

    def check_device_liveness(self, last_seen: dict[str, Optional[float]]) -> None:
        """last_seen: {'piezo': monotonic_timestamp_or_None, 'wifi': ...}"""
        now = time.monotonic()

        piezo_last = last_seen.get("piezo")
        if piezo_last is None or (now - piezo_last) > config.PIEZO_OFFLINE_TIMEOUT_SEC:
            self._dispatch(
                "piezo_offline",
                "critical",
                f"No piezo readings received in over {config.PIEZO_OFFLINE_TIMEOUT_SEC:.0f}s.",
            )

        wifi_last = last_seen.get("wifi")
        if wifi_last is None or (now - wifi_last) > config.WIFI_OFFLINE_TIMEOUT_SEC:
            self._dispatch(
                "wifi_offline",
                "critical",
                f"No WiFi occupancy readings received in over {config.WIFI_OFFLINE_TIMEOUT_SEC:.0f}s.",
            )
