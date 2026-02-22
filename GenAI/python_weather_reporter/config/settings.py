"""
Configuration management using Pydantic Settings.
All config is driven by environment variables or .env file.
"""

import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Google API Keys ---
    google_api_key: str = Field(..., description="Gemini API key")
    google_application_credentials: str = Field(
        ..., description="Path to service account JSON"
    )

    # --- Fallback Weather API ---
    openweathermap_api_key: str = Field(
        default="", description="OpenWeatherMap API key (fallback)"
    )

    # --- Google Sheets ---
    spreadsheet_id: str = Field(..., description="Google Sheet ID for logging")
    sheet_name: str = Field(default="WeatherLog", description="Sheet tab name")

    # --- Google Drive ---
    drive_folder_id: str = Field(..., description="Drive folder ID for uploads")

    # --- Location ---
    city: str = Field(default="Storrs")
    state: str = Field(default="Connecticut")
    latitude: float = Field(default=41.8084)
    longitude: float = Field(default=-72.2495)

    # --- Feature Flags ---
    enable_audio: bool = Field(default=True)
    enable_video: bool = Field(default=True)
    veo_fallback: bool = Field(
        default=True, description="Fall back to MoviePy if Veo fails"
    )

    # --- TTS Config ---
    tts_voice_name: str = Field(default="en-US-Wavenet-D")
    tts_speaking_rate: float = Field(default=1.0)

    # --- Gemini Config ---
    gemini_model: str = Field(default="gemini-2.0-flash")
    gemini_max_retries: int = Field(default=2)

    @property
    def location_display(self) -> str:
        return f"{self.city}, {self.state}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """Factory function with .env path resolution."""
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
    )
    if os.path.exists(env_path):
        return Settings(_env_file=env_path)
    return Settings()
