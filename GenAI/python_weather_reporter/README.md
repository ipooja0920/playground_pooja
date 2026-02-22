# Daily AI Weather Reporter 🌤️

A production-grade Python system that generates daily AI weather broadcast reports for **Storrs, Connecticut**.

## Features

| Feature | Description |
|---|---|
| 🌡️ **Weather Data** | Fetches real-time data from Google Weather API (OpenWeatherMap fallback) |
| 🤖 **AI Script** | Generates 5-10 minute broadcast scripts using Google Gemini 2.0 Flash |
| 🔊 **Audio** | Converts script to speech using Google Cloud TTS (WaveNet) |
| 🎬 **Video** | Generates weather video using Google Veo (MoviePy fallback) |
| 📁 **Storage** | Uploads all outputs to Google Drive with organized date folders |
| 📊 **Logging** | Logs historical weather data to Google Sheets |
| 🛡️ **Resilient** | Anti-hallucination validation, retry logic, graceful degradation |

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and credentials
```

**Required credentials:**
- `GOOGLE_API_KEY` — Gemini API key
- `GOOGLE_APPLICATION_CREDENTIALS` — Path to service account JSON
- `DRIVE_FOLDER_ID` — Google Drive folder for uploads
- `SPREADSHEET_ID` — Google Sheet for logging

### 3. Run

```bash
# Full pipeline (script + audio + video)
python main.py

# Script + audio only (skip video)
python main.py --no-video

# Text script only
python main.py --no-audio

# Dry run (fetch + script, no uploads)
python main.py --dry-run

# Verbose debug logging
python main.py --dry-run -v
```

## Architecture

```
main.py                 CLI entry point
  └── pipeline.py       9-stage orchestrator
        ├── services/weather_fetcher.py    Google Weather API + fallback
        ├── services/script_generator.py   Gemini + anti-hallucination
        ├── services/audio_generator.py    Cloud TTS + gTTS fallback
        ├── services/video_generator.py    Veo + MoviePy fallback
        └── services/storage.py            Drive + Sheets
```

## Graceful Degradation

| Level | Condition | Output |
|---|---|---|
| L0 | All services up | Video + Audio + Script + Data |
| L1 | Veo unavailable | Title-card video + Audio + Script + Data |
| L2 | TTS unavailable | Script + Data (text only) |
| L3 | LLM unavailable | Template script + Data |
| L5 | Weather API down | Alert sent, no report |

## Scheduling (Production)

For daily 7 AM runs, use **cron** (local) or **Google Cloud Scheduler** (production):

```bash
# crontab -e
0 7 * * * cd /path/to/python_weather_reporter && python main.py >> /var/log/weather_reporter.log 2>&1
```
