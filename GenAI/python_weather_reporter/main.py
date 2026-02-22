"""
Daily AI Weather Reporter — CLI Entry Point
Generates a weather broadcast for Storrs, Connecticut.

Usage:
    python main.py                    # Full pipeline (script + audio + video)
    python main.py --no-video         # Script + audio only
    python main.py --no-audio         # Script only (text)
    python main.py --dry-run          # Fetch + generate script, no uploads
"""

import argparse
import logging
import sys

from config.settings import get_settings
from pipeline import Pipeline


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Reduce noise from third-party libs
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("oauth2client").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(
        description="Daily AI Weather Reporter — Storrs, CT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Skip audio generation",
    )
    parser.add_argument(
        "--no-video",
        action="store_true",
        help="Skip video generation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch weather + generate script only (no uploads, no audio/video)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger("main")

    # Load settings
    try:
        settings = get_settings()
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        logger.error("Make sure .env file exists. See .env.example")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("  DAILY AI WEATHER REPORTER")
    logger.info(f"  Location: {settings.location_display}")
    logger.info(f"  Coordinates: {settings.latitude}, {settings.longitude}")
    logger.info("=" * 60)

    # Run pipeline
    enable_audio = not args.no_audio and not args.dry_run
    enable_video = not args.no_video and not args.dry_run

    pipeline = Pipeline(
        settings=settings,
        enable_audio=enable_audio,
        enable_video=enable_video,
        dry_run=args.dry_run,
    )

    report = pipeline.run()

    # Print summary
    manifest = report.manifest
    logger.info("")
    logger.info("=" * 60)
    logger.info("  PIPELINE RESULTS")
    logger.info("=" * 60)
    logger.info(f"  Status:       {manifest.status}")
    logger.info(f"  Degradation:  {manifest.degradation_level}")
    logger.info(f"  Run ID:       {manifest.run_id}")

    if manifest.stage_timings:
        logger.info("  Stage Timings:")
        for stage, secs in manifest.stage_timings.items():
            logger.info(f"    {stage:20s} {secs:6.2f}s")

    total = None
    if manifest.started_at and manifest.completed_at:
        total = (manifest.completed_at - manifest.started_at).total_seconds()
        logger.info(f"  Total:        {total:.2f}s")

    if manifest.errors:
        logger.warning("  Errors:")
        for err in manifest.errors:
            logger.warning(f"    - {err}")

    if report.script_text:
        logger.info(f"  Script:       {report.script_word_count} words")

    if report.script_drive_id:
        logger.info(f"  Script ID:    {report.script_drive_id}")
    if report.audio_drive_id:
        logger.info(f"  Audio ID:     {report.audio_drive_id}")
    if report.video_drive_id:
        logger.info(f"  Video ID:     {report.video_drive_id}")

    logger.info("=" * 60)

    # Print script preview in dry-run mode
    if args.dry_run and report.script_text:
        print("\n--- SCRIPT PREVIEW ---\n")
        print(report.script_text)
        print("\n--- END PREVIEW ---")

    # Exit code based on status
    if manifest.status == "failed":
        sys.exit(1)
    elif manifest.status == "partial":
        sys.exit(0)  # Partial success is still success
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
