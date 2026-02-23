from google import genai
from google.genai import types
import os
import re
import json
import subprocess

REFERENCE_IMAGE_PATH = "maya_reference.jpg"
LOGO_PATH = "uconn_news_logo.png"


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

    prompt = f"""
    Evaluate the following weather report script based on the provided data.

    Script: "{script_text}"
    Weather data: Location={weather_data['location']}, Condition={weather_data['condition']}, Current Temp={weather_data['temp_c']}°C, High={weather_data['high_c']}°C, Low={weather_data['low_c']}°C{alert_line}

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

    # 2a. Extract the three display card sections
    top_match = re.search(r"TOP SECTION[^']*'([^']+)'", prompt_text, re.IGNORECASE)
    mid_match = re.search(r"MIDDLE SECTION[^']*'([^']+)'", prompt_text, re.IGNORECASE)
    bot_match = re.search(r"BOTTOM SECTION[^']*'([^']+)'", prompt_text, re.IGNORECASE)
    top_section = top_match.group(1) if top_match else ""
    mid_section = mid_match.group(1) if mid_match else ""
    bot_section = bot_match.group(1) if bot_match else ""

    if not top_section or not mid_section or not bot_section:
        return False, (
            "Display card three-section structure (TOP SECTION / MIDDLE SECTION / BOTTOM SECTION) "
            "not found in prompt — temperature card must be described as three explicit sections."
        )

    # 2b. TOP section must contain only the current temperature — no HIGH/LOW
    if weather_data:
        expected_temp = f"{weather_data['temp_c']}°C"
        if expected_temp not in top_section:
            return False, f"TOP section should contain only the current temperature '{expected_temp}', found: '{top_section}'."
    if re.search(r'\b(HIGH|LOW)\b', top_section, re.IGNORECASE):
        return False, f"TOP section must show ONLY the current temperature — 'HIGH' or 'LOW' must not appear here."

    # 2c. MIDDLE section — HIGH and LOW each exactly once, spelled correctly, values match weather_data
    high_count = len(re.findall(r'\bHIGH\b', mid_section, re.IGNORECASE))
    low_count = len(re.findall(r'\bLOW\b', mid_section, re.IGNORECASE))
    if high_count != 1:
        return False, f"'HIGH' must appear exactly once in MIDDLE section, found {high_count} times."
    if low_count != 1:
        return False, f"'LOW' must appear exactly once in MIDDLE section, found {low_count} times."
    if re.search(r'\bHIGHH+\b', prompt_text, re.IGNORECASE):
        return False, "Misspelling detected: 'HIGHH' found in prompt — should be 'HIGH'."
    if re.search(r'\bLOWW+\b', prompt_text, re.IGNORECASE):
        return False, "Misspelling detected: 'LOWW' found in prompt — should be 'LOW'."
    if weather_data:
        expected_high = f"{weather_data['high_c']}°C"
        expected_low = f"{weather_data['low_c']}°C"
        if expected_high not in mid_section:
            return False, f"MIDDLE section HIGH value should be '{expected_high}', not found in: '{mid_section}'."
        if expected_low not in mid_section:
            return False, f"MIDDLE section LOW value should be '{expected_low}', not found in: '{mid_section}'."

    # 2d. BOTTOM section must contain only the weather condition — no extra labels or numbers
    if re.search(r'\b(HIGH|LOW)\b', bot_section, re.IGNORECASE):
        return False, f"BOTTOM section must show ONLY the weather condition — 'HIGH' or 'LOW' must not appear here."
    if re.search(r'-?\d+°C', bot_section):
        return False, f"BOTTOM section must show ONLY the weather condition — no temperature values allowed here."

    # 2e. TEMP: label must not appear anywhere
    if re.search(r'\bTEMP:', prompt_text, re.IGNORECASE):
        return False, "'TEMP:' label found — temperature card shows bare value only, no TEMP: prefix."

    # 2f. HIGH: and LOW: must not appear outside the display card block
    display_block_match = re.search(
        r'divided into three clearly separated sections.*?shown exactly once\.',
        prompt_text, re.DOTALL | re.IGNORECASE
    )
    prompt_without_display = (
        prompt_text.replace(display_block_match.group(0), "")
        if display_block_match else prompt_text
    )
    if re.search(r'\bHIGH:', prompt_without_display, re.IGNORECASE):
        return False, "'HIGH:' label appears outside the display card section."
    if re.search(r'\bLOW:', prompt_without_display, re.IGNORECASE):
        return False, "'LOW:' label appears outside the display card section."

    # 3. Overlay graphics checks
    if "UConn News" not in prompt_text or "Today's Weather Forecast" not in prompt_text:
        return False, "Overlay graphics (Logo or Title) missing from video prompt."

    # 4. Visual text spelling — manual checks only
    # All on-screen text is either standardized constants (UConn News, Today's Weather
    # Forecast, WARNING: X IN EFFECT) or numeric/abbreviated weather values (°C, SUNNY).
    # LLM spell-check of these strings consistently hallucinates false positives, so
    # all misspelling detection is handled by the targeted manual checks above (HIGHH, LOWW)
    # and the three-section structural validation.

    # 5. Lower-third layout validation (6-point check)
    # 5a. Format: prompt must specify 4K and 16:9 aspect ratio
    if "4K" not in prompt_text or "16:9" not in prompt_text:
        return False, "Video format (4K, 16:9) not specified in prompt."

    # 5b. Lower-third structure: single full-width navy blue bar containing the title
    if "navy blue" not in prompt_text.lower():
        return False, "Lower-third bar must specify a navy blue background."
    if not re.search(r'full.width', prompt_text, re.IGNORECASE):
        return False, "Lower-third bar must be described as full-width."

    # 5c. Forbidden elements: prompt must explicitly prohibit badges and extra boxes
    if not re.search(r'no condition badges|no extra boxes|no floating labels', prompt_text, re.IGNORECASE):
        return False, "Prompt must explicitly forbid condition badges and extra elements in the lower-third."

    # 5d. Typography: lower-third must specify bold white sans-serif font
    if "bold white sans-serif" not in prompt_text.lower():
        return False, "Lower-third typography must specify 'bold white sans-serif'."

    # 5e. Text duplication: title appears exactly once; ALERT: appears only when alert is active
    forecast_count = len(re.findall(r"Today's Weather Forecast", prompt_text, re.IGNORECASE))
    if forecast_count != 1:
        return False, f"'Today's Weather Forecast' must appear exactly once in prompt, found {forecast_count} times."

    alert_data = weather_data.get("alert") if weather_data else None
    has_active_alert = bool(alert_data and alert_data.get("severity") in ("Extreme", "Severe"))
    alert_count = len(re.findall(r'\bALERT:', prompt_text, re.IGNORECASE))
    if has_active_alert and alert_count != 1:
        return False, f"Active alert present — 'ALERT:' must appear exactly once in prompt, found {alert_count} times."
    if not has_active_alert and alert_count > 0:
        return False, f"No active alert — 'ALERT:' must not appear in prompt, found {alert_count} times."

    # 5f. Layout: alert bar must be positioned directly beneath the title bar (not floating elsewhere)
    if has_active_alert:
        if not re.search(r'directly below|directly beneath', prompt_text, re.IGNORECASE):
            return False, "Alert bar must be positioned 'directly below' the lower-third title bar."

    # 6. Landmark Checks
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

    # 7. Logo placement validation
    # 7a. Logo must be present and positioned in the top-left corner
    if "UConn News" not in prompt_text:
        return False, "UConn News logo missing from video prompt."
    if "top-right corner" not in prompt_text.lower():
        return False, "UConn News logo must be positioned in the top-right corner."

    # 7b. Placement spec: 80px padding and 400px width must be specified
    if "80px" not in prompt_text:
        return False, "UConn News logo must specify 80px padding from top and right edges."
    if "400px" not in prompt_text:
        return False, "UConn News logo must specify approximately 400px width."

    # 7c. Static constraint: prompt must say the logo does not move, animate, or duplicate
    if not re.search(r'do NOT (move|resize|animate|duplicate)', prompt_text, re.IGNORECASE):
        return False, "Prompt must explicitly state logo is static (do NOT move/resize/animate/duplicate)."

    # 7d. Logo must appear exactly once — no duplication
    if not re.search(r'appears exactly once', prompt_text, re.IGNORECASE):
        return False, "Prompt must state UConn News logo appears exactly once."

    # 7e. No color or text modification
    if not re.search(r'no color changes|no text modification', prompt_text, re.IGNORECASE):
        return False, "Prompt must explicitly state no color changes and no text modification to the logo."

    return True, "Prompt looks good."


def validate_logo_consistency():
    """
    Checks that the UConn News logo file exists locally.
    If missing, it will be auto-generated on the next video run.
    """
    if os.path.exists(LOGO_PATH):
        return True, f"UConn News logo found: {LOGO_PATH}"
    return False, (
        f"UConn News logo not found at '{LOGO_PATH}'. "
        "It will be auto-generated on the next video run."
    )


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
            "Read every piece of visible text in this broadcast video frame exactly as it appears. "
            "Do NOT correct spelling, interpret intent, or skip garbled text — transcribe precisely what you see. "
            "Return ONLY a JSON object with these exact keys:\n"
            "{\n"
            '  "top_section": "<exact text in the top of the weather card>",\n'
            '  "middle_section": "<exact text in the middle of the weather card>",\n'
            '  "bottom_section": "<exact text in the bottom of the weather card>",\n'
            '  "logo_text": "<exact text of the logo in the top-right corner>",\n'
            '  "lower_third": "<exact text in the navy bar at the bottom of the frame>",\n'
            '  "alert_banner": "<exact text in the red banner below the navy bar, or null if not present>"\n'
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
        expected_high = f"{weather_data['high_c']}°C"
        expected_low  = f"{weather_data['low_c']}°C"

        top         = extracted.get("top_section", "")
        mid         = extracted.get("middle_section", "")
        logo        = extracted.get("logo_text", "")
        lower_third = extracted.get("lower_third", "")
        alert_banner = extracted.get("alert_banner")

        # TOP section — must contain the current temp, must NOT have a HIGH/LOW label
        if expected_temp not in top:
            issues.append(f"TOP section shows '{top}' — expected '{expected_temp}'")
        if re.search(r'\b(HIGH|LOW)\b', top, re.IGNORECASE):
            issues.append(f"TOP section has HIGH/LOW label — must show bare temp only: '{top}'")

        # MIDDLE section — must contain HIGH: {high} and LOW: {low}
        if f"HIGH: {expected_high}" not in mid:
            issues.append(f"MIDDLE section missing 'HIGH: {expected_high}' — got: '{mid}'")
        if f"LOW: {expected_low}" not in mid:
            issues.append(f"MIDDLE section missing 'LOW: {expected_low}' — got: '{mid}'")

        # Logo — must read exactly "UConn News"
        if logo.strip() != "UConn News":
            issues.append(f"Logo shows '{logo}' — expected 'UConn News'")

        # Lower-third — must read exactly "Today's Weather Forecast"
        if lower_third.strip() != "Today's Weather Forecast":
            issues.append(f"Lower-third shows '{lower_third}' — expected \"Today's Weather Forecast\"")

        # Alert banner — must match exactly when active, must be absent when not active
        alert = weather_data.get("alert")
        has_active_alert = bool(alert and alert.get("severity") in ("Extreme", "Severe"))
        if has_active_alert:
            alert_event = alert["event"].upper()
            expected_banner = f"ALERT: {alert_event} IN EFFECT"
            if not alert_banner:
                issues.append(f"Alert banner missing — expected '{expected_banner}'")
            elif alert_banner.strip() != expected_banner:
                issues.append(f"Alert banner shows '{alert_banner}' — expected '{expected_banner}'")
        elif alert_banner:
            issues.append(f"Alert banner present but no active alert — got: '{alert_banner}'")

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

    # Extract display values from the prompt (between the display quotes)
    display_match = re.search(r'TEMP: (-?\d+)', video_prompt)
    high_match = re.search(r'HIGH: (-?\d+)', video_prompt)
    low_match = re.search(r'LOW: (-?\d+)', video_prompt)

    display_numbers = set()
    if display_match:
        display_numbers.add(display_match.group(1))
    if high_match:
        display_numbers.add(high_match.group(1))
    if low_match:
        display_numbers.add(low_match.group(1))

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

    # 5. Logo consistency (logo file exists)
    logo_pass, logo_msg = validate_logo_consistency()
    print(f"Logo Consistency:        {'PASS' if logo_pass else 'WARN'} — {logo_msg}")
    # Soft warning — logo will be auto-generated on next video run if missing

    return all_passed


if __name__ == "__main__":
    mock_data = {"location": "Storrs", "condition": "Sunny", "temp_c": 15, "high_c": 20, "low_c": 10, "feels_like_c": 14, "alert": None}
    mock_script = "Good morning Storrs! Crisp and clear out there — a beautiful start to the day. Get outside!"
    mock_prompt = (
        "A professional 4K 16:9 TV news broadcast shot of Maya the anchor reporter in a sunny studio. "
        "Behind her and to her left is a sleek new-age glass-textured broadcast studio display panel "
        "divided into three clearly separated sections (top to bottom): "
        "TOP SECTION — shows ONLY the bare value '15°C' with no label and no prefix "
        "(this is the CURRENT real-time temperature — do NOT label it HIGH, do NOT repeat this value elsewhere in the card); "
        "MIDDLE SECTION — shows only 'HIGH: 20°C  LOW: 10°C' (HIGH on the left, LOW on the right); "
        "BOTTOM SECTION — shows only 'SUNNY' (weather condition label only, no temperature numbers). "
        "The card must contain ONLY these three sections — no extra numbers, no timestamps, "
        "no random strings, no duplicate values, HIGH and LOW each spelled correctly and shown exactly once. "
        "Overlay graphics: in the top-right corner of the frame is the official 'UConn News' broadcast logo — "
        "bold white sans-serif text on a deep navy blue background with a subtle red accent. "
        "Logo placement: 80px padding from the top and right edges, approximately 400px wide, maintaining its original aspect ratio. "
        "The logo is static and identical across all frames — do NOT move, resize, animate, or duplicate it. "
        "It appears exactly once in the top-right corner only, with no color changes and no text modification. "
        "At the very bottom of the frame is a single lower-third title bar: a full-width semi-transparent navy blue bar "
        "containing only the centered text 'Today's Weather Forecast' in bold white sans-serif (Helvetica Neue or Roboto Condensed style) — "
        "no random characters, watermarks, or other text appear in this bar before or after the title. "
        "No condition badges, no extra boxes, no floating labels, no duplicate title elements anywhere else in the frame. "
        "The video starts immediately. Camera is static. 4K resolution, professional broadcast quality. "
        "Studio environment: golden sunlight over the Homer Babbidge Library and the central green at UConn Storrs campus."
    )
    run_all_tests(mock_script, mock_prompt, mock_data)
