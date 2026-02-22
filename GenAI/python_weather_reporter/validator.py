import vertexai
from vertexai.generative_models import GenerativeModel
import re

def validate_script_content(script_text, weather_data):
    """
    Checks if the script accurately reflects the weather data and is in English.
    """
    model = GenerativeModel("gemini-2.0-flash")
    
    prompt = f"""
    Evaluate the following weather report script based on the provided data.

    Script: "{script_text}"
    Weather data: Location={weather_data['location']}, Condition={weather_data['condition']}, Current Temp={weather_data['temp_c']}°C, High={weather_data['high_c']}°C, Low={weather_data['low_c']}°C

    Checklist:
    1. Is the script in English?
    2. Are there any clear spelling or grammar errors?
    3. Does the script mention the correct condition (e.g. overcast, sunny, rainy)?
    4. Any temperature values mentioned in the script must match one of: current temp, high, or low from the data. The script does NOT need to mention all temperatures.
    5. Is the tone appropriate for a weather reporter?

    Respond with 'PASS' if all criteria are met, otherwise respond with 'FAIL' followed by a brief reason.
    """
    
    response = model.generate_content(prompt)
    result = response.text.strip().upper()
    return result.startswith("PASS"), result

def validate_video_prompt(prompt_text, weather_data):
    """
    Ensures the video prompt maintains character consistency and background relevance.
    """
    condition = weather_data['condition'].lower()
    
    # Simple keyword checks for background relevance
    passed = True
    reason = "Prompt looks good."
    
    if "sunny" in condition and "sunny" not in prompt_text and "clear blue sky" not in prompt_text:
        passed = False
        reason = "Sunny condition missing from background prompt."
    elif "rain" in condition and "rain" not in prompt_text:
        passed = False
        reason = "Rainy condition missing from background prompt."
    elif "snow" in condition and "snow" not in prompt_text:
        passed = False
        reason = "Snowy condition missing from background prompt."
        
    # Check for character consistency (Maya)
    if "Maya" not in prompt_text or "reporter" not in prompt_text:
        passed = False
        reason = "Character identity (Maya) not found in prompt."
        
    return passed, reason

def run_all_tests(script_text, prompt_text, weather_data):
    """
    Runs all validation tests.
    """
    print("--- Running Validation Tests ---")
    
    # 1. Script Validation
    script_pass, script_msg = validate_script_content(script_text, weather_data)
    print(f"Script Validation: {'PASS' if script_pass else 'FAIL'} ({script_msg})")
    
    # 2. Prompt Validation
    prompt_pass, prompt_msg = validate_video_prompt(prompt_text, weather_data)
    print(f"Prompt Validation: {'PASS' if prompt_pass else 'FAIL'} ({prompt_msg})")
    
    return script_pass and prompt_pass

if __name__ == "__main__":
    # Test validator
    mock_data = {"location": "Storrs", "condition": "Sunny", "high_c": 20, "low_c": 10}
    mock_script = "Hello Storrs! It's a sunny day with a high of 20 and low of 10. Have a great day!"
    mock_prompt = "Maya the reporter in a sunny studio talking about the weather."
    
    # run_all_tests(mock_script, mock_prompt, mock_data)
