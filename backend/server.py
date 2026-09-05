import asyncio
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PowerStep Grid Backend")

# Allow Frontend to connect from any port (e.g., Live Server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Fake Data Generators (Simulator)
# ---------------------------------------------------------
def generate_live_data():
    """Generates realistic live telemetry matching API_SPEC.md"""
    gen_w = round(random.uniform(3.0, 8.0), 1)
    con_w = round(random.uniform(2.0, 6.0), 1)
    
    return {
        "day": 1,
        "sim_time": "12:00:00", # Real time logic could be added
        "generation_w": gen_w,
        "consumption_w": con_w,
        "forecast_w": round(gen_w + random.uniform(-1, 1.5), 1),
        "self_sufficiency_pct": min(100, round((gen_w / max(0.1, con_w)) * 100)),
        "storage_soc_pct": round(random.uniform(70.0, 95.0), 1),
        "power_source": "harvested" if gen_w >= con_w else "grid",
        "footfall": random.randint(5, 25),
        "voltage_v": round(random.uniform(12.0, 12.8), 1),
        "current_a": round(random.uniform(0.1, 0.8), 2),
        "system_uptime": "05:12:00",
        "battery_temperature": round(random.uniform(22.0, 26.0), 1),
        "cumulative_gen_wh": 145.3210,
        "cumulative_con_wh": 98.4520,
        "co2_saved_grams": 58.12,
        "cost_saved": 0.042,
        "exported_wh": 12.4,
        "ai_status": {
            "forecast_model": "Online",
            "anomaly_model": "Online"
        },
        "loads": {
            "load_1": { "name": "Main Lights", "state": "ON" },
            "load_2": { "name": "AC Unit", "state": "Standby" if con_w < 4 else "ON" },
            "load_3": { "name": "Sensors", "state": "ON" }
        },
        "alerts": [],
        "tiles": [
            { "id": i, "stepped_on": random.choice([True, False, False]), "efficiency_pct": round(random.uniform(75.0, 100.0), 1) }
            for i in range(1, 17)
        ]
    }

# ---------------------------------------------------------
# REST APIs
# ---------------------------------------------------------
@app.get("/api/history")
def get_history():
    return {
        "t": [10.0, 10.25, 10.5, 10.75, 11.0, 11.25, 11.5, 11.75],
        "gen_wh": [5.1, 5.3, 5.0, 5.2, 5.8, 6.1, 5.9, 6.2],
        "con_wh": [3.2, 3.4, 3.1, 3.3, 4.0, 4.2, 3.8, 3.9],
        "footfall": [14, 12, 18, 15, 20, 22, 19, 16]
    }

@app.get("/api/analytics/summary")
def get_analytics_summary():
    return {
        "total_records": 1500,
        "peak_generation_wh": 7.2,
        "peak_consumption_wh": 6.1,
        "avg_footfall": 15.4,
        "recent_data": [
            { "sim_hour": 10.0, "gen_wh": 5.1, "con_wh": 3.2, "soc_wh": 80.1, "footfall": 14 },
            { "sim_hour": 10.5, "gen_wh": 5.0, "con_wh": 3.1, "soc_wh": 81.2, "footfall": 18 },
            { "sim_hour": 11.0, "gen_wh": 5.8, "con_wh": 4.0, "soc_wh": 82.5, "footfall": 20 },
            { "sim_hour": 11.5, "gen_wh": 5.9, "con_wh": 3.8, "soc_wh": 83.1, "footfall": 19 }
        ]
    }

# ---------------------------------------------------------
# WebSocket (Live Telemetry)
# ---------------------------------------------------------
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = generate_live_data()
            
            # 10% chance to simulate a random AI alert
            if random.random() < 0.1:
                data["alerts"].append({"level": "warning", "text": "انخفاض طفيف في كفاءة البلاطة رقم 4"})
                
            await websocket.send_json(data)
            await asyncio.sleep(1)  # send every 1 second
    except WebSocketDisconnect:
        print("Client disconnected")

# Run with: uvicorn server:app --reload
