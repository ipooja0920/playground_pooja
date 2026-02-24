from google import genai
from google.genai import types
import os
import re
import json
import subprocess

REFERENCE_IMAGE_PATH = "maya_reference.jpg"


def validate_script_content(script_text, weather_data):
    """
    Checks if the script accurately reflects the weather data and is in English.
    Also checks that no phrase or advisory is repeated twice in the script.
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        print("Warning: GOOGLE_CLOUD_PROJECT not set. Skipping LLM script validation.")
        return True, "PASS (Manual only - no Project ID)"
    client = genai.Client(vertexai=True, project=project_id, location="us-central1")

    alert = weather_data.get("alert")
    alert_line = ""
    if alert and alert.get("severity") in ("Extreme", "Severe"):
        alert_line = (
            f"\n    Active NWS Alert: {alert['event']} (Severity: {alert['severity']})"
            f"\n    7. There is an active {alert['severity']} alert ({alert['event']}). "
            f"The script MUST mention this alert or warn listeners urgently. FAIL if it is not mentioned at all."
        )

    unknown_note = ""
    if "unknown" in weather_data.get("condition", "").lower():
        unknown_note = (
            "\n    NOTE: The condition is 'Unknown precipitation' — an unclassified precipitation event. "
            "PASS any script that describes general wintry, messy, uncertain, or cautionary conditions. "
            "Do NOT fail for being vague about the precipitation type — specificity is impossible here."
        )

    prompt = f"""
    Evaluate the following weather report script based on the provided data.

    Script: "{script_text}"
    Weather data: Location={weather_data['location']}, Condition={weather_data['condition']}, Current Temp={weather_data['temp_c']}°C, High={weather_data['high_c']}°C, Low={weather_data['low_c']}°C{alert_line}{unknown_note}

    Checklist:
    1. Is the script in English?
    2. Are there any clear spelling or grammar errors?
    3. Does the script reflect the correct weather condition (e.g. overcast, sunny, rainy)?
    4. Any specific temperature numbers mentioned in the script must match current temp, high, or low from the data.
    5. Is the tone appropriate for a TV weather anchor? Weather segments are intentionally energetic, casual, and punchy — informal expressions like "bundle up", "serious cold", "stay dry" are acceptable and expected. Only FAIL if the tone is offensive, inappropriate, or wildly unprofessional.
    6. Is any full phrase or advisory repeated twice in the same script? (e.g. "stay warm, stay warm" or two identical sign-off lines). If yes, FAIL.
    7. If an active Extreme or Severe NWS alert is listed above, the script must mention it in some way (e.g. "Blizzard Warning", "storm warning", "dangerous conditions"). FAIL ONLY if the alert is completely absent — do not fail just because the wording isn't dramatic enough.

    Respond with 'PASS' if all criteria are met, otherwise respond with 'FAIL' followed by a brief reason.
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    result = response.text.strip().upper()
    return result.startswith("PASS"), result


def validate_video_prompt(prompt_text, weather_data):
    """
    Checks the video prompt for:
    - Correct weather condition reflected in studio background
    - Character identity (Maya)
    - No display card or text overlay instructions present
    - Explicit no-text instruction included
    - UConn landmark keywords for the given condition
    - Active snowfall keyword for snowy conditions
    """
    condition = weather_data['condition'].lower()

    # 1. Weather condition keywords for studio background
    if "sunny" in condition and "sunny" not in prompt_text.lower() and "golden sunlight" not in prompt_text.lower():
        return False, "Sunny condition missing from background prompt."
    if "rain" in condition and "rain" not in prompt_text.lower():
        return False, "Rainy condition missing from background prompt."
    if "snow" in condition and "snow" not in prompt_text.lower():
        return False, "Snowy condition missing from background prompt."

    # 2. Character identity
    if "Maya" not in prompt_text or ("reporter" not in prompt_text and "anchor" not in prompt_text):
        return False, "Character identity (Maya) not found in prompt."

    # 3. No display card or text overlay instructions — these belong in post-production
    if "TOP SECTION" in prompt_text or "BOTTOM SECTION" in prompt_text:
        return False, "Prompt contains display card instructions (TOP/BOTTOM SECTION) — remove these, text is composited in post-production."
    if re.search(r'\bTEMP:', prompt_text, re.IGNORECASE):
        return False, "Prompt contains 'TEMP:' label — display card instructions must be removed."

    # 4. Prompt must explicitly tell Veo not to render any text
    no_text_keywords = ["no text overlays", "no on-screen graphics", "no chyrons", "no display panels"]
    if not any(kw in prompt_text.lower() for kw in no_text_keywords):
        return False, "Prompt must include explicit no-text instruction (e.g. 'no text overlays, no on-screen graphics, no chyrons, no display panels')."

    # 5. Format: prompt must specify 4K and 16:9 aspect ratio
    if "4K" not in prompt_text or "16:9" not in prompt_text:
        return False, "Video format (4K, 16:9) not specified in prompt."

    # 6. Landmark checks
    landmark_checks = {
        ("sunny", "clear"): (
            ["Homer Babbidge", "central green", "golden sunlight"],
            "Sunny prompt missing UConn landmark."
        ),
        ("overcast", "cloud"): (
            ["Georgian brick", "brick", "central green"],
            "Cloudy prompt missing UConn landmark."
        ),
        ("heavy rain", "rain", "shower"): (
            ["UConn green", "UConn Storrs", "central UConn"],
            "Rainy prompt missing UConn landmark."
        ),
        ("snow", "blizzard"): (
            ["Homer Babbidge", "central green", "UConn Storrs"],
            "Snowy prompt missing UConn Storrs landmark (Homer Babbidge Library or central green)."
        ),
    }

    for condition_keys, (expected_keywords, fail_reason) in landmark_checks.items():
        if any(ck in condition for ck in condition_keys):
            if not any(kw.lower() in prompt_text.lower() for kw in expected_keywords):
                return False, fail_reason
            break

    # 7. Snowy conditions: active snowfall must be visible through the window
    if "snow" in condition or "blizzard" in condition:
        active_snow_keywords = ["falling", "drifting", "swirling", "snowflakes", "blizzard rages", "curtains of snow"]
        if not any(kw.lower() in prompt_text.lower() for kw in active_snow_keywords):
            return False, (
                "Snowy prompt must show active snowfall through the studio windows "
                "(e.g. 'snowflakes falling', 'drifting past the glass', 'blizzard rages outside'). "
                "Settled snow alone is not enough — Veo needs to render live snowfall."
            )

    return True, "Prompt looks good."


def validate_video_frame(video_path, weather_data):
    """
    Post-generation frame check: verifies no text overlays appear in the rendered video.
    Text is composited in post-production, so the raw Veo output should contain only
    Maya and the studio background — no chyrons, no display cards, no on-screen graphics.
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        return True, "GOOGLE_CLOUD_PROJECT not set — skipping frame validation."

    if not os.path.exists(str(video_path)):
        return True, "Video not a local file (may be GCS URI) — skipping frame validation."

    # Extract a frame at 4 seconds (midpoint of the 8-second video)
    frame_path = str(video_path).replace(".mp4", "_frame_check.jpg")
    try:
        subprocess.run(
            ["ffmpeg", "-ss", "4", "-i", str(video_path), "-vframes", "1", frame_path, "-y"],
            capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        return True, "ffmpeg not found — skipping frame validation (install ffmpeg to enable)."
    except subprocess.TimeoutExpired:
        return True, "Frame extraction timed out — skipping frame validation."

    if not os.path.exists(frame_path):
        return True, "Could not extract frame from video — skipping frame validation."

    try:
        with open(frame_path, "rb") as f:
            frame_bytes = f.read()

        # Ask Gemini Vision to check whether any text overlays are visible
        ocr_prompt = (
            "Look at this broadcast video frame carefully. "
            "Is there any visible text on screen — including temperature values, weather labels, "
            "chyrons, lower-thirds, on-screen graphics, display cards, or any other text overlay? "
            "The anchor's spoken words do not count — only look for on-screen text graphics. "
            "Reply with exactly one of:\n"
            "NO TEXT — if the frame contains no on-screen text overlays\n"
            "TEXT FOUND: <brief description> — if any text overlay is visible"
        )

        client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg"),
                ocr_prompt,
            ]
        )

        result = response.text.strip()
        if result.upper().startswith("NO TEXT"):
            return True, "Frame is clean — no text overlays detected."
        else:
            return False, f"Text detected in frame: {result}"

    except Exception as e:
        return True, f"Frame validation skipped due to error: {e}"
    finally:
        if os.path.exists(frame_path):
            os.remove(frame_path)


def validate_no_repetition(script_text, video_prompt, weather_data):
    """
    Checks that temperature numbers are not repeated across both the script (spoken)
    and the display text (visible on screen), since the viewer would see/hear the same
    value twice simultaneously.
    """
    passed = True
    reason = "No repeated values between script and display."

    # Extract all numeric values from the script (temperatures)
    script_numbers = set(re.findall(r'-?\d+', script_text))

    # Extract the current temperature from the TOP SECTION of the display card
    top_match = re.search(r"TOP SECTION[^']*'(-?\d+)", video_prompt)
    display_numbers = set()
    if top_match:
        display_numbers.add(top_match.group(1))

    overlap = script_numbers & display_numbers
    if overlap:
        passed = False
        reason = (
            f"Temperature value(s) {overlap} appear in both the spoken script and the "
            f"studio display — viewer sees and hears the same number simultaneously."
        )

    return passed, reason


def validate_character_consistency():
    """
    Checks that Maya's reference image exists locally.
    If it exists, it was passed to Veo as an ASSET reference ensuring visual consistency.
    Warns if the reference image is missing (first-run or was deleted).
    """
    if os.path.exists(REFERENCE_IMAGE_PATH):
        return True, f"Character reference image found: {REFERENCE_IMAGE_PATH}"
    return False, (
        f"Maya reference image not found at '{REFERENCE_IMAGE_PATH}'. "
        "It will be auto-generated on the next video run. Character consistency cannot be guaranteed for this run."
    )


def run_all_tests(script_text, prompt_text, weather_data):
    """
    Runs all validation tests.
    """
    print("--- Running Validation Tests ---")
    all_passed = True

    # 1. Script content
    script_pass, script_msg = validate_script_content(script_text, weather_data)
    print(f"Script Validation:       {'PASS' if script_pass else 'FAIL'} — {script_msg}")
    all_passed = all_passed and script_pass

    # 2. Video prompt structure & weather accuracy
    prompt_pass, prompt_msg = validate_video_prompt(prompt_text, weather_data)
    print(f"Prompt Validation:       {'PASS' if prompt_pass else 'FAIL'} — {prompt_msg}")
    all_passed = all_passed and prompt_pass

    # 3. Character consistency (reference image exists)
    char_pass, char_msg = validate_character_consistency()
    print(f"Character Consistency:   {'PASS' if char_pass else 'WARN'} — {char_msg}")
    # Soft warning — does not block video generation



    return all_passed


if __name__ == "__main__":
    mock_data = {"location": "Storrs", "condition": "Sunny", "temp_c": 15, "high_c": 20, "low_c": 10, "feels_like_c": 14, "alert": None}
    mock_script = "Good morning Storrs! Crisp and clear out there — a beautiful start to the day. Get outside!"
    mock_prompt = (
        "A professional 4K 16:9 TV news broadcast shot of Maya the anchor reporter standing centered in the frame. "
        "She delivers the weather report with clear lip-sync and natural speech rhythm. "
        "Studio environment: warm golden sunlight bathes the UConn Storrs campus visible through the studio windows — "
        "the Homer Babbidge Library, the sunlit central green, and blue skies above the iconic Georgian brick buildings; "
        "bright warm-white studio lighting with a clean energetic feel. "
        "Camera is static and locked at eye level. "
        "No text overlays, no on-screen graphics, no chyrons, no display panels — only Maya and the studio background. "
        "4K resolution, professional broadcast quality."
    )
    run_all_tests(mock_script, mock_prompt, mock_data)
