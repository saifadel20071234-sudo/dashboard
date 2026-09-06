"""
realtime_inference.py
======================
Receives one live reading at a time (from either sensing channel) and turns
it into a fully-scored record: original telemetry + AI predictions, ready to
be persisted (database_manager.py) and monitored (alert_manager.py).

This file only ever *loads and calls* the team's pre-trained models via
joblib — it never retrains, edits, or overwrites them.

Three AI models are combined here:
  1. piezo_step_model.joblib      -> was this a genuine footstep? (Voltage, Power)
  2. wifi_occupancy_model.joblib  -> is the area occupied at all? (csi_variance)
     + wifi_count_model.joblib    -> if occupied, how many people? (device_count_raw)
  3. peak_forecast_model_1st.joblib -> what occupancy level is *expected* right
     now, purely from time-of-day/day-of-week (trained on
     university_simulated_week_1st.csv by train_peak_forecast_model.py)

The third model gives the system a time-based expectation to compare live
sensor readings against, which is what lets alert_manager.py flag genuine
anomalies (e.g. a "peak" reading during an expected-idle 3am slot) instead of
just reacting to raw thresholds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import joblib
import pandas as pd

import config

logger = logging.getLogger("realtime_inference")

OCCUPANCY_LEVEL_LABELS = {0: "idle", 1: "medium", 2: "peak"}


_warned_missing: set[str] = set()


def _require_model(path: Path):
    if not path.exists():
        key = str(path)
        if key not in _warned_missing:
            _warned_missing.add(key)
            logger.warning(
                "Model file not found (AI inference for this channel will be "
                "disabled until it appears): %s",
                path,
            )
        return None
    return joblib.load(path)


def _frame_for_model(model, values: dict) -> pd.DataFrame:
    """Build a single-row DataFrame whose columns EXACTLY match the order the
    model was trained with (model.feature_names_in_). scikit-learn validates
    both the *names* and the *order* of DataFrame columns at predict time, so
    this indirection (rather than hardcoding column order) protects us from
    silent mis-predictions if a model is ever retrained with reordered
    features.
    """
    if hasattr(model, "feature_names_in_"):
        ordered_cols = list(model.feature_names_in_)
    else:
        ordered_cols = list(values.keys())
    row = {col: values[col] for col in ordered_cols}
    return pd.DataFrame([row], columns=ordered_cols)


@dataclass
class PiezoInferenceResult:
    ai_step_detected: bool
    ai_step_confidence: Optional[float]


@dataclass
class WifiInferenceResult:
    ai_is_occupied: bool
    ai_occupancy_confidence: Optional[float]
    ai_people_estimate: int
    final_people_count: int
    expected_occupancy_level: int
    expected_occupancy_label: str
    mismatch: bool


class InferenceEngine:
    """Loads all models once and exposes cheap per-reading prediction calls."""

    def __init__(
        self,
        piezo_model_path: Path = config.PIEZO_STEP_MODEL_PATH,
        wifi_occupancy_model_path: Path = config.WIFI_OCCUPANCY_MODEL_PATH,
        wifi_count_model_path: Path = config.WIFI_COUNT_MODEL_PATH,
        peak_forecast_model_path: Path = config.PEAK_FORECAST_MODEL_PATH,
    ):
        logger.info("Loading piezo step model from %s", piezo_model_path)
        self.piezo_model = _require_model(piezo_model_path)

        logger.info("Loading wifi occupancy model from %s", wifi_occupancy_model_path)
        self.wifi_occupancy_model = _require_model(wifi_occupancy_model_path)

        logger.info("Loading wifi count model from %s", wifi_count_model_path)
        self.wifi_count_model = _require_model(wifi_count_model_path)

        logger.info("Loading peak forecast model from %s", peak_forecast_model_path)
        self.peak_forecast_model = _require_model(peak_forecast_model_path)

        logger.info("All models loaded successfully.")

    # ------------------------------------------------------------------
    # Low-level, single-purpose predictors
    # ------------------------------------------------------------------
    def predict_piezo_step(self, voltage_v: float, generation_w: float) -> PiezoInferenceResult:
        if self.piezo_model is None:
            # No model available yet — defer to the firmware's own threshold.
            return PiezoInferenceResult(ai_step_detected=True, ai_step_confidence=None)
        frame = _frame_for_model(
            self.piezo_model, {"Voltage (V)": voltage_v, "Power (W)": generation_w}
        )
        pred = int(self.piezo_model.predict(frame)[0])
        confidence = None
        if hasattr(self.piezo_model, "predict_proba"):
            proba = self.piezo_model.predict_proba(frame)[0]
            confidence = float(max(proba))
        return PiezoInferenceResult(ai_step_detected=bool(pred), ai_step_confidence=confidence)

    def predict_wifi_occupancy(self, csi_variance: float) -> tuple[bool, Optional[float]]:
        if self.wifi_occupancy_model is None:
            return True, None
        frame = _frame_for_model(self.wifi_occupancy_model, {"csi_variance": csi_variance})
        pred = int(self.wifi_occupancy_model.predict(frame)[0])
        confidence = None
        if hasattr(self.wifi_occupancy_model, "predict_proba"):
            proba = self.wifi_occupancy_model.predict_proba(frame)[0]
            confidence = float(max(proba))
        return bool(pred), confidence

    def predict_wifi_count(self, device_count_raw: float) -> int:
        if self.wifi_count_model is None:
            return 0
        frame = _frame_for_model(self.wifi_count_model, {"device_count_raw": device_count_raw})
        return int(self.wifi_count_model.predict(frame)[0])

    def predict_peak_level(self, when: datetime) -> tuple[int, str]:
        if self.peak_forecast_model is None:
            return 0, OCCUPANCY_LEVEL_LABELS[0]
        frame = _frame_for_model(
            self.peak_forecast_model,
            {"hour": when.hour, "minute": when.minute, "day_of_week": when.weekday()},
        )
        level = int(self.peak_forecast_model.predict(frame)[0])
        return level, OCCUPANCY_LEVEL_LABELS.get(level, "unknown")

    # ------------------------------------------------------------------
    # High-level per-channel processing (raw device JSON -> scored record)
    # ------------------------------------------------------------------
    def process_piezo_reading(self, raw: dict[str, Any]) -> dict[str, Any]:
        """raw is one decoded JSON object exactly as emitted by ae8.ino."""
        voltage_v = float(raw.get("voltage_v", 0.0))
        current_a = float(raw.get("current_a", 0.0))
        generation_w = float(raw.get("generation_w", 0.0))
        cumulative_gen_wh = float(raw.get("cumulative_gen_wh", 0.0))
        storage_soc_pct = float(raw.get("storage_soc_pct", 0.0))
        power_source = raw.get("power_source", "unknown")
        footfall = int(raw.get("footfall", 0))

        tiles = raw.get("tiles") or []
        tile0 = tiles[0] if tiles else {}

        result = self.predict_piezo_step(voltage_v, generation_w)

        return {
            "received_at": datetime.now().isoformat(timespec="seconds"),
            "device_day": raw.get("day"),
            "device_sim_time": raw.get("sim_time"),
            "device_uptime": raw.get("system_uptime"),
            "voltage_v": voltage_v,
            "current_a": current_a,
            "generation_w": generation_w,
            "cumulative_gen_wh": cumulative_gen_wh,
            "storage_soc_pct": storage_soc_pct,
            "power_source": power_source,
            "footfall": footfall,
            "ai_step_detected": int(result.ai_step_detected),
            "ai_step_confidence": result.ai_step_confidence,
            "tile_id": tile0.get("id"),
            "tile_efficiency_pct": tile0.get("efficiency_pct"),
            "tile_total_steps": tile0.get("total_steps"),
        }

    def process_wifi_reading(self, raw: dict[str, Any]) -> dict[str, Any]:
        """raw is the JSON body POSTed by esp32_probe_csi_combined__1_.ino to
        /api/ingest: {people_count, device_count_raw, csi_variance,
        csi_people_estimate}.
        """
        now = datetime.now()
        device_count_raw = float(raw.get("device_count_raw", 0) or 0)
        csi_variance = float(raw.get("csi_variance", 0.0) or 0.0)
        csi_people_estimate = int(raw.get("csi_people_estimate", 0) or 0)
        firmware_people_count = int(raw.get("people_count", 0) or 0)

        is_occupied, occ_confidence = self.predict_wifi_occupancy(csi_variance)

        ai_people_estimate = 0
        if is_occupied and device_count_raw > 0:
            ai_people_estimate = self.predict_wifi_count(device_count_raw)

        expected_level, expected_label = self.predict_peak_level(now)

        # Decision logic: the firmware already fuses probe-request device
        # counting with its own CSI heuristic into `people_count`, so that
        # remains the primary live estimate. Our independently-trained
        # wifi_count_model acts as a cross-check; if it disagrees strongly
        # with the firmware while also disagreeing with the occupancy model,
        # we lean on whichever value is non-zero and larger, favoring not
        # under-counting occupancy.
        if is_occupied:
            final_people_count = max(firmware_people_count, ai_people_estimate)
        else:
            # Model says empty. Trust it unless the firmware itself is
            # confidently reporting people (defer to the firmware in that
            # tie-break, since it directly counts real MAC addresses).
            final_people_count = firmware_people_count

        # Mismatch: AI's binary occupancy call disagrees with what the
        # firmware itself believes (people_count > 0). Single-reading flag —
        # alert_manager.py is responsible for requiring a persistent streak
        # before actually alerting on it.
        firmware_says_occupied = firmware_people_count > 0
        mismatch = is_occupied != firmware_says_occupied

        return {
            "received_at": now.isoformat(timespec="seconds"),
            "node_id": config.WIFI_NODE_ID,
            "device_count_raw": device_count_raw,
            "csi_variance": csi_variance,
            "csi_people_estimate": csi_people_estimate,
            "firmware_people_count": firmware_people_count,
            "ai_is_occupied": int(is_occupied),
            "ai_occupancy_confidence": occ_confidence,
            "ai_people_estimate": ai_people_estimate,
            "final_people_count": final_people_count,
            "expected_occupancy_level": expected_level,
            "expected_occupancy_label": expected_label,
            "mismatch_flag": int(mismatch),
        }
