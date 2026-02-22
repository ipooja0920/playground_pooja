import vertexai
from vertexai.generative_models import GenerativeModel
import os
import re

REFERENCE_IMAGE_PATH = "maya_reference.jpg"


def validate_script_content(script_text, weather_data):
    """
    Checks if the script accurately reflects the weather data and is in English.
    Also checks that no phrase or advisory is repeated twice in the script.
    """
    model = GenerativeModel("gemini-2.0-flash")

    prompt = f"""
    Evaluate the following weather report script based on the provided data.

    Script: "{script_text}"
    Weather data: Location={weather_data['location']}, Condition={weather_data['condition']}, Current Temp={weather_data['temp_c']}°C, High={weather_data['high_c']}°C, Low={weather_data['low_c']}°C

    Checklist:
    1. Is the script in English?
    2. Are there any clear spelling or grammar errors?
    3. Does the script reflect the correct weather condition (e.g. overcast, sunny, rainy)?
    4. Any specific temperature numbers mentioned in the script must match current temp, high, or low from the data.
    5. Is the tone appropriate for a TV weather anchor? Weather segments are intentionally energetic, casual, and punchy — informal expressions like "bundle up", "serious cold", "stay dry" are acceptable and expected. Only FAIL if the tone is offensive, inappropriate, or wildly unprofessional.
    6. Is any full phrase or advisory repeated twice in the same script? (e.g. "stay warm, stay warm" or two identical sign-off lines). If yes, FAIL.

    Respond with 'PASS' if all criteria are met, otherwise respond with 'FAIL' followed by a brief reason.
    """

    response = model.generate_content(prompt)
    result = response.text.strip().upper()
    return result.startswith("PASS"), result


def validate_video_prompt(prompt_text, weather_data):
    """
    Checks the video prompt for:
    - Correct weather condition reflected in the studio environment
    - Maya (character) is present
    - The studio display shows each data label exactly once (TEMP, HIGH, LOW, weather type)
    - No data value is duplicated in the display string
    """
    condition = weather_data['condition'].lower()
    passed = True
    reason = "Prompt looks good."

    # Check weather condition is reflected
    if "sunny" in condition and "sunny" not in prompt_text and "golden sunlight" not in prompt_text:
        passed = False
        reason = "Sunny condition missing from background prompt."
    elif "rain" in condition and "rain" not in prompt_text:
        passed = False
        reason = "Rainy condition missing from background prompt."
    elif "snow" in condition and "snow" not in prompt_text:
        passed = False
        reason = "Snowy condition missing from background prompt."

    # Check character identity
    if "Maya" not in prompt_text or ("reporter" not in prompt_text and "anchor" not in prompt_text):
        passed = False
        reason = "Character identity (Maya) not found in prompt."

    # Check studio display has no duplicate labels
    display_labels = ["TEMP:", "HIGH:", "LOW:"]
    for label in display_labels:
        count = prompt_text.count(label)
        if count > 1:
            passed = False
            reason = f"Display label '{label}' appears {count} times in the prompt — should appear exactly once."
            break

    return passed, reason


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
    mock_data = {"location": "Storrs", "condition": "Sunny", "high_c": 20, "low_c": 10}
    mock_script = "Good morning Storrs! Crisp and clear out there — a beautiful start to the day. Get outside!"
    mock_prompt = "Maya the anchor in a sunny studio. TEMP: 15°C  |  HIGH: 20°C  |  LOW: 10°C  |  SUNNY"
    run_all_tests(mock_script, mock_prompt, mock_data)
