import vertexai
import os
from pathlib import Path
from weather_service import get_weather

# Load .env file from this directory if present
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())
from script_service import generate_script, read_latest_weather_from_csv, save_script_locally
from video_service import generate_weather_video, generate_video_prompt
from validator import run_all_tests, validate_video_frame
from sync_weather import sync_to_local_csv
from compositor import composite_overlay

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
        print(f"\nVideo Prompt:\n{video_prompt}\n")

        # 7. Generate Video — retry up to 3 times if frame validation fails
        # Prompt is built once above and reused for all retries unchanged
        MAX_VISUAL_RETRIES = 3
        for visual_attempt in range(1, MAX_VISUAL_RETRIES + 1):
            if visual_attempt > 1:
                print(f"\nFrame validation failed — regenerating video (visual attempt {visual_attempt}/{MAX_VISUAL_RETRIES})...")

            video_path, final_prompt = generate_weather_video(
                weather_data, script_text, project_id=project_id, location=location,
                prompt=video_prompt
            )

            if not video_path or not os.path.exists(str(video_path)):
                print("Video generation failed or output file not found.")
                break

            print(f"Video saved locally: {os.path.abspath(video_path)}")

            # 8. Post-generation: validate actual rendered frame for text accuracy
            frame_pass, frame_msg = validate_video_frame(video_path, weather_data)
            print(f"Frame Validation:        {'PASS' if frame_pass else 'FAIL'} — {frame_msg}")

            if frame_pass:
                # 9. Composite display card onto the clean video
                composite_overlay("output_video.mp4", "final_video.mp4", weather_data)
                break

            if visual_attempt == MAX_VISUAL_RETRIES:
                print("Frame validation failed after all attempts. Check the output video manually.")
    else:
        print("Tests Failed. Video will not be generated.")


if __name__ == "__main__":
    main()
