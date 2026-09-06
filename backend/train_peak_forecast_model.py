"""
train_peak_forecast_model.py
=============================
Trains the time-based occupancy-level forecasting model that
realtime_inference.py uses as the third AI model in the decision pipeline.

Per the task's explicit instruction, this trains EXCLUSIVELY on
`university_simulated_week_1st.csv` (the file the team's own
`cleaning_data.py` used to generate a full, purely time-driven synthetic
week — nights/weekends idle, lecture-transition minutes peak).

This mirrors the modeling approach of the team's existing
`XGBoost_peak.py` (same features, same 3-class target, same algorithm),
but:
  1. Uses the mandated `_1st` file instead of `university_simulated_week.csv`.
  2. Saves the result under a brand-new filename
     (`peak_forecast_model_1st.joblib`) so none of the team's existing
     joblib artifacts are ever overwritten or modified.

This file only *reads* the original CSV — it never edits it.

Run with:
    python train_peak_forecast_model.py
"""

import logging

import joblib
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_peak_forecast_model")


def categorize_occupancy(count: int) -> int:
    """Same 3-level bucketing the team used in XGBoost_peak.py:
    0 = idle, 1 = light/medium occupancy (1-2 people), 2 = peak (3+ people).
    """
    if count >= 3:
        return 2
    elif count > 0:
        return 1
    return 0


def main() -> None:
    if not config.PRIMARY_TRAINING_CSV.exists():
        raise FileNotFoundError(
            f"Mandated training file not found: {config.PRIMARY_TRAINING_CSV}\n"
            "This script must be run against the original "
            "'university_simulated_week_1st.csv' file."
        )

    logger.info("Loading mandated training file: %s", config.PRIMARY_TRAINING_CSV)
    df = pd.read_csv(config.PRIMARY_TRAINING_CSV)

    required_cols = {"hour", "minute", "day_of_week", "people_count"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Training file is missing expected columns: {missing}")

    df["occupancy_level"] = df["people_count"].apply(categorize_occupancy)

    feature_cols = ["hour", "minute", "day_of_week"]
    X = df[feature_cols]
    y = df["occupancy_level"]

    logger.info("Class distribution:\n%s", y.value_counts().sort_index().to_string())

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    logger.info("Training XGBClassifier on hour/minute/day_of_week -> occupancy_level ...")
    model = xgb.XGBClassifier(eval_metric="mlogloss", random_state=42)
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    logger.info("Test accuracy: %.2f%%", accuracy * 100)
    logger.info("Classification report:\n%s", classification_report(y_test, predictions))

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, config.PEAK_FORECAST_MODEL_PATH)
    logger.info("Saved new model to: %s", config.PEAK_FORECAST_MODEL_PATH)
    logger.info(
        "Note: this is a NEW file — the team's existing "
        "xgboost_peak_predictor.joblib / xgboost_peak_predictor_new.joblib "
        "were not touched."
    )


if __name__ == "__main__":
    main()
