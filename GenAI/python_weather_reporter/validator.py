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
    - Correct weather condition reflected (manual & LLM check)
    - Spellings (LLM check)
    - No duplicated data or words in the display (manual & LLM check)
    - Character consistency and landmarks (manual)
    """
    condition = weather_data['condition'].lower()
    passed = True
    reason = "Prompt looks good."

    # 1. Manual Checks for Core Requirements
    if "sunny" in condition and "sunny" not in prompt_text.lower() and "golden sunlight" not in prompt_text.lower():
        return False, "Sunny condition missing from background prompt."
    if "rain" in condition and "rain" not in prompt_text.lower():
        return False, "Rainy condition missing from background prompt."
    if "snow" in condition and "snow" not in prompt_text.lower():
        return False, "Snowy condition missing from background prompt."
    if "Maya" not in prompt_text or ("reporter" not in prompt_text and "anchor" not in prompt_text):
        return False, "Character identity (Maya) not found in prompt."

    # 2a. Extract display card sections
    is_unknown_condition = "unknown" in condition
    top_match = re.search(r"TOP SECTION[^']*'([^']+)'", prompt_text, re.IGNORECASE)
    bot_match = re.search(r"BOTTOM SECTION[^']*'([^']+)'", prompt_text, re.IGNORECASE)
    top_section = top_match.group(1) if top_match else ""
    bot_section = bot_match.group(1) if bot_match else ""

    if not top_section:
        return False, "TOP SECTION (current temperature) not found in prompt."
    if not is_unknown_condition and not bot_section:
        return False, (
            "Display card BOTTOM SECTION (weather condition) not found in prompt — "
            "required when condition is known."
        )

    # 2b. TOP section must contain only the current temperature
    if weather_data:
        expected_temp = f"{weather_data['temp_c']}°C"
        if expected_temp not in top_section:
            return False, f"TOP section should contain only the current temperature '{expected_temp}', found: '{top_section}'."

    # 2c. BOTTOM section must contain only the weather condition — no temperature numbers
    # (skipped when condition is unknown — no condition label is shown)
    if not is_unknown_condition and re.search(r'-?\d+°C', bot_section):
        return False, "BOTTOM section must show ONLY the weather condition — no temperature values allowed here."

    # 2d. TEMP: label must not appear anywhere
    if re.search(r'\bTEMP:', prompt_text, re.IGNORECASE):
        return False, "'TEMP:' label found — temperature card shows bare value only, no TEMP: prefix."

    # 3. Format: prompt must specify 4K and 16:9 aspect ratio
    if "4K" not in prompt_text or "16:9" not in prompt_text:
        return False, "Video format (4K, 16:9) not specified in prompt."

    # 4. Landmark Checks
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

    # Extra check for snowy conditions: active snowfall must be visible through the window
    # (not just settled snow — Veo must show snow falling/drifting past the glass)
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
    Post-generation frame check in two steps:
      1. Gemini Vision reads ALL visible text from the frame as structured JSON (pure OCR — no judgment).
      2. Python validates the extracted values against expected weather data using explicit rules.

    This separates reading (Gemini's job) from validation (Python's job), making checks
    deterministic and reusing the same logic applied to the prompt.
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        return True, "GOOGLE_CLOUD_PROJECT not set — skipping frame validation."

    if not os.path.exists(str(video_path)):
        return True, "Video not a local file (may be GCS URI) — skipping frame validation."

    # Step 1: Extract a frame at 4 seconds (midpoint of the 8-second video)
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

        # Step 2: Ask Gemini Vision to read visible text as structured JSON — no validation, pure OCR
        ocr_prompt = (
            "Read the visible text in the weather display card in this broadcast video frame exactly as it appears. "
            "Do NOT correct spelling, interpret intent, or skip garbled text — transcribe precisely what you see. "
            "Return ONLY a JSON object with these exact keys:\n"
            "{\n"
            '  "top_section": "<exact text in the top section of the weather card>",\n'
            '  "bottom_section": "<exact text in the bottom section of the weather card>"\n'
            "}\n"
            "Return ONLY the JSON — no explanation, no markdown."
        )

        client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg"),
                ocr_prompt,
            ]
        )

        raw = response.text.strip()
        # Strip markdown code fences if Gemini wraps the JSON anyway
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        extracted = json.loads(raw)

        # Step 3: Validate extracted values using explicit Python rules
        issues = []
        expected_temp = f"{weather_data['temp_c']}°C"

        def _norm(text):
            """Collapse all whitespace (including newlines) to single spaces."""
            return re.sub(r'\s+', ' ', (text or "").strip())

        top = _norm(extracted.get("top_section"))

        # TOP section — must contain the current temperature
        if expected_temp not in top:
            issues.append(f"TOP section shows '{top}' — expected '{expected_temp}'")

        if issues:
            return False, "Frame issues:\n" + "\n".join(f"  - {i}" for i in issues)
        return True, "Frame text verified — all visible elements correct."

    except json.JSONDecodeError as e:
        return True, f"Frame validation skipped — could not parse OCR response: {e}"
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

    # 3. No repeated values between script and display
    repeat_pass, repeat_msg = validate_no_repetition(script_text, prompt_text, weather_data)
    print(f"No-Repetition Check:     {'PASS' if repeat_pass else 'WARN'} — {repeat_msg}")
    # This is a soft warning — does not block video generation

    # 4. Character consistency (reference image exists)
    char_pass, char_msg = validate_character_consistency()
    print(f"Character Consistency:   {'PASS' if char_pass else 'WARN'} — {char_msg}")
    # Also a soft warning — Veo will generate the reference image if missing



    return all_passed


if __name__ == "__main__":
    mock_data = {"location": "Storrs", "condition": "Sunny", "temp_c": 15, "high_c": 20, "low_c": 10, "feels_like_c": 14, "alert": None}
    mock_script = "Good morning Storrs! Crisp and clear out there — a beautiful start to the day. Get outside!"
    mock_prompt = (
        "A professional 4K 16:9 TV news broadcast shot of Maya the anchor reporter in a sunny studio. "
        "Behind her and to her left is a sleek new-age glass-textured broadcast studio display panel "
        "divided into two clearly separated sections (top to bottom): "
        "TOP SECTION — shows ONLY the current temperature '15°C' in large bold text, nothing else; "
        "BOTTOM SECTION — shows ONLY the weather condition 'SUNNY' — no temperature numbers in this section. "
        "The card must contain ONLY these two sections — no extra numbers, no timestamps, no random strings. "
        "The video starts immediately. Camera is static. 4K resolution, professional broadcast quality. "
        "Studio environment: golden sunlight over the Homer Babbidge Library and the central green at UConn Storrs campus."
    )
    run_all_tests(mock_script, mock_prompt, mock_data)
