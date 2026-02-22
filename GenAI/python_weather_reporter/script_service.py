import vertexai
from vertexai.generative_models import GenerativeModel, Part
import os
import pandas as pd
from datetime import date, datetime

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

    prompt = f"""
    Generate a catchy, energetic weather report script for a female TV reporter named Maya.
    The script must be exactly 8 seconds long when spoken (strictly 15-20 words, no more).

    Today's date: {report_date}
    Time of day: {time_of_day}
    Location: {weather_data['location']}
    Condition: {weather_data['condition']}
    Current Temp: {weather_data['temp_c']}°C
    High: {weather_data['high_c']}°C
    Low: {weather_data['low_c']}°C

    Rules:
    - Open with a time-appropriate greeting ("Good {time_of_day}, Storrs!")
    - Naturally weave in the condition and at least one temperature
    - End with a punchy, weather-relevant sign-off line
    - Use vivid, conversational language — no jargon
    - Plain text only, no stage directions, labels, or quotes

    Example style: "Good morning Storrs! It's a crisp 8 degrees with clouds rolling in — high of 14 today. Bundle up!"
    """

    response = model.generate_content(prompt)
    script_text = response.text.strip()
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
        return {
            "location": "Storrs, CT",
            "date": today.strftime("%Y-%m-%d"),
            "condition": latest["Condition"],
            "temp_c": latest["Temp (C)"],
            "high_c": latest["High (C)"],
            "low_c": latest["Low (C)"],
            "is_sunny": latest["Sunny"],
            "is_rainy": latest["Rainy"],
            "is_stormy": latest["Stormy"],
            "is_snowy": latest["Snowy"],
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
