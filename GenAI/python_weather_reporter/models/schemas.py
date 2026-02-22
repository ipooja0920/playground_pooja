"""
Pydantic data models for the Daily AI Weather Reporter.
Defines input (raw), internal (normalized), and output (report) schemas.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Normalized Weather (internal)
# ---------------------------------------------------------------------------
class NormalizedWeather(BaseModel):
    """Validated and enriched weather data."""

    # Location
    location_name: str
    latitude: float
    longitude: float

    # Timestamp
    report_date: date
    report_time: time
    timezone: str = "America/New_York"

    # Current conditions
    temperature_f: float
    feels_like_f: float
    humidity_pct: int = Field(ge=0, le=100)
    wind_speed_mph: float = Field(ge=0)
    wind_direction: str
    pressure_inhg: Optional[float] = None
    visibility_miles: Optional[float] = None
    uv_index: Optional[float] = None
    condition_text: str
    condition_code: Optional[int] = None

    # Derived fields
    wind_chill_f: Optional[float] = None
    heat_index_f: Optional[float] = None
    uv_category: Optional[str] = None

    # Forecast
    high_f: Optional[float] = None
    low_f: Optional[float] = None
    rain_chance_pct: Optional[int] = Field(default=None, ge=0, le=100)
    snow_chance_pct: Optional[int] = Field(default=None, ge=0, le=100)
    forecast_condition: Optional[str] = None

    # Metadata
    data_source: str = "google_weather_api"
    fetch_timestamp: Optional[datetime] = None
    data_freshness_min: Optional[int] = None

    @field_validator("temperature_f")
    @classmethod
    def validate_temp(cls, v: float) -> float:
        if v < -60 or v > 140:
            raise ValueError(f"Temperature {v}°F is out of plausible range [-60, 140]")
        return v

    def compute_derived_fields(self) -> None:
        """Compute wind chill, heat index, and UV category."""
        # Wind Chill (valid when temp < 50°F and wind > 3 mph)
        if self.temperature_f < 50 and self.wind_speed_mph > 3:
            self.wind_chill_f = (
                35.74
                + 0.6215 * self.temperature_f
                - 35.75 * (self.wind_speed_mph**0.16)
                + 0.4275 * self.temperature_f * (self.wind_speed_mph**0.16)
            )

        # Heat Index (valid when temp > 80°F)
        if self.temperature_f > 80:
            t = self.temperature_f
            h = self.humidity_pct
            self.heat_index_f = (
                -42.379
                + 2.04901523 * t
                + 10.14333127 * h
                - 0.22475541 * t * h
                - 6.83783e-3 * t**2
                - 5.481717e-2 * h**2
                + 1.22874e-3 * t**2 * h
                + 8.5282e-4 * t * h**2
                - 1.99e-6 * t**2 * h**2
            )

        # UV Category
        if self.uv_index is not None:
            if self.uv_index < 3:
                self.uv_category = "Low"
            elif self.uv_index < 6:
                self.uv_category = "Moderate"
            elif self.uv_index < 8:
                self.uv_category = "High"
            elif self.uv_index < 11:
                self.uv_category = "Very High"
            else:
                self.uv_category = "Extreme"


# ---------------------------------------------------------------------------
# Run Manifest
# ---------------------------------------------------------------------------
class RunManifest(BaseModel):
    """Pipeline execution metadata."""

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending | running | success | partial | failed
    stage_timings: dict[str, float] = Field(default_factory=dict)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    degradation_level: str = "L0"  # L0-L5


# ---------------------------------------------------------------------------
# Weather Report (output)
# ---------------------------------------------------------------------------
class WeatherReport(BaseModel):
    """Complete output artifact."""

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: Optional[datetime] = None

    # Source data
    weather_data: Optional[NormalizedWeather] = None

    # Generated content
    script_text: Optional[str] = None
    script_word_count: int = 0

    # Artifact paths (Drive file IDs)
    script_drive_id: Optional[str] = None
    audio_drive_id: Optional[str] = None
    video_drive_id: Optional[str] = None
    raw_data_drive_id: Optional[str] = None

    # Quality
    validation_passed: bool = False
    hallucination_flags: list[str] = Field(default_factory=list)

    # Pipeline metadata
    manifest: RunManifest = Field(default_factory=RunManifest)
