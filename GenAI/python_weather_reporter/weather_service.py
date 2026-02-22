import requests
import json
import os
from datetime import date

def get_weather(location="Storrs, CT"):
    """
    Fetches weather data for a given location.
    Using a public weather API (wttr.in) for demonstration if Google API is not configured.
    """
    # Note: In a production scenario, we'd use Google Custom Search or a specific Weather API key.
    # For now, we'll use wttr.in which provides a clean JSON output.
    url = f"https://wttr.in/{location}?format=j1"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        current_condition = data['current_condition'][0]
        weather_desc = current_condition['weatherDesc'][0]['value']
        temp_c = current_condition['temp_C']
        
        # Get today's forecast (first day in 'weather' list)
        today_forecast = data['weather'][0]
        max_temp = today_forecast['maxtempC']
        min_temp = today_forecast['mintempC']
        
        weather_report = {
            "location": location,
            "date": date.today().strftime("%Y-%m-%d"),
            "condition": weather_desc,
            "temp_c": temp_c,
            "high_c": max_temp,
            "low_c": min_temp,
            "is_sunny": "sunny" in weather_desc.lower() or "clear" in weather_desc.lower(),
            "is_rainy": "rain" in weather_desc.lower() or "drizzle" in weather_desc.lower(),
            "is_stormy": "thunder" in weather_desc.lower() or "storm" in weather_desc.lower(),
            "is_snowy": "snow" in weather_desc.lower()
        }
        
        return weather_report
    except Exception as e:
        print(f"Error fetching weather: {e}")
        return None

if __name__ == "__main__":
    report = get_weather()
    if report:
        print(json.dumps(report, indent=2))
