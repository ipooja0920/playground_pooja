import vertexai
import os
from weather_service import get_weather
from script_service import generate_script, read_latest_weather_from_csv, save_script_locally
from video_service import generate_weather_video, generate_video_prompt
from validator import run_all_tests
from sync_weather import sync_to_local_csv

CSV_FILE = "weather_report.csv"


def main():
    # 1. Initialization
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = "us-central1"

    if not project_id:
        print("Error: GOOGLE_CLOUD_PROJECT environment variable not set.")
        return

    vertexai.init(project=project_id, location=location)

    # 2. Fetch Weather & Save to Local CSV
    print("Fetching weather for Storrs...")
    weather_data = get_weather("Storrs, CT")
    if not weather_data:
        print("Failed to fetch weather data.")
        return

    sync_to_local_csv(weather_data, CSV_FILE)

    # 3. Read Today's Data from Local CSV
    print("Reading today's weather data from CSV...")
    weather_data = read_latest_weather_from_csv(CSV_FILE)
    if not weather_data:
        print("Failed to read weather data from CSV.")
        return

    # 4. Generate Script
    print("Generating script...")
    script_text = generate_script(weather_data)
    print(f"Generated Script: {script_text}")

    # 5. Save Script Locally
    save_script_locally(script_text)

    # 6. Generate Video Prompt & Validate
    video_prompt = generate_video_prompt(weather_data, script_text)

    if run_all_tests(script_text, video_prompt, weather_data):
        print("Tests Passed! Proceeding to Video Generation...")

        # 7. Generate Video
        video_path, final_prompt = generate_weather_video(
            weather_data, script_text, project_id=project_id, location=location
        )

        if video_path and os.path.exists(video_path):
            print(f"Video saved locally: {os.path.abspath(video_path)}")
        else:
            print("Video generation failed or output file not found.")
    else:
        print("Tests Failed. Video will not be generated.")


if __name__ == "__main__":
    main()
