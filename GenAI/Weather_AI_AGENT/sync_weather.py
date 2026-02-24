import pandas as pd
import os
from weather_service import get_weather
from datetime import datetime

def sync_to_local_csv(weather_data, filename="weather_report.csv"):
    """
    Appends the weather data to a local CSV file.
    """
    now = datetime.now()
    alert = weather_data.get('alert')
    df_new = pd.DataFrame([{
        "Date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "Condition": weather_data['condition'],
        "Temp (C)": weather_data['temp_c'],
        "Feels Like (C)": weather_data.get('feels_like_c', ''),
        "High (C)": weather_data['high_c'],
        "Low (C)": weather_data['low_c'],
        "Sunny": weather_data.get('is_sunny', False),
        "Rainy": weather_data.get('is_rainy', False),
        "Stormy": weather_data.get('is_stormy', False),
        "Snowy": weather_data.get('is_snowy', False),
        "Cloudy": weather_data.get('is_cloudy', False),
        "Foggy": weather_data.get('is_foggy', False),
        "Hazy": weather_data.get('is_hazy', False),
        "Icy": weather_data.get('is_icy', False),
        "Windy": weather_data.get('is_windy', False),
        "Alert Event": alert['event'] if alert else '',
        "Alert Severity": alert['severity'] if alert else '',
        "Alert Headline": alert['headline'] if alert else '',
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
