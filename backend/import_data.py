import pandas as pd
import json
import glob
import sys
from pathlib import Path

# Add backend to path so imports work correctly
sys.path.append(str(Path(__file__).parent))

from database_manager import DatabaseManager
from realtime_inference import InferenceEngine

def import_all():
    db = DatabaseManager()
    engine = InferenceEngine()

    csv_files = glob.glob(r"C:\Users\Adel\.gemini\antigravity-ide\brain\92beffa3-b728-41b2-a4cf-571524cce013\.user_uploaded\*.csv")
    
    total_piezo = 0
    total_wifi = 0

    for file in csv_files:
        print(f"Processing {file}...")
        try:
            df = pd.read_csv(file)
            for _, row in df.iterrows():
                source = row['source']
                try:
                    raw = json.loads(row['data'])
                    ts = row.get('ts')
                    
                    if source == 'piezo':
                        record = engine.process_piezo_reading(raw)
                        if ts:
                            # Replace the now() generated received_at with the historical one
                            record['received_at'] = str(ts).replace(" ", "T") 
                        db.insert_piezo_reading(record)
                        total_piezo += 1
                    elif source == 'wifi_occupancy' or source == 'wifi':
                        record = engine.process_wifi_reading(raw)
                        if ts:
                            record['received_at'] = str(ts).replace(" ", "T")
                        db.insert_wifi_reading(record)
                        total_wifi += 1
                except Exception as e:
                    # ignore bad rows
                    pass
        except Exception as e:
            print(f"Failed to read {file}: {e}")

    print(f"Done! Imported {total_piezo} piezo readings and {total_wifi} wifi readings.")

if __name__ == "__main__":
    import_all()
