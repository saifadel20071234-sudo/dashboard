import csv, json, os, sys, threading, time
from flask import Flask, send_from_directory
from flask_cors import CORS

DATA_DIR = os.path.join("C:\\Users\\Adel\\Desktop", "الداتا")
UNI_CSV = os.path.join(DATA_DIR, "university_simulated_week.csv")
WIFI_CSV = os.path.join(DATA_DIR, "wifi_dataset (3).csv")
PIEZO_JSON_CSV = os.path.join(DATA_DIR, "live_piezo_data_json (2).csv")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashboard_bridge import get_bridge

def load_wifi(path):
    rows = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    p = json.loads(row["data"]); p["ts"] = row.get("ts",""); rows.append(p)
                except Exception: continue
    return rows

def load_uni(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    return []

def load_piezo(path):
    rows = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    p = json.loads(row["JSON_Data"]); p["timestamp"] = row.get("Timestamp",""); rows.append(p)
                except Exception: continue
    return rows

app = Flask(__name__, static_folder=ROOT, static_url_path="")
CORS(app)
bridge = get_bridge(); bridge.attach(app)

@app.route("/")
def index(): return send_from_directory(ROOT, "index.html")
@app.route("/<path:path>")
def static_files(path): return send_from_directory(ROOT, path)

def feed():
    wifi, uni, piezo = load_wifi(WIFI_CSV), load_uni(UNI_CSV), load_piezo(PIEZO_JSON_CSV)
    wi = fi = pi = 0
    while True:
        if piezo:
            bridge.on_piezo(piezo[pi % len(piezo)]); pi += 1
        if uni:
            row = uni[fi % len(uni)]
            bridge.on_wifi({"people_count": int(float(row.get("people_count",0))),
                            "device_count_raw": int(float(row.get("device_count_raw",0))),
                            "csi_variance": float(row.get("csi_variance",0))})
            if not piezo:
                bridge.on_piezo({"tile_id": f"Tile_{(fi%16)+1}", "voltage": float(row.get("piezo_voltage",0)),
                                 "avg_watt": float(row.get("piezo_avg_watt",0)),
                                 "step_status": "PRESSED" if float(row.get("people_count",0))>0 else "IDLE"})
            fi += 1
        if wifi:
            bridge.on_wifi(wifi[wi % len(wifi)]); wi += 1
        time.sleep(0.5)

if __name__ == "__main__":
    threading.Thread(target=feed, daemon=True).start()
    app.run(host="127.0.0.1", port=8001, threaded=True)
