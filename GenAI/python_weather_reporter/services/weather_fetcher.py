"""
Weather data fetcher with fallback support.
Primary: Google Weather API | Fallback: OpenWeatherMap
"""

import logging
import time
from datetime import date, datetime

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.settings import Settings
from models.schemas import NormalizedWeather

logger = logging.getLogger(__name__)


class WeatherFetchError(Exception):
    """Raised when all weather sources fail."""
    pass


class WeatherFetcher:
    """Fetches and normalizes weather data from external APIs."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch(self) -> NormalizedWeather:
        """Fetch weather data with automatic fallback."""
        # Try Google Weather API first
        try:
            logger.info("Fetching from Google Weather API...")
            data = self._fetch_google_weather()
            logger.info("Google Weather API: OK")
            return data
        except Exception as e:
            logger.warning(f"Google Weather API failed: {e}")

        # Fallback to OpenWeatherMap
        if self.settings.openweathermap_api_key:
            try:
                logger.info("Falling back to OpenWeatherMap...")
                data = self._fetch_openweathermap()
                logger.info("OpenWeatherMap: OK")
                return data
            except Exception as e:
                logger.warning(f"OpenWeatherMap fallback failed: {e}")

        raise WeatherFetchError("All weather data sources failed.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((requests.RequestException, KeyError)),
        before_sleep=lambda retry_state: logger.info(
            f"Retrying Google Weather API (attempt {retry_state.attempt_number})..."
        ),
    )
    def _fetch_google_weather(self) -> NormalizedWeather:
        """Fetch from Google Weather API (via Gemini grounding or direct endpoint)."""
        # Google Weather API endpoint
        # Using the publicly available endpoint format
        url = "https://weather.googleapis.com/v1/currentConditions:lookup"
        params = {
            "key": self.settings.google_api_key,
            "location.latitude": self.settings.latitude,
            "location.longitude": self.settings.longitude,
        }

        fetch_time = datetime.now()
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        raw = response.json()

        # Also fetch forecast
        forecast_url = "https://weather.googleapis.com/v1/forecast/days:lookup"
        forecast_params = {
            "key": self.settings.google_api_key,
            "location.latitude": self.settings.latitude,
            "location.longitude": self.settings.longitude,
            "days": 1,
        }
        forecast_resp = requests.get(forecast_url, params=forecast_params, timeout=10)
        forecast_data = {}
        if forecast_resp.status_code == 200:
            forecast_data = forecast_resp.json()

        return self._normalize_google(raw, forecast_data, fetch_time)

    def _normalize_google(
        self, raw: dict, forecast: dict, fetch_time: datetime
    ) -> NormalizedWeather:
        """Normalize Google Weather API response."""
        current = raw.get("currentConditions", raw)

        # Extract temperature (Google returns Celsius, convert to F)
        temp_c = current.get("temperature", {}).get("degrees", 0)
        feels_c = current.get("feelsLikeTemperature", {}).get("degrees", temp_c)
        temp_f = temp_c * 9 / 5 + 32
        feels_f = feels_c * 9 / 5 + 32

        # Wind
        wind = current.get("wind", {})
        wind_speed_kph = wind.get("speed", {}).get("value", 0)
        wind_speed_mph = wind_speed_kph * 0.621371
        wind_dir_deg = wind.get("direction", {}).get("degrees", 0)
        wind_direction = self._degrees_to_cardinal(wind_dir_deg)

        # Condition
        condition = current.get("weatherCondition", "Unknown")

        # Humidity
        humidity = current.get("humidity", {}).get("percentage", 50)

        # UV / Pressure / Visibility
        uv = current.get("uvIndex", None)
        pressure_hpa = current.get("pressure", {}).get("value", None)
        pressure_inhg = pressure_hpa * 0.02953 if pressure_hpa else None
        visibility_km = current.get("visibility", {}).get("value", None)
        visibility_mi = visibility_km * 0.621371 if visibility_km else None

        # Forecast
        high_f, low_f, rain_pct, snow_pct, fc_condition = None, None, None, None, None
        if forecast:
            days = forecast.get("forecastDays", [])
            if days:
                day = days[0].get("daytimeForecast", days[0])
                high_c = day.get("temperature", {}).get("degrees", None)
                low_c = days[0].get("overnightForecast", {}).get("temperature", {}).get("degrees", None)
                high_f = high_c * 9 / 5 + 32 if high_c is not None else None
                low_f = low_c * 9 / 5 + 32 if low_c is not None else None
                precip = day.get("precipitation", {})
                rain_pct = precip.get("probability", {}).get("percentage", None)
                fc_condition = day.get("weatherCondition", None)

        weather = NormalizedWeather(
            location_name=self.settings.location_display,
            latitude=self.settings.latitude,
            longitude=self.settings.longitude,
            report_date=date.today(),
            report_time=fetch_time.time(),
            temperature_f=round(temp_f, 1),
            feels_like_f=round(feels_f, 1),
            humidity_pct=int(humidity),
            wind_speed_mph=round(wind_speed_mph, 1),
            wind_direction=wind_direction,
            pressure_inhg=round(pressure_inhg, 2) if pressure_inhg else None,
            visibility_miles=round(visibility_mi, 1) if visibility_mi else None,
            uv_index=uv,
            condition_text=condition,
            high_f=round(high_f, 1) if high_f is not None else None,
            low_f=round(low_f, 1) if low_f is not None else None,
            rain_chance_pct=rain_pct,
            snow_chance_pct=snow_pct,
            forecast_condition=fc_condition,
            data_source="google_weather_api",
            fetch_timestamp=fetch_time,
        )
        weather.compute_derived_fields()
        return weather

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type(requests.RequestException),
    )
    def _fetch_openweathermap(self) -> NormalizedWeather:
        """Fallback: fetch from OpenWeatherMap."""
        fetch_time = datetime.now()
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": self.settings.latitude,
            "lon": self.settings.longitude,
            "appid": self.settings.openweathermap_api_key,
            "units": "imperial",
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        raw = response.json()

        # Also get forecast
        forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        forecast_resp = requests.get(
            forecast_url, params=params, timeout=10
        )
        forecast_data = forecast_resp.json() if forecast_resp.status_code == 200 else {}

        return self._normalize_owm(raw, forecast_data, fetch_time)

    def _normalize_owm(
        self, raw: dict, forecast: dict, fetch_time: datetime
    ) -> NormalizedWeather:
        """Normalize OpenWeatherMap response."""
        main = raw.get("main", {})
        wind = raw.get("wind", {})
        weather_list = raw.get("weather", [{}])
        condition = weather_list[0].get("description", "Unknown").title()

        # Forecast high/low from forecast API
        high_f, low_f, rain_pct = None, None, None
        if forecast and "list" in forecast:
            today_temps = [
                entry["main"]["temp"]
                for entry in forecast["list"][:8]  # next 24h
            ]
            if today_temps:
                high_f = max(today_temps)
                low_f = min(today_temps)
            # Rain probability from first forecast entry
            pop = forecast["list"][0].get("pop", 0)
            rain_pct = int(pop * 100)

        weather = NormalizedWeather(
            location_name=self.settings.location_display,
            latitude=self.settings.latitude,
            longitude=self.settings.longitude,
            report_date=date.today(),
            report_time=fetch_time.time(),
            temperature_f=main.get("temp", 0),
            feels_like_f=main.get("feels_like", 0),
            humidity_pct=main.get("humidity", 50),
            wind_speed_mph=wind.get("speed", 0),
            wind_direction=self._degrees_to_cardinal(wind.get("deg", 0)),
            pressure_inhg=round(main.get("pressure", 1013) * 0.02953, 2),
            visibility_miles=round(raw.get("visibility", 10000) / 1609.34, 1),
            condition_text=condition,
            high_f=round(high_f, 1) if high_f else None,
            low_f=round(low_f, 1) if low_f else None,
            rain_chance_pct=rain_pct,
            forecast_condition=condition,
            data_source="openweathermap",
            fetch_timestamp=fetch_time,
        )
        weather.compute_derived_fields()
        return weather

    @staticmethod
    def _degrees_to_cardinal(deg: float) -> str:
        """Convert wind direction degrees to cardinal direction."""
        directions = [
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
        ]
        idx = round(deg / 22.5) % 16
        return directions[idx]
