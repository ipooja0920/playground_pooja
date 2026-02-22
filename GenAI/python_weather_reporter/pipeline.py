"""
Pipeline orchestrator for the Daily AI Weather Reporter.
Executes stages sequentially with timing, error handling, and graceful degradation.
"""

import logging
import time
from datetime import datetime

from config.settings import Settings
from models.schemas import NormalizedWeather, RunManifest, WeatherReport
from services.weather_fetcher import WeatherFetcher, WeatherFetchError
from services.script_generator import ScriptGenerator
from services.audio_generator import AudioGenerator
from services.video_generator import VideoGenerator
from services.storage import StorageService

logger = logging.getLogger(__name__)


class Pipeline:
    """Orchestrates the full weather report generation pipeline."""

    def __init__(self, settings: Settings, enable_audio: bool = True,
                 enable_video: bool = True, dry_run: bool = False):
        self.settings = settings
        self.enable_audio = enable_audio and settings.enable_audio
        self.enable_video = enable_video and settings.enable_video
        self.dry_run = dry_run

        # Initialize services
        self.weather_fetcher = WeatherFetcher(settings)
        self.script_generator = ScriptGenerator(settings)
        self.audio_generator = AudioGenerator(settings) if self.enable_audio else None
        self.video_generator = VideoGenerator(settings) if self.enable_video else None
        self.storage = StorageService(settings) if not dry_run else None

    def run(self) -> WeatherReport:
        """Execute the full pipeline. Returns a WeatherReport with results."""
        report = WeatherReport(generated_at=datetime.now())
        manifest = report.manifest
        manifest.started_at = datetime.now()
        manifest.status = "running"

        logger.info(f"Pipeline started | Run ID: {manifest.run_id}")
        logger.info(f"Mode: audio={self.enable_audio}, video={self.enable_video}, dry_run={self.dry_run}")

        # ---------------------------------------------------------------
        # Stage 1: Fetch Weather Data
        # ---------------------------------------------------------------
        weather = self._run_stage(manifest, "fetch", self._stage_fetch)
        if weather is None:
            manifest.status = "failed"
            manifest.degradation_level = "L5"
            manifest.completed_at = datetime.now()
            logger.error("Pipeline FAILED: No weather data")
            return report

        report.weather_data = weather

        # ---------------------------------------------------------------
        # Stage 2: Generate Script
        # ---------------------------------------------------------------
        script = self._run_stage(manifest, "script", self._stage_script, weather)
        if script:
            report.script_text = script
            report.script_word_count = len(script.split())
            report.validation_passed = True
        else:
            manifest.degradation_level = "L3"
            manifest.errors.append("Script generation failed")
            manifest.status = "partial"
            manifest.completed_at = datetime.now()
            logger.warning("Pipeline PARTIAL: No script generated")
            return report

        # ---------------------------------------------------------------
        # Stage 3: Upload text + raw data (if not dry run)
        # ---------------------------------------------------------------
        if not self.dry_run:
            self._run_stage(manifest, "upload_text", self._stage_upload_text, report)

        # ---------------------------------------------------------------
        # Stage 4: Generate Audio
        # ---------------------------------------------------------------
        audio_fp = None
        if self.enable_audio and script:
            audio_fp = self._run_stage(manifest, "audio", self._stage_audio, script)
            if audio_fp is None:
                manifest.degradation_level = "L2"
                manifest.errors.append("Audio generation failed")

        # ---------------------------------------------------------------
        # Stage 5: Generate Video
        # ---------------------------------------------------------------
        video_fp = None
        if self.enable_video and audio_fp:
            video_fp = self._run_stage(
                manifest, "video", self._stage_video, audio_fp, weather
            )
            if video_fp is None:
                if manifest.degradation_level == "L0":
                    manifest.degradation_level = "L1"
                manifest.errors.append("Video generation failed")

        # ---------------------------------------------------------------
        # Stage 6: Upload audio/video (if not dry run)
        # ---------------------------------------------------------------
        if not self.dry_run:
            if audio_fp:
                self._run_stage(
                    manifest, "upload_audio", self._stage_upload_audio,
                    report, audio_fp
                )
            if video_fp:
                self._run_stage(
                    manifest, "upload_video", self._stage_upload_video,
                    report, video_fp
                )

        # ---------------------------------------------------------------
        # Stage 7: Log to Sheets (if not dry run)
        # ---------------------------------------------------------------
        if not self.dry_run:
            self._run_stage(manifest, "log_sheets", self._stage_log, weather)

        # ---------------------------------------------------------------
        # Finalize
        # ---------------------------------------------------------------
        manifest.completed_at = datetime.now()
        if manifest.status == "running":
            manifest.status = "success" if not manifest.errors else "partial"

        total = (manifest.completed_at - manifest.started_at).total_seconds()
        logger.info(
            f"Pipeline completed | Status: {manifest.status} | "
            f"Degradation: {manifest.degradation_level} | "
            f"Duration: {total:.1f}s"
        )

        return report

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------
    def _stage_fetch(self) -> NormalizedWeather:
        return self.weather_fetcher.fetch()

    def _stage_script(self, weather: NormalizedWeather) -> str:
        return self.script_generator.generate(weather)

    def _stage_audio(self, script: str):
        return self.audio_generator.generate(script)

    def _stage_video(self, audio_fp, weather: NormalizedWeather):
        return self.video_generator.generate(audio_fp, weather)

    def _stage_upload_text(self, report: WeatherReport) -> None:
        folder_id = self.storage.get_or_create_date_folder(
            self.settings.drive_folder_id
        )
        # Upload script
        date_str = report.weather_data.report_date.isoformat()
        report.script_drive_id = self.storage.upload_to_drive(
            report.script_text,
            f"broadcast_script_{date_str}.txt",
            "text/plain",
            folder_id,
        )
        # Upload raw data
        report.raw_data_drive_id = self.storage.upload_raw_data(
            report.weather_data, folder_id
        )

    def _stage_upload_audio(self, report: WeatherReport, audio_fp) -> None:
        folder_id = self.storage.get_or_create_date_folder(
            self.settings.drive_folder_id
        )
        date_str = report.weather_data.report_date.isoformat()
        report.audio_drive_id = self.storage.upload_to_drive(
            audio_fp,
            f"broadcast_audio_{date_str}.mp3",
            "audio/mpeg",
            folder_id,
        )

    def _stage_upload_video(self, report: WeatherReport, video_fp) -> None:
        folder_id = self.storage.get_or_create_date_folder(
            self.settings.drive_folder_id
        )
        date_str = report.weather_data.report_date.isoformat()
        report.video_drive_id = self.storage.upload_to_drive(
            video_fp,
            f"broadcast_video_{date_str}.mp4",
            "video/mp4",
            folder_id,
        )

    def _stage_log(self, weather: NormalizedWeather) -> None:
        self.storage.log_to_sheets(weather)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _run_stage(self, manifest: RunManifest, name: str, func, *args):
        """Run a pipeline stage with timing and error handling."""
        start = time.time()
        try:
            result = func(*args)
            elapsed = time.time() - start
            manifest.stage_timings[name] = round(elapsed, 2)
            logger.info(f"Stage [{name}] completed in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start
            manifest.stage_timings[name] = round(elapsed, 2)
            manifest.errors.append(f"{name}: {str(e)}")
            manifest.retry_counts[name] = manifest.retry_counts.get(name, 0) + 1
            logger.error(f"Stage [{name}] failed after {elapsed:.2f}s: {e}")
            return None
