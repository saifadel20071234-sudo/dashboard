import pandas as pd
import sqlite3

def import_csvs():
    conn = sqlite3.connect(r"C:\Users\Adel\Desktop\dashboard\backend\runtime_data\powerstep_system.db")
    cursor = conn.cursor()

    count = 0
    
    try:
        # Import media_1788728343337.csv (has both)
        df1 = pd.read_csv(r"C:\Users\Adel\.gemini\antigravity-ide\brain\92beffa3-b728-41b2-a4cf-571524cce013\.user_uploaded\media_1788728343337.csv")
        for _, row in df1.iterrows():
            ts = str(row['timestamp']).replace(" ", "T")
            gen = float(row['piezo_avg_watt'])
            foot = int(row['people_count'])
            soc = 80.0 # mock
            
            cursor.execute('''
                INSERT INTO piezo_readings (received_at, generation_w, storage_soc_pct, footfall)
                VALUES (?, ?, ?, ?)
            ''', (ts, gen, soc, foot))
            count += 1
    except Exception as e:
        print(f"Error df1: {e}")

    try:
        # Import media_1788728343260.csv (has piezo and SOC)
        df2 = pd.read_csv(r"C:\Users\Adel\.gemini\antigravity-ide\brain\92beffa3-b728-41b2-a4cf-571524cce013\.user_uploaded\media_1788728343260.csv")
        for _, row in df2.iterrows():
            ts = str(row['Timestamp']).replace(" ", "T")
            gen = float(row['Power (W)'])
            soc = float(row['SOC (%)'])
            foot = 1 if row['Step Status'] == 'PRESSED' else 0
            
            cursor.execute('''
                INSERT INTO piezo_readings (received_at, generation_w, storage_soc_pct, footfall)
                VALUES (?, ?, ?, ?)
            ''', (ts, gen, soc, foot))
            count += 1
    except Exception as e:
        print(f"Error df2: {e}")

    conn.commit()
    conn.close()
    print(f"Successfully inserted {count} records into piezo_readings.")

if __name__ == "__main__":
    import_csvs()
