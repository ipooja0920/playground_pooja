import pandas as pd
import os
from weather_service import get_weather
from datetime import datetime

def sync_to_local_csv(weather_data, filename="weather_report.csv"):
    """
    Appends the weather data to a local CSV file.
    """
    now = datetime.now()
    df_new = pd.DataFrame([{
        "Date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "Condition": weather_data['condition'],
        "Temp (C)": weather_data['temp_c'],
        "High (C)": weather_data['high_c'],
        "Low (C)": weather_data['low_c'],
        "Sunny": weather_data['is_sunny'],
        "Rainy": weather_data['is_rainy'],
        "Stormy": weather_data['is_stormy'],
        "Snowy": weather_data['is_snowy']
    }])

    if os.path.exists(filename):
        df_new.to_csv(filename, mode='a', header=False, index=False)
    else:
        df_new.to_csv(filename, index=False)

    print(f"CSV updated: {os.path.abspath(filename)}")

def main():
    print("Step 1: Fetching current weather for Storrs...")
    weather_data = get_weather("Storrs, CT")

    if weather_data:
        print(f"Current Condition: {weather_data['condition']} ({weather_data['temp_c']}°C)")
        sync_to_local_csv(weather_data)
    else:
        print("Failed to fetch weather data.")

if __name__ == "__main__":
    main()
