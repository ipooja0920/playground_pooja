import vertexai
from vertexai.generative_models import GenerativeModel, Part
import os
import pandas as pd
from datetime import date, datetime
from weather_service import get_nws_alert

# Initialize Vertex AI
# PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT") # Set this in your env
# LOCATION = "us-central1"
# vertexai.init(project=PROJECT_ID, location=LOCATION)

def generate_script(weather_data):
    """
    Generates a catchy 8-second script for a weather report based on today's data.
    An 8-second script should be about 15-20 words.
    """
    model = GenerativeModel("gemini-2.0-flash")

    hour = datetime.now().hour
    if hour < 12:
        time_of_day = "morning"
    elif hour < 17:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"

    report_date = weather_data.get("date", date.today().strftime("%B %d, %Y"))
    alert = weather_data.get("alert")  # fetched live from NWS

    alert_block = ""
    if alert and alert.get("severity") in ("Extreme", "Severe"):
        alert_block = f"""
    ⚠️  ACTIVE NWS ALERT: {alert['event']} ({alert['severity']})
    Headline: {alert['headline']}

    IMPORTANT — There is an active {alert['event']} in effect. The script MUST open with or
    urgently mention this alert. Use language like "A {alert['event']} is in effect" or
    "Blizzard Warning tonight" — make it the lead, not an afterthought.
    """

    prompt = f"""
    Generate a catchy, energetic weather report script for a female TV news anchor named Maya.
    The script must be exactly 8 seconds long when spoken (strictly 15-20 words, no more).

    Today's date: {report_date}
    Time of day: {time_of_day}
    Location: {weather_data['location']}
    Condition: {weather_data['condition']}
    Current Temp: {weather_data['temp_c']}°C (feels like {weather_data.get('feels_like_c', weather_data['temp_c'])}°C)
    High: {weather_data['high_c']}°C
    Low: {weather_data['low_c']}°C
    {alert_block}
    IMPORTANT — The studio background display already shows all temperature numbers
    (current temp, high, and low) as on-screen graphics. Do NOT repeat any of those
    exact numbers in the spoken script — the viewer can see them. Instead, use
    descriptive language for temperature (e.g. "chilly", "bitter cold", "a warm afternoon")
    and focus the script on the condition and a clear, punchy advisory.

    Rules:
    - Open with a time-appropriate greeting ("Good {time_of_day}, Storrs!")
    - If there is an active Extreme or Severe alert, lead with it urgently
    - Describe the condition vividly — do NOT quote the temperature numbers from the display
    - End with a single punchy, weather-relevant sign-off (one call to action only)
    - Use vivid, conversational language — no jargon
    - Plain text only, no stage directions, labels, or quotes
    - Do NOT repeat any phrase or advisory twice

    Example style (no alert): "Good morning Storrs! It's a bitterly cold and overcast start — heavy clouds rolling in. Bundle up tight!"
    Example style (with alert): "Good evening, Storrs! A Blizzard Warning is in effect — dangerous conditions ahead. Stay home and stay safe!"
    """

    response = model.generate_content(prompt)
    # Collapse any newlines Gemini may insert — the script is a single spoken sentence
    script_text = " ".join(response.text.strip().split())
    return script_text

def read_latest_weather_from_csv(filename="weather_report.csv"):
    """
    Reads today's latest weather row from the local CSV file and returns a weather_data dict.
    Filters by today's date so the script always reflects current conditions.
    """
    try:
        df = pd.read_csv(filename)
        if df.empty:
            print("CSV file is empty.")
            return None

        df["Date"] = pd.to_datetime(df["Date"])
        today = date.today()
        today_rows = df[df["Date"].dt.date == today]

        if today_rows.empty:
            print(f"No weather data found for today ({today}). Run sync_weather.py first.")
            return None

        latest = today_rows.iloc[-1]

        # Fetch live NWS alert — always real-time, not stored in CSV
        alert = get_nws_alert()
        if alert:
            print(f"⚠️  NWS Alert active: {alert['event']} ({alert['severity']})")

        return {
            "location": "Storrs, CT",
            "date": today.strftime("%Y-%m-%d"),
            "condition": latest["Condition"],
            "temp_c": latest["Temp (C)"],
            "feels_like_c": latest.get("Feels Like (C)", latest["Temp (C)"]),
            "high_c": latest["High (C)"],
            "low_c": latest["Low (C)"],
            "is_sunny": latest["Sunny"],
            "is_rainy": latest["Rainy"],
            "is_stormy": latest["Stormy"],
            "is_snowy": latest["Snowy"],
            "alert": alert,
        }
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return None


def save_script_locally(script_text, filename="weather_script.txt"):
    """
    Saves the generated script to a local file.
    """
    with open(filename, "w") as f:
        f.write(script_text)
    print(f"Script saved locally: {os.path.abspath(filename)}")

if __name__ == "__main__":
    # Mock data for testing
    mock_weather = {
        "location": "Storrs, CT",
        "condition": "Sunny",
        "high_c": 22,
        "low_c": 10
    }
    # Note: vertexai.init() must be called before this
    # print(generate_script(mock_weather))
