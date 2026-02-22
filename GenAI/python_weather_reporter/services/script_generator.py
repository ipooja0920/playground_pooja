"""
AI Script Generator using Google Gemini.
Includes anti-hallucination validation and template fallback.
"""

import logging
import re
from datetime import datetime

import google.generativeai as genai

from config.settings import Settings
from models.schemas import NormalizedWeather

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Broadcast prompt template
# ---------------------------------------------------------------------------
BROADCAST_SYSTEM_PROMPT = """You are a charismatic and professional radio/TV weather anchor for a station serving Storrs, Connecticut and the surrounding UConn area.

Create a detailed, engaging broadcast-style weather script that would take 5-10 minutes to read aloud (approximately 800-1500 words).

Structure your broadcast with these segments:
1. **TEASER**: A punchy 2-sentence hook that grabs attention immediately.
2. **CURRENT CONDITIONS**: Detailed sensory description of right now — what it feels like stepping outside. Reference EXACT numbers from the data.
3. **THE SCIENCE**: Brief meteorological context — why the weather is the way it is. Reference pressure systems, fronts, or seasonal patterns.
4. **COMMUTER FORECAST**: How weather impacts the morning and evening commute. Road conditions, visibility, etc.
5. **CAMPUS & LIFESTYLE**: Advice for UConn students and Storrs residents — what to wear, outdoor activities, health tips (UV, pollen, etc.).
6. **LOOKING AHEAD**: Project the next 2-3 days based on the trend you see in the data.
7. **SIGN-OFF**: A warm, memorable closing line.

CRITICAL RULES:
- Use ONLY the exact numerical values provided in the weather data. Do NOT invent temperatures, wind speeds, or percentages.
- Write in a spoken, conversational tone — no bullet points, no markdown formatting, no headers.
- Use natural transitions between segments.
- Reference the location as "Storrs, Connecticut" or "the Storrs area" or "here in Storrs".
- Spell out numbers and units naturally (e.g., "twenty-eight degrees", "twelve miles per hour").
- Include the day of the week and date naturally in the intro.
"""


TEMPLATE_REPORT = """Good morning, {location}! This is your weather update for {date}.

Right now, we're looking at {condition} conditions outside with a temperature of {temp}°F, though it feels more like {feels_like}°F when you factor in the wind. Speaking of wind, we've got {wind_direction} winds blowing at about {wind_speed} miles per hour today.

Humidity is sitting at {humidity} percent, so {humidity_comment}.

{forecast_section}

That's your weather update for today. Stay safe out there, {location}!
"""


class ScriptGenerator:
    """Generates weather broadcast scripts using Gemini with validation."""

    def __init__(self, settings: Settings):
        self.settings = settings
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

    def generate(self, weather: NormalizedWeather) -> str:
        """Generate a broadcast script with validation and retry logic."""
        weather_json = self._format_weather_prompt(weather)

        for attempt in range(self.settings.gemini_max_retries + 1):
            try:
                logger.info(f"Gemini script generation attempt {attempt + 1}...")
                script = self._call_gemini(weather_json, attempt)

                if script and len(script.split()) >= 100:
                    # Validate against hallucination
                    flags = self._validate_script(script, weather)
                    if not flags:
                        logger.info("Script validation PASSED")
                        return script
                    else:
                        logger.warning(
                            f"Hallucination detected (attempt {attempt + 1}): {flags}"
                        )
                else:
                    logger.warning(f"Script too short (attempt {attempt + 1})")

            except Exception as e:
                logger.error(f"Gemini error (attempt {attempt + 1}): {e}")

        # All retries exhausted — use template fallback
        logger.warning("All Gemini attempts failed. Using template fallback.")
        return self._template_fallback(weather)

    def _format_weather_prompt(self, weather: NormalizedWeather) -> str:
        """Format weather data into a clear prompt section."""
        lines = [
            f"Location: {weather.location_name}",
            f"Date: {weather.report_date.strftime('%A, %B %d, %Y')}",
            f"Current Temperature: {weather.temperature_f}°F",
            f"Feels Like: {weather.feels_like_f}°F",
            f"Condition: {weather.condition_text}",
            f"Humidity: {weather.humidity_pct}%",
            f"Wind: {weather.wind_direction} at {weather.wind_speed_mph} mph",
        ]

        if weather.wind_chill_f is not None:
            lines.append(f"Wind Chill: {round(weather.wind_chill_f, 1)}°F")
        if weather.heat_index_f is not None:
            lines.append(f"Heat Index: {round(weather.heat_index_f, 1)}°F")
        if weather.pressure_inhg:
            lines.append(f"Barometric Pressure: {weather.pressure_inhg} inHg")
        if weather.visibility_miles:
            lines.append(f"Visibility: {weather.visibility_miles} miles")
        if weather.uv_index is not None:
            lines.append(f"UV Index: {weather.uv_index} ({weather.uv_category})")
        if weather.high_f is not None:
            lines.append(f"Today's High: {weather.high_f}°F")
        if weather.low_f is not None:
            lines.append(f"Today's Low: {weather.low_f}°F")
        if weather.rain_chance_pct is not None:
            lines.append(f"Rain Chance: {weather.rain_chance_pct}%")
        if weather.snow_chance_pct is not None:
            lines.append(f"Snow Chance: {weather.snow_chance_pct}%")
        if weather.forecast_condition:
            lines.append(f"Forecast Condition: {weather.forecast_condition}")

        return "\n".join(lines)

    def _call_gemini(self, weather_data: str, attempt: int) -> str | None:
        """Call Gemini model to generate the script."""
        strictness = ""
        if attempt > 0:
            strictness = (
                "\n\nIMPORTANT: A previous attempt was rejected for inaccuracy. "
                "Use ONLY the EXACT numerical values from the weather data provided. "
                "Do NOT round, estimate, or invent ANY numbers."
            )

        prompt = (
            f"{BROADCAST_SYSTEM_PROMPT}\n\n"
            f"--- WEATHER DATA ---\n{weather_data}\n--- END DATA ---\n"
            f"{strictness}\n\n"
            f"Generate the broadcast script now."
        )

        response = self.model.generate_content(prompt)
        return response.text if response and response.text else None

    def _validate_script(self, script: str, weather: NormalizedWeather) -> list[str]:
        """Validate script against source data to catch hallucinations."""
        flags = []

        # Check temperature (±1°F tolerance)
        temp_numbers = re.findall(r'(\d+\.?\d*)\s*(?:degrees?|°)', script.lower())
        if temp_numbers:
            # Check if any extracted temp is wildly different from our data
            source_temp = round(weather.temperature_f)
            found_close = False
            for num_str in temp_numbers:
                num = float(num_str)
                if abs(num - source_temp) <= 2:
                    found_close = True
                    break
            if not found_close:
                # Also check written-out numbers
                written_temp = self._number_to_words(source_temp)
                if written_temp.lower() not in script.lower() and str(source_temp) not in script:
                    flags.append(
                        f"Temperature {source_temp}°F not found in script "
                        f"(found: {temp_numbers})"
                    )

        # Check location mention
        loc_lower = script.lower()
        if "storrs" not in loc_lower and "connecticut" not in loc_lower:
            flags.append("Location 'Storrs, Connecticut' not mentioned in script")

        return flags

    def _template_fallback(self, weather: NormalizedWeather) -> str:
        """Generate a basic report using string template when LLM is unavailable."""
        humidity_comment = (
            "it might feel a bit damp"
            if weather.humidity_pct > 70
            else "the air should feel comfortable"
        )

        forecast_parts = []
        if weather.high_f is not None and weather.low_f is not None:
            forecast_parts.append(
                f"We're expecting a high of {weather.high_f}°F "
                f"and a low of {weather.low_f}°F today."
            )
        if weather.rain_chance_pct is not None and weather.rain_chance_pct > 10:
            forecast_parts.append(
                f"There's a {weather.rain_chance_pct} percent chance of rain, "
                f"so you might want to grab an umbrella."
            )
        if weather.snow_chance_pct is not None and weather.snow_chance_pct > 10:
            forecast_parts.append(
                f"There's a {weather.snow_chance_pct} percent chance of snow today. "
                f"Drive carefully!"
            )

        forecast_section = " ".join(forecast_parts) if forecast_parts else ""

        return TEMPLATE_REPORT.format(
            location=weather.location_name,
            date=weather.report_date.strftime("%A, %B %d, %Y"),
            condition=weather.condition_text.lower(),
            temp=weather.temperature_f,
            feels_like=weather.feels_like_f,
            wind_direction=weather.wind_direction,
            wind_speed=weather.wind_speed_mph,
            humidity=weather.humidity_pct,
            humidity_comment=humidity_comment,
            forecast_section=forecast_section,
        )

    @staticmethod
    def _number_to_words(n: int) -> str:
        """Basic integer-to-words for validation matching."""
        ones = [
            "", "one", "two", "three", "four", "five", "six", "seven",
            "eight", "nine", "ten", "eleven", "twelve", "thirteen",
            "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
        ]
        tens = [
            "", "", "twenty", "thirty", "forty", "fifty",
            "sixty", "seventy", "eighty", "ninety",
        ]
        if n < 0:
            return "negative " + ScriptGenerator._number_to_words(abs(n))
        if n < 20:
            return ones[n]
        if n < 100:
            return tens[n // 10] + ("-" + ones[n % 10] if n % 10 else "")
        return str(n)
