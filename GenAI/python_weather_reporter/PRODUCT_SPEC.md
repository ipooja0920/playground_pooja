# Daily AI Weather Reporter — Product Specification

**Version**: 1.0  
**Date**: February 21, 2026  
**Author**: AI Systems Architecture  
**Location Target**: Storrs, Connecticut  
**Schedule**: Daily at 7:00 AM EST  

---

## 1. System Overview

### 1.1 High-Level Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        DAILY AI WEATHER REPORTER                        │
│                                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────┐  │
│  │  SCHEDULER   │───▶│  DATA LAYER  │───▶│  AI LAYER    │───▶│ OUTPUT │  │
│  │ (Cloud Sched)│    │              │    │              │    │ LAYER  │  │
│  └─────────────┘    │ Weather API  │    │ Gemini LLM   │    │        │  │
│                     │ (Google)     │    │ Google TTS   │    │ Drive  │  │
│                     │ Google Sheets│    │ Google Veo   │    │ Upload │  │
│                     └──────────────┘    └──────────────┘    └────────┘  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                     OBSERVABILITY LAYER                            │ │
│  │          Cloud Logging  ·  Error Reporting  ·  Metrics             │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

### 1.2 End-to-End Data Pipeline

```
06:55 AM ─ Cloud Scheduler fires trigger
      │
      ▼
[1] FETCH ─── Google Weather API (Storrs, CT)
      │        └─ Fallback: OpenWeatherMap / NWS API
      ▼
[2] VALIDATE ─ Schema validation + missing field detection
      │
      ▼
[3] NORMALIZE ─ Convert units, enrich with derived fields
      │           (heat index, wind chill, UV category)
      ▼
[4] GENERATE SCRIPT ─ Gemini 2.0 Flash (LLM)
      │                 └─ System prompt + weather JSON → broadcast script
      ▼
[5] VALIDATE SCRIPT ─ Output contract enforcement
      │                 └─ Reject hallucinated data, re-generate if needed
      ▼
[6] GENERATE AUDIO ─ Google Cloud Text-to-Speech (WaveNet)
      │
      ▼
[7] GENERATE VIDEO ─ Google Veo (image + audio → video)
      │
      ▼
[8] UPLOAD ─ Google Drive (organized by date)
      │
      ▼
[9] NOTIFY ─ Optional email/Slack notification
      │
07:00 AM ─ Report available
```

### 1.3 External Dependencies

| Dependency | Purpose | Criticality |
|---|---|---|
| Google Weather API | Real-time weather data | **Critical** |
| Google Gemini 2.0 Flash | Script generation | **Critical** |
| Google Cloud TTS (WaveNet) | Spoken audio generation | **Critical** |
| Google Veo | Video generation from audio + visuals | **High** |
| Google Sheets API | Historical data logging | Medium |
| Google Drive API | Output storage & delivery | **High** |
| Google Cloud Scheduler | Daily 7 AM trigger | **High** |
| Google Cloud Run / Functions | Compute environment | **High** |

---

## 2. Functional Requirements

### FR-01: Scheduled Trigger

| Field | Detail |
|---|---|
| **Description** | System triggers automatically at 7:00 AM EST every day |
| **Acceptance Criteria** | Trigger fires within ±60 seconds of 07:00:00 EST, 365 days/year. Handles DST transitions (EST ↔ EDT) |
| **Edge Cases** | Cloud Scheduler downtime → manual trigger endpoint available; Leap seconds ignored |

### FR-02: Weather Data Fetching

| Field | Detail |
|---|---|
| **Description** | Fetch current conditions + 24-hour forecast for Storrs, CT (41.8084° N, 72.2495° W) |
| **Acceptance Criteria** | Returns temperature, feels-like, humidity, wind speed/direction, precipitation probability, UV index, visibility, pressure, weather condition within 5 seconds |
| **Edge Cases** | API rate limit → exponential backoff (3 retries, 2s/4s/8s). API returns stale data (>30 min old) → log warning, proceed with disclaimer. API down → fallback to secondary provider |

### FR-03: Data Validation & Normalization

| Field | Detail |
|---|---|
| **Description** | Validate all incoming weather fields against expected ranges and normalize units |
| **Acceptance Criteria** | Temperature: -50°F to 130°F. Humidity: 0–100%. Wind: 0–200 mph. Precipitation: 0–100%. Invalid values flagged and replaced with "data unavailable" |
| **Edge Cases** | Partial API response (missing fields) → fill with "N/A", flag in report. All-null response → abort pipeline, send alert |

### FR-04: AI Script Generation

| Field | Detail |
|---|---|
| **Description** | Generate a natural-language broadcast script (800–1500 words, 5–10 min read time) using Gemini |
| **Acceptance Criteria** | Script includes all 7 segments: Teaser, Current Conditions, Meteorological Context, Commuter Forecast, Lifestyle/Health, Weekly Outlook, Sign-off. Script references actual data values. No fabricated temperature/wind values |
| **Edge Cases** | LLM timeout (>30s) → retry once. LLM returns short response (<200 words) → re-prompt with "expand" instruction. LLM hallucinates numbers not in input → validation layer catches and regenerates (max 2 retries) |

### FR-05: Script Validation (Anti-Hallucination)

| Field | Detail |
|---|---|
| **Description** | Verify that all numerical values in the generated script match the source weather data |
| **Acceptance Criteria** | Temperature in script within ±1° of source. Wind speed within ±2 mph. Precipitation within ±5%. Location name matches exactly |
| **Edge Cases** | LLM paraphrases values ("mid-thirties" for 35°F) → allow fuzzy match. Invented forecast numbers for future days → allow (clearly speculative). Completely wrong location mentioned → reject and regenerate |

### FR-06: Audio Generation

| Field | Detail |
|---|---|
| **Description** | Convert validated script to natural-sounding audio using Google Cloud TTS (WaveNet voice) |
| **Acceptance Criteria** | Output: MP3, 48kHz, mono. Duration: 5–10 minutes. Voice: en-US WaveNet-D (male) or WaveNet-F (female). Speaking rate: 1.0x |
| **Edge Cases** | Script exceeds TTS character limit (5000 chars/request) → chunk script into paragraphs, concatenate audio. TTS returns silence → retry. Special characters (°, %) → pre-process to spoken equivalents ("degrees", "percent") |

### FR-07: Video Generation (Veo)

| Field | Detail |
|---|---|
| **Description** | Generate a weather report video using Google Veo, combining visual elements with the broadcast audio |
| **Acceptance Criteria** | Output: MP4, 1080p (1920×1080), 24fps. Duration matches audio length. Visual: weather-themed scenes contextual to conditions (sunny → bright outdoor, rain → rainy cityscape). Audio track synchronized |
| **Edge Cases** | Veo generation timeout (>5 min) → fall back to static title-card video (Pillow + MoviePy). Veo returns low-quality output → accept if >720p, reject otherwise. Veo unavailable → automatic fallback to title-card mode |

### FR-08: Output Storage

| Field | Detail |
|---|---|
| **Description** | Upload all outputs to a structured Google Drive folder |
| **Acceptance Criteria** | Folder structure: `CT_Weather_Data_Daily/YYYY/MM/DD/`. Files: `script.txt`, `audio.mp3`, `video.mp4`, `weather_data.json`. Upload completes within 60 seconds |
| **Edge Cases** | Drive quota exceeded → alert admin, store locally. Upload fails mid-way → retry individual file (not full pipeline). Duplicate date → append timestamp suffix |

### FR-09: Historical Data Logging

| Field | Detail |
|---|---|
| **Description** | Append each day's raw weather data to a Google Sheet for trend analysis |
| **Acceptance Criteria** | One row per day. Columns: date, location, temp, feels_like, humidity, wind_speed, wind_dir, precip_prob, uv_index, condition, pressure. Sheet auto-creates new tab per month |
| **Edge Cases** | Sheet API rate limit → queue and retry. Sheet reaches row limit (10M) → create new sheet. Write conflict → use exponential backoff |

### FR-10: Notification

| Field | Detail |
|---|---|
| **Description** | Send notification upon successful report generation with a link to the Drive folder |
| **Acceptance Criteria** | Notification sent within 2 minutes of pipeline completion. Includes: status (success/partial/failure), Drive link, runtime duration |
| **Edge Cases** | Notification service down → log locally, do not block pipeline. Partial success (audio OK, video failed) → send with warning |

---

## 3. Non-Functional Requirements

### 3.1 Latency Targets

| Stage | Target | Max |
|---|---|---|
| Weather API fetch | 2s | 10s |
| Data validation | 50ms | 200ms |
| LLM script generation | 15s | 45s |
| Script validation | 100ms | 500ms |
| TTS audio generation | 30s | 120s |
| Veo video generation | 120s | 300s |
| Drive upload | 15s | 60s |
| **Total pipeline** | **~3 min** | **~9 min** |

### 3.2 Reliability & Availability

- **Uptime target**: 99.5% (allows ~1.8 missed days/year)
- **Retry policy**: Each stage retries up to 3 times with exponential backoff
- **Fallback chain**: Veo → MoviePy title-card; Google Weather API → OpenWeatherMap → cached last-known data
- **Dead letter queue**: Failed runs logged and retried manually via admin endpoint

### 3.3 Scalability

- **Current**: Single location (Storrs, CT), single daily run
- **Designed for**: Multi-location (up to 50 cities) via config-driven location list
- **Horizontal scaling**: Each location runs as an independent Cloud Run job
- **Cost scales linearly**: ~$0.15/city/day at current API pricing

### 3.4 Observability & Logging

| Component | Tool |
|---|---|
| Structured logging | Python `logging` → Google Cloud Logging |
| Error alerting | Google Cloud Error Reporting → email/Slack |
| Pipeline metrics | Custom metrics: `pipeline_duration_seconds`, `stage_success_rate`, `api_latency_seconds` |
| Dashboards | Google Cloud Monitoring dashboard |
| Audit trail | Every run produces a `run_manifest.json` with stage timestamps, statuses, and artifact IDs |

### 3.5 Cost Constraints

| Service | Estimated Daily Cost | Monthly |
|---|---|---|
| Google Weather API | Free tier / ~$0.01 | ~$0.30 |
| Gemini 2.0 Flash | ~$0.002 (input+output tokens) | ~$0.06 |
| Cloud TTS (WaveNet) | ~$0.06 (per 1M chars, ~5K chars/day) | ~$1.80 |
| Google Veo | ~$0.10–0.50 (per video) | ~$3–15 |
| Google Drive | Free (within 15GB quota) | $0 |
| Cloud Run | ~$0.01 (per invocation, <512MB, <5min) | ~$0.30 |
| Cloud Scheduler | Free (up to 3 jobs) | $0 |
| **Total** | **~$0.20–0.60/day** | **~$6–18/month** |

---

## 4. Tech Stack

| Layer | Technology | Justification |
|---|---|---|
| **Language** | Python 3.11+ | Richest ecosystem for AI/ML, Google Cloud SDKs, rapid prototyping |
| **Weather API** | Google Weather API | First-party Google integration, reliable, structured JSON response, free tier available |
| **Weather Fallback** | OpenWeatherMap API | Mature, well-documented, generous free tier (1000 calls/day) |
| **LLM** | Google Gemini 2.0 Flash | Fast inference, low cost, excellent instruction following, native Google auth |
| **Text-to-Speech** | Google Cloud TTS (WaveNet) | Studio-quality voices, SSML support, fine-grained control over prosody |
| **Video Generation** | Google Veo | Native Google ecosystem, generates contextual weather visuals from prompts, API-accessible |
| **Video Fallback** | MoviePy + Pillow | Offline fallback for title-card videos when Veo is unavailable |
| **Storage** | Google Drive API v3 | User-accessible, no infrastructure to manage, shareable links |
| **Data Logging** | Google Sheets API v4 | Visual, collaborative, easy trend analysis, no database setup |
| **Scheduling** | Google Cloud Scheduler | Managed cron, timezone-aware, integrates with Cloud Run |
| **Compute** | Google Cloud Run (Jobs) | Serverless, pay-per-use, auto-scales to zero, Docker-based |
| **Logging** | Google Cloud Logging | Native integration with Cloud Run, structured logs, alerting |
| **Config** | `.env` + Google Secret Manager | Secrets never in code; local dev via `.env`, production via Secret Manager |

### Python Libraries

| Package | Purpose |
|---|---|
| `google-cloud-aiplatform` | Gemini API + Veo API access |
| `google-generativeai` | Gemini client (alternative lightweight SDK) |
| `google-cloud-texttospeech` | WaveNet TTS |
| `google-api-python-client` | Sheets + Drive APIs |
| `google-auth` | Service account authentication |
| `requests` | HTTP calls to Weather API |
| `pydantic` | Data validation & schema enforcement |
| `python-dotenv` | Local environment variable loading |
| `moviepy` | Fallback video assembly |
| `Pillow` | Fallback title card generation |
| `tenacity` | Retry logic with exponential backoff |
| `structlog` | Structured logging |

---

## 5. Data Models

### 5.1 Input Weather Schema (Raw API Response)

```json
{
  "location": {
    "name": "Storrs",
    "region": "Connecticut",
    "country": "US",
    "lat": 41.8084,
    "lon": -72.2495
  },
  "current": {
    "temp_f": 28.4,
    "feelslike_f": 18.2,
    "humidity": 65,
    "wind_mph": 12.3,
    "wind_dir": "NW",
    "pressure_in": 30.12,
    "precip_in": 0.0,
    "uv": 2.0,
    "vis_miles": 10.0,
    "condition": {
      "text": "Partly Cloudy",
      "code": 1003
    }
  },
  "forecast": {
    "forecastday": [
      {
        "date": "2026-02-21",
        "day": {
          "maxtemp_f": 35.0,
          "mintemp_f": 22.0,
          "daily_chance_of_rain": 10,
          "daily_chance_of_snow": 40,
          "condition": { "text": "Light Snow", "code": 1213 }
        }
      }
    ]
  }
}
```

### 5.2 Internal Normalized Schema

```python
@dataclass
class NormalizedWeather:
    # Location
    location_name: str          # "Storrs, Connecticut"
    latitude: float             # 41.8084
    longitude: float            # -72.2495
    
    # Timestamp
    report_date: date           # 2026-02-21
    report_time: time           # 07:00:00
    timezone: str               # "America/New_York"
    
    # Current Conditions
    temperature_f: float        # 28.4
    feels_like_f: float         # 18.2
    humidity_pct: int           # 65
    wind_speed_mph: float       # 12.3
    wind_direction: str         # "NW"
    pressure_inhg: float        # 30.12
    visibility_miles: float     # 10.0
    uv_index: float             # 2.0
    condition_text: str         # "Partly Cloudy"
    condition_code: int         # 1003
    
    # Derived Fields
    wind_chill_f: float | None  # Calculated if temp < 50°F and wind > 3 mph
    heat_index_f: float | None  # Calculated if temp > 80°F
    uv_category: str            # "Low" | "Moderate" | "High" | "Very High" | "Extreme"
    
    # Forecast
    high_f: float               # 35.0
    low_f: float                # 22.0
    rain_chance_pct: int        # 10
    snow_chance_pct: int        # 40
    forecast_condition: str     # "Light Snow"
    
    # Metadata
    data_source: str            # "google_weather_api"
    fetch_timestamp: datetime   # When data was retrieved
    data_freshness_min: int     # Minutes since last API update
```

### 5.3 Output Structured Report Schema

```python
@dataclass
class WeatherReport:
    # Identity
    report_id: str              # UUID
    generated_at: datetime      # Pipeline completion timestamp
    
    # Source Data
    weather_data: NormalizedWeather
    
    # Generated Content
    script_text: str            # Full broadcast script (800-1500 words)
    script_word_count: int      # Validated word count
    script_segments: list[str]  # ["teaser", "current", "context", "commuter",
                                #  "lifestyle", "outlook", "signoff"]
    
    # Artifacts
    audio_path: str             # GDrive path to MP3
    audio_duration_sec: float   # Duration in seconds
    video_path: str             # GDrive path to MP4
    video_duration_sec: float   # Duration in seconds
    video_source: str           # "veo" | "moviepy_fallback"
    raw_data_path: str          # GDrive path to weather_data.json
    
    # Quality
    validation_passed: bool     # Script validation result
    hallucination_flags: list   # Any flagged discrepancies
    retry_count: int            # Number of LLM retries needed
    
    # Metadata
    pipeline_duration_sec: float
    stage_timings: dict         # {"fetch": 2.1, "llm": 14.3, ...}
    status: str                 # "success" | "partial" | "failed"
```

---

## 6. Output Contract

A valid weather report **MUST** contain all of the following in the generated script. Any missing element triggers a regeneration.

| # | Required Element | Script Representation | Validation |
|---|---|---|---|
| 1 | **Location** | "Storrs, Connecticut" or "Storrs, CT" | Exact substring match |
| 2 | **Timestamp** | Day of week + date (e.g., "this Saturday, February 21st") | Day-of-week matches actual calendar |
| 3 | **Current Conditions** | Condition description (e.g., "partly cloudy skies") | Semantic match to `condition_text` |
| 4 | **Temperature** | Current temp + feels-like (e.g., "28 degrees, feels like 18") | Within ±1°F of source |
| 5 | **Wind** | Speed + direction (e.g., "northwest winds at 12 miles per hour") | Speed within ±2 mph, direction matches |
| 6 | **Precipitation Probability** | Rain/snow chance (e.g., "40% chance of light snow") | Within ±5% of source |
| 7 | **Forecast Summary** | High/low + general outlook | High/low within ±2°F of source |
| 8 | **Spoken-Style Script** | Conversational tone, no raw JSON/numbers-as-data | No markdown formatting, no bullet points, reads naturally aloud |

### Example Output Contract Validation

```
INPUT:  temperature_f = 28.4
SCRIPT: "...sitting at a brisk twenty-eight degrees..."
RESULT: ✅ PASS (28 ≈ 28.4, within ±1°F)

INPUT:  wind_speed_mph = 12.3
SCRIPT: "...winds gusting to forty-five miles per hour..."
RESULT: ❌ FAIL (45 ≠ 12.3, hallucination detected → regenerate)
```

---

## 7. Failure Modes & Fallback Strategy

### 7.1 Failure Mode Matrix

| # | Failure Mode | Detection | Impact | Fallback Strategy | Recovery |
|---|---|---|---|---|---|
| **F1** | Weather API down | HTTP 5xx / timeout >10s | No data | Try fallback API (OpenWeatherMap). If both fail → use last cached data with "data may be outdated" disclaimer | Auto-retry next day |
| **F2** | Weather API returns partial data | Schema validation fails on required fields | Incomplete report | Fill missing fields with "data unavailable". If >3 critical fields missing → abort | Alert admin |
| **F3** | Gemini API timeout | Response >45s | No script | Retry once with shorter prompt. If fails again → use template-based report (fill-in-the-blank) | Auto-retry in 15 min |
| **F4** | LLM hallucination | Output contract validation fails | Inaccurate report | Regenerate with stricter prompt (include: "Use ONLY the provided numbers"). Max 2 retries → template fallback | Log for model tuning |
| **F5** | LLM generates unsafe content | Content filter / keyword scan | Inappropriate output | Reject and regenerate. After 2 failures → template fallback | Alert admin |
| **F6** | TTS API failure | HTTP error or silent audio | No audio | Retry once. Fallback to gTTS (lower quality but reliable). If all fail → deliver text-only | Auto-retry |
| **F7** | TTS character limit | Script >5000 chars/chunk | Truncated audio | Split into paragraph chunks, generate separately, concatenate with `pydub` | N/A (handled in code) |
| **F8** | Veo generation failure | API error or timeout >5 min | No video | Automatic fallback to MoviePy + Pillow title-card video | Log for review |
| **F9** | Veo low quality output | Resolution <720p or artifacts | Poor video | Accept with quality warning in metadata. If unwatchable → title-card fallback | N/A |
| **F10** | Drive upload failure | HTTP error / quota exceeded | Output not stored | Retry 3x. If quota → store locally and alert admin. Queue for upload when quota resets | Manual upload |
| **F11** | Network timeout (general) | Socket timeout >30s | Stage blocked | Per-stage retry with exponential backoff. Circuit breaker after 3 consecutive days of failure | Admin intervention |
| **F12** | Cloud Scheduler misfire | Pipeline not triggered | Missed report | Health check at 7:15 AM: if no run detected → auto-trigger via Cloud Monitoring alert | Self-healing |

### 7.2 Fallback Priority Chain

```
Weather Data:   Google Weather API → OpenWeatherMap → NWS API → Cached (last 24h)
Script:         Gemini (strict) → Gemini (template-guided) → Template fill-in
Audio:          Cloud TTS WaveNet → Cloud TTS Standard → gTTS
Video:          Veo → MoviePy + Pillow title card
Storage:        Google Drive → Local filesystem → Cloud Storage bucket
Notification:   Email → Slack → Cloud Logging (always)
```

### 7.3 Graceful Degradation Levels

| Level | Condition | Output |
|---|---|---|
| **L0: Full** | All services operational | Video + Audio + Script + Data JSON |
| **L1: No Video** | Veo unavailable | Title-card video + Audio + Script + Data JSON |
| **L2: No Audio** | TTS unavailable | Script + Data JSON (text only) |
| **L3: Template** | LLM unavailable | Template-generated script + Data JSON |
| **L4: Data Only** | LLM + TTS unavailable | Raw weather_data.json uploaded, alert sent |
| **L5: Failure** | Weather API + all fallbacks down | Alert sent. No report generated. Logged as missed day |

---

*End of Specification — v1.0*
