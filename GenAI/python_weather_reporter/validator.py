from google import genai
from google.genai import types
import os
import re

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

    # 2a. Case-insensitive duplicate check for label words with colon across the FULL prompt
    # Catches if "HIGH:", "TEMP:", "LOW:" (formatted labels) appear more than once
    for label in ["TEMP", "HIGH", "LOW"]:
        count = len(re.findall(rf"\b{label}:", prompt_text, re.IGNORECASE))
        if count > 1:
            return False, (
                f"'{label}:' appears {count} times in the full prompt (case-insensitive). "
                f"Each data label must appear exactly once — check for duplicate visual descriptions."
            )

    # 2b. Anti-pattern check: detect explanation sentences that list labels bare (e.g.
    # "Each data label (TEMP, HIGH, LOW, weather type)...") — these caused Veo to render
    # duplicate label text in the video even though the colon-form only appeared once.
    if re.search(r'\b(TEMP|HIGH|LOW)\b.*\b(TEMP|HIGH|LOW)\b.*\b(TEMP|HIGH|LOW)\b', prompt_text, re.IGNORECASE):
        # All three bare label words found — check if this is OUTSIDE the display string
        display_section_match = re.search(r'showing bold dynamic data[^"]*"([^"]+)"', prompt_text, re.IGNORECASE)
        prompt_without_display = (
            prompt_text.replace(display_section_match.group(0), "")
            if display_section_match else prompt_text
        )
        if re.search(r'\b(TEMP|HIGH|LOW)\b.*\b(TEMP|HIGH|LOW)\b.*\b(TEMP|HIGH|LOW)\b', prompt_without_display, re.IGNORECASE):
            return False, (
                "Label words TEMP, HIGH, LOW all appear outside the display section. "
                "Remove any explanation sentence that lists these labels — it causes Veo to render them twice."
            )

    # 2c. Display section — no duplicate label words inside the quoted display string
    display_section_match_2 = re.search(r'showing bold dynamic data[^"]*"([^"]+)"', prompt_text, re.IGNORECASE)
    display_section = display_section_match_2.group(1) if display_section_match_2 else ""
    if display_section:
        for label in ["TEMP", "HIGH", "LOW"]:
            count = len(re.findall(rf"\b{label}\b", display_section, re.IGNORECASE))
            if count > 1:
                return False, f"Display label '{label}' appears {count} times in the display string — should appear exactly once."

    # 3. Overlay graphics checks
    if "UConn News" not in prompt_text or "Today's Weather Forecast" not in prompt_text:
        return False, "Overlay graphics (Logo or Title) missing from video prompt."
    if "husky" not in prompt_text.lower():
        return False, "UConn Husky mascot icon missing from logo badge description."

    # 4. Focused LLM spelling + grammar check on the extracted visual text elements only
    # (display text, logo badge text, title text) — not the full narrative prompt
    visual_text_parts: list[str] = []
    display_match = re.search(r'showing bold dynamic data[^"]*"([^"]+)"', prompt_text, re.IGNORECASE)
    if display_match:
        visual_text_parts.append("Studio display: " + display_match.group(1))
    overlay_match = re.search(r'Overlay graphics:(.*?)(?:The video starts|Camera is)', prompt_text, re.DOTALL | re.IGNORECASE)
    if overlay_match:
        visual_text_parts.append("Overlay/logo text: " + overlay_match.group(1).strip())
    visual_text: str = "\n".join(visual_text_parts)

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        print("Warning: GOOGLE_CLOUD_PROJECT not set. Skipping LLM prompt validation.")
    elif not visual_text:
        print("Warning: Could not extract visual text sections — skipping spelling check.")
    else:
        client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        llm_prompt = f"""
        You are a spell-checker and grammar checker for on-screen broadcast graphics.

        Check the following visual text elements (what will be rendered on screen in the video)
        for spelling mistakes and grammar errors.

        Visual text to check:
        {visual_text}

        Rules:
        - Check for misspelled words (e.g. "Foreciast" instead of "Forecast", "Broadcat" instead of "Broadcast").
        - Check for obvious grammar errors in title cards and labels.
        - Ignore temperature values, degree symbols, and weather abbreviations like CLOUDY, SUNNY, RAINY.
        - Ignore narrative/descriptive language — only check text that would be visually displayed on screen.
        - If everything is correct, respond with exactly: PASS
        - If there is an error, respond with: FAIL — [exact problem and correction]
        """
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=llm_prompt
            )
            llm_result = response.text.strip().upper()
            if llm_result.startswith("FAIL"):
                return False, f"Visual Spelling/Grammar Check Failed: {llm_result[4:].strip()}"
        except Exception as e:
            print(f"Warning: LLM prompt validation failed due to error: {e}")

    # 3. Landmark Checks
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

    # 4. Overlay graphics check
    if "UConn News" not in prompt_text or "Today's Weather Forecast" not in prompt_text:
        return False, "Overlay graphics (Logo or Title) missing from video prompt."

    return True, "Prompt looks good."


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

    return all_passed


if __name__ == "__main__":
    mock_data = {"location": "Storrs", "condition": "Sunny", "temp_c": 15, "high_c": 20, "low_c": 10}
    mock_script = "Good morning Storrs! Crisp and clear out there — a beautiful start to the day. Get outside!"
    mock_prompt = (
        "Maya the anchor in a sunny studio. "
        "Behind her is a display showing bold dynamic data in large text: \"TEMP: 15°C  |  HIGH: 20°C  |  LOW: 10°C  |  SUNNY\". "
        "Overlay graphics: UConn Husky mascot icon beside 'UConn News' in bold white text on navy blue. "
        "At the bottom of the frame is a lower-third title card reading 'Today's Weather Forecast'. "
        "The video starts immediately. Camera is static. "
        "Studio environment: golden sunlight over the Homer Babbidge Library and the central green at UConn Storrs campus."
    )
    run_all_tests(mock_script, mock_prompt, mock_data)
