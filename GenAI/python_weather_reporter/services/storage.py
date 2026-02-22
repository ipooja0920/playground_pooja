"""
Output storage: Google Drive upload and Google Sheets logging.
"""

import io
import json
import logging
import os
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import Settings
from models.schemas import NormalizedWeather

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class StorageService:
    """Handles Google Drive uploads and Sheets logging."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._creds = None

    @property
    def creds(self):
        """Lazy-load credentials."""
        if self._creds is None:
            cred_path = self.settings.google_application_credentials
            if not os.path.exists(cred_path):
                raise FileNotFoundError(
                    f"Service account file not found: {cred_path}"
                )
            self._creds = service_account.Credentials.from_service_account_file(
                cred_path, scopes=SCOPES
            )
        return self._creds

    # ------------------------------------------------------------------
    # Google Drive
    # ------------------------------------------------------------------
    def get_or_create_date_folder(self, parent_folder_id: str) -> str:
        """Create organized folder structure: YYYY/MM/DD under parent."""
        drive = build("drive", "v3", credentials=self.creds)
        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")

        year_id = self._get_or_create_subfolder(drive, parent_folder_id, year)
        month_id = self._get_or_create_subfolder(drive, year_id, month)
        day_id = self._get_or_create_subfolder(drive, month_id, day)
        return day_id

    def _get_or_create_subfolder(
        self, drive, parent_id: str, name: str
    ) -> str:
        """Find or create a subfolder by name under parent."""
        query = (
            f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
            f"and '{parent_id}' in parents and trashed=false"
        )
        results = drive.files().list(q=query, fields="files(id)").execute()
        files = results.get("files", [])
        if files:
            return files[0]["id"]

        # Create folder
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = drive.files().create(body=metadata, fields="id").execute()
        logger.info(f"Created Drive folder: {name} ({folder['id']})")
        return folder["id"]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
    )
    def upload_to_drive(
        self,
        content: str | io.BytesIO,
        filename: str,
        mime_type: str,
        folder_id: str,
    ) -> str | None:
        """Upload a file to Google Drive. Returns file ID."""
        drive = build("drive", "v3", credentials=self.creds)

        metadata = {
            "name": filename,
            "parents": [folder_id],
            "mimeType": mime_type,
        }

        if isinstance(content, str):
            media = MediaIoBaseUpload(
                io.BytesIO(content.encode("utf-8")), mimetype=mime_type
            )
        else:
            content.seek(0)
            media = MediaIoBaseUpload(content, mimetype=mime_type)

        try:
            file = (
                drive.files()
                .create(body=metadata, media_body=media, fields="id")
                .execute()
            )
            file_id = file.get("id")
            logger.info(f"Uploaded to Drive: {filename} (ID: {file_id})")
            return file_id
        except Exception as e:
            logger.error(f"Drive upload failed for {filename}: {e}")
            raise

    # ------------------------------------------------------------------
    # Google Sheets
    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
    )
    def log_to_sheets(self, weather: NormalizedWeather) -> None:
        """Append a row of weather data to the Google Sheet."""
        sheets = build("sheets", "v4", credentials=self.creds)

        row = [
            weather.report_date.isoformat(),
            weather.report_time.strftime("%H:%M:%S"),
            weather.location_name,
            weather.temperature_f,
            weather.feels_like_f,
            weather.humidity_pct,
            weather.wind_speed_mph,
            weather.wind_direction,
            weather.condition_text,
            weather.pressure_inhg or "",
            weather.uv_index or "",
            weather.uv_category or "",
            weather.high_f or "",
            weather.low_f or "",
            weather.rain_chance_pct or "",
            weather.snow_chance_pct or "",
            weather.wind_chill_f or "",
            weather.data_source,
        ]

        body = {"values": [row]}
        try:
            sheets.spreadsheets().values().append(
                spreadsheetId=self.settings.spreadsheet_id,
                range=f"{self.settings.sheet_name}!A:R",
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()
            logger.info("Weather data logged to Google Sheets")
        except Exception as e:
            logger.error(f"Sheets logging failed: {e}")
            raise

    def upload_raw_data(
        self, weather: NormalizedWeather, folder_id: str
    ) -> str | None:
        """Upload raw weather data as JSON to Drive."""
        data_json = weather.model_dump_json(indent=2)
        filename = f"weather_data_{weather.report_date.isoformat()}.json"
        return self.upload_to_drive(data_json, filename, "application/json", folder_id)
