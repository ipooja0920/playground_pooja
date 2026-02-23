import requests
import json
import os
from datetime import date

# Storrs, CT coordinates for NWS alerts API
STORRS_LAT = 41.8084
STORRS_LON = -72.2495


def get_nws_alert(lat=STORRS_LAT, lon=STORRS_LON):
    """
    Fetches the most severe active NWS weather alert for the given coordinates.
    Returns a dict with 'event', 'headline', 'severity' or None if no active alert.
    The NWS API is free and requires no API key.
    """
    try:
        url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
        response = requests.get(url, headers={"User-Agent": "uconn-weather-reporter"}, timeout=10)
        response.raise_for_status()
        features = response.json().get("features", [])
        if not features:
            return None
        # Severity ranking: Extreme > Severe > Moderate > Minor
        severity_rank = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1}
        best = max(features, key=lambda f: severity_rank.get(f["properties"].get("severity", "Minor"), 0))
        props = best["properties"]
        return {
            "event": props.get("event", ""),
            "headline": props.get("headline", ""),
            "severity": props.get("severity", ""),
        }
    except Exception as e:
        print(f"Warning: Could not fetch NWS alerts: {e}")
        return None


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
        feels_like_c = current_condition['FeelsLikeC']

        # Get today's forecast (first day in 'weather' list)
        today_forecast = data['weather'][0]
        max_temp = today_forecast['maxtempC']
        min_temp = today_forecast['mintempC']

        # Fetch active NWS weather alert (blizzard warning, winter storm, etc.)
        alert = get_nws_alert()

        weather_report = {
            "location": location,
            "date": date.today().strftime("%Y-%m-%d"),
            "condition": weather_desc,
            "temp_c": temp_c,
            "feels_like_c": feels_like_c,
            "high_c": max_temp,
            "low_c": min_temp,
            "is_sunny": "sunny" in weather_desc.lower() or "clear" in weather_desc.lower(),
            "is_rainy": "rain" in weather_desc.lower() or "drizzle" in weather_desc.lower(),
            "is_stormy": "thunder" in weather_desc.lower() or "storm" in weather_desc.lower(),
            "is_snowy": "snow" in weather_desc.lower(),
            "alert": alert,  # None if no active alert, else {"event", "headline", "severity"}
        }

        if alert:
            print(f"⚠️  NWS Alert: {alert['event']} ({alert['severity']})")

        return weather_report
    except Exception as e:
        print(f"Error fetching weather: {e}")
        return None

if __name__ == "__main__":
    report = get_weather()
    if report:
        print(json.dumps(report, indent=2))
