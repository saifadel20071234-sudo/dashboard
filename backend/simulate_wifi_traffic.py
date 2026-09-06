"""
simulate_wifi_traffic.py
=========================
Optional helper (not required by the task, but genuinely useful): replays
real historical rows from the team's own `wifi_dataset (2).csv` /
`wifi_dataset (3).csv` as if they were live POSTs from
esp32_probe_csi_combined__1_.ino, so you can exercise the entire
main_system.py pipeline (inference -> database -> alerts) before the
physical WiFi board is available or wired up.

This only *reads* the existing CSVs — it never modifies them.

Usage:
    1. In one terminal: python main_system.py
    2. In another:      python simulate_wifi_traffic.py
       (optionally: python simulate_wifi_traffic.py --interval 1 --count 50)
"""

from __future__ import annotations

import argparse
import json
import time

import pandas as pd
import requests

import config


def load_replay_pool() -> pd.DataFrame:
    frames = []
    for name in ["wifi_dataset (2).csv", "wifi_dataset (3).csv"]:
        path = config.MODELS_DIR / name
        if not path.exists():
            print(f"  (skipping {name}, not found)")
            continue
        df = pd.read_csv(path)
        parsed = df["data"].apply(json.loads).apply(pd.Series)
        frames.append(parsed[["people_count", "device_count_raw", "csi_variance", "csi_people_estimate"]])

    if not frames:
        raise FileNotFoundError(
            "Neither 'wifi_dataset (2).csv' nor 'wifi_dataset (3).csv' were found "
            f"under {config.MODELS_DIR}"
        )
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="main_system.py host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=config.WIFI_INGEST_PORT, help="main_system.py port")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between simulated readings")
    parser.add_argument("--count", type=int, default=0, help="number of readings to send (0 = infinite)")
    args = parser.parse_args()

    pool = load_replay_pool()
    url = f"http://{args.host}:{args.port}/api/ingest"
    print(f"Loaded {len(pool)} historical readings to replay against {url}")
    print("Press Ctrl+C to stop.\n")

    sent = 0
    try:
        while args.count == 0 or sent < args.count:
            row = pool.sample(1).iloc[0]
            payload = {
                "people_count": int(row["people_count"]),
                "device_count_raw": int(row["device_count_raw"]),
                "csi_variance": float(row["csi_variance"]),
                "csi_people_estimate": int(row["csi_people_estimate"]),
            }
            try:
                resp = requests.post(url, json=payload, timeout=5)
                print(f"-> {payload}  =>  {resp.status_code} {resp.json()}")
            except requests.RequestException as exc:
                print(f"-> {payload}  =>  FAILED: {exc}")

            sent += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\nStopped after sending {sent} readings.")


if __name__ == "__main__":
    main()
