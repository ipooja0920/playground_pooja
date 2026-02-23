# Product Specification: AI Weather Reporter (Storrs)

## Overview
A Python-based AI pipeline that fetches live weather data for Storrs, CT, stores it locally, generates an 8-second spoken weather report script, and produces a professional broadcast-style video featuring a consistent AI anchor (Maya) using Vertex AI Veo 3.0. The video is generated only after all validation tests pass.

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| **Language** | Python 3 |
| **Weather Data** | [wttr.in](https://wttr.in) (free JSON API, no key required) |
| **Weather Alerts** | [NWS API](https://api.weather.gov) (free, no key — `alerts/active?point={lat},{lon}`) |
| **Local Storage** | CSV file (`weather_report.csv`) via `pandas` |
| **Script Generation** | Vertex AI — Gemini 2.0 Flash |
| **Script Validation** | Vertex AI — Gemini 2.0 Flash (LLM-assisted) |
| **Video Generation** | Vertex AI — Veo 3.0 (`veo-3.0-generate-preview`) |
| **Anchor Image** | Vertex AI — Imagen 3 (`imagen-3.0-generate-001`) |
| **GCP Auth** | Application Default Credentials — project ID loaded from `.env` |

---

## Project Files

| File | Purpose |
|------|---------|
| `main.py` | Pipeline entry point — loads `.env`, orchestrates all steps in order |
| `weather_service.py` | Fetches weather from wttr.in + live NWS alerts for Storrs, CT |
| `sync_weather.py` | Appends weather data to local `weather_report.csv` |
| `script_service.py` | Generates 8-second script via Gemini 2.0 Flash; reads/writes CSV and `.txt` |
| `video_service.py` | Builds the Veo 3.0 prompt and generates the video; manages Maya's reference image |
| `validator.py` | Runs all validation checks before video generation |
| `sheets_service.py` | Google Sheets integration — OAuth2 helper to append weather data to a Drive spreadsheet |
| `.env` | Local secrets file (gitignored) — stores `GOOGLE_CLOUD_PROJECT` |

### Output Files (generated at runtime, gitignored)
| File | Description |
|------|-------------|
| `weather_report.csv` | Appended daily — stores fetched weather history |
| `weather_script.txt` | Latest generated spoken script |
| `maya_reference.jpg` | Maya's anchor reference image (auto-generated once, reused for consistency) |
| `output_video.mp4` | Final generated video (if all tests pass) |

---

## Pipeline Data Flow

```
1. Fetch Weather     weather_service.py  →  wttr.in (condition, temp, feels-like, high, low)
                                         →  NWS API (active alerts — blizzard, winter storm, etc.)
2. Store Locally     sync_weather.py     →  weather_report.csv (append row)
3. Read Today's Data script_service.py   →  reads latest row from CSV + live NWS alert
4. Generate Script   script_service.py   →  Gemini 2.0 Flash → weather_script.txt
5. Build Video Prompt video_service.py   →  constructs Veo 3.0 prompt with display data + alert overlay
6. Validate          validator.py        →  4 checks (see below) — hard fails block video generation
7. Generate Video    video_service.py    →  Veo 3.0 → output_video.mp4 (up to 3 retries)
```

---

## Weather Data Fields

| Field | Source | Description |
|-------|--------|-------------|
| `condition` | wttr.in | Raw condition string (e.g. `"Light snow, mist"`, `"Blizzard"`) |
| `temp_c` | wttr.in | Current temperature in °C |
| `feels_like_c` | wttr.in | Feels-like temperature in °C |
| `high_c` | wttr.in | Today's forecast high in °C |
| `low_c` | wttr.in | Today's forecast low in °C |
| `alert` | NWS API | Most severe active alert dict (`event`, `headline`, `severity`) or `None` |

NWS alert severity ranking: **Extreme > Severe > Moderate > Minor**. Only Extreme and Severe alerts affect the video (red banner overlay) and script (must lead with alert).

---

## Anchor Character: Maya

Maya's appearance is locked via a constant `ANCHOR_CHARACTER` string in `video_service.py` and reused in every run:
- Female broadcast news anchor, mid-30s
- Shoulder-length chestnut brown hair, sharp green eyes, warm fair complexion
- Tailored royal blue blazer over a white silk shirt and matching pencil skirt

A reference image (`maya_reference.jpg`) is auto-generated via Imagen 3 on first run and reused to maintain visual consistency across daily videos.

---

## Studio Display

Each video shows a side panel with weather data displayed as:
```
TEMP: {temp}°C  |  HIGH: {high}°C  |  LOW: {low}°C  |  {WEATHER_LABEL}
```
- Each label (`TEMP`, `HIGH`, `LOW`) appears **exactly once** (validated case-insensitively)
- Weather label is mapped from the raw condition string (e.g. `"Overcast"` → `CLOUDY`, `"Light rain"` → `LIGHT RAIN`, `"Light snow, mist"` → `LIGHT SNOW`)
- The spoken script describes conditions in words only — no temperature numbers — since they are already visible on screen

---

## Overlay Graphics
- **Top-right**: `UConn News` logo badge with a UConn Husky mascot icon (white husky dog head silhouette) in bold white on navy blue rounded rectangle
- **Bottom**: Lower-third title card reading `Today's Weather Forecast` in white on semi-transparent navy bar
- **Alert banner** (Extreme/Severe only): Flashing red bar directly below the lower-third reading `WARNING: {ALERT EVENT} IN EFFECT` in bold white on solid red, full-width

---

## Studio Background

The background is dynamically matched to the weather condition. For snowy conditions, the window view must show **active snowfall** (not just settled snow):

| Condition | Background |
|-----------|-----------|
| Sunny / Clear | Golden sunlight over UConn campus, Homer Babbidge Library visible |
| Overcast / Cloudy | Grey sky over UConn central green and Georgian brick buildings |
| Heavy Rain | Rain streaking studio windows, UConn green visible through downpour |
| Light Rain / Drizzle | Soft drizzle, misty UConn pathways and Wilbur Cross Building |
| **Blizzard / Heavy Snow** | Full whiteout — thick curtains of snow **actively swirling** past glass, Homer Babbidge Library barely visible; harsh white studio lighting |
| **Light / Patchy Snow** | Light snowflakes **drifting and falling** gently past windows, campus lightly frosted; quiet wintry feel |
| **Moderate Snow** | Snowflakes **actively falling**, campus blanketed in fresh snow; flat white sky |
| Fog / Mist | Misty silhouette of campus buildings and tall oaks |
| Thunderstorm | Stormy sky, lightning, deep blue-grey studio lighting |
| Other | Neutral campus view, professional broadcast lighting |

---

## Validation Tests

All 4 checks run before video generation. **Hard FAILs** block video generation.

### 1. Script Validation (Hard — FAIL blocks video)
Uses **Gemini 2.0 Flash** to verify the spoken script:
- Written in English with no spelling or grammar errors
- Reflects the correct weather condition
- Any temperature numbers mentioned match actual data (current, high, or low)
- Tone is appropriate for a TV weather anchor
- No phrase or advisory is repeated twice within the script
- If an Extreme or Severe NWS alert is active: FAIL only if the alert is **completely absent** from the script

### 2. Prompt Validation (Hard — FAIL blocks video)
Manual + LLM checks on the Veo 3.0 prompt:
- **Manual**: Weather condition keywords present in prompt
- **Manual**: Maya's name and anchor role present
- **Manual**: Display labels `TEMP`, `HIGH`, `LOW` each appear **exactly once** (case-insensitive, colon-scoped)
- **Manual**: No bare `TEMP`/`HIGH`/`LOW` labels outside the display data section
- **Manual**: UConn Husky mascot referenced in logo badge
- **Manual**: UConn landmark keywords present for the given condition
- **Manual**: `UConn News` overlay and `Today's Weather Forecast` title card present
- **Manual**: For snowy conditions — active snowfall keyword present (`falling`, `drifting`, `swirling`, `snowflakes`, `blizzard rages`, or `curtains of snow`)
- **LLM (Gemini 2.0 Flash)**: Checks for misspellings in visual text sections only

### 3. No-Repetition Check (Soft — WARN only)
Checks that temperature numbers shown on the studio display are not also spoken aloud in the script.

### 4. Character Consistency Check (Soft — WARN only)
Checks that `maya_reference.jpg` exists locally.

---

## Script Rules
- Opens with a time-appropriate greeting: `"Good [morning/afternoon/evening], Storrs!"`
- If Extreme/Severe NWS alert active: **must lead with or urgently mention** the alert
- Describes condition vividly using words, not temperature numbers
- Ends with a single punchy, weather-relevant call to action (no repetition)
- Strictly 15–20 words (~8 seconds when spoken)
- Plain text only — no stage directions, labels, or quotes

---

## Video Generation
- **Model**: Veo 3.0 (`veo-3.0-generate-preview`) — controlled by `VEO_MODEL` constant
- **Format**: 16:9, 4K, 8 seconds, 1 video
- **Retries**: Up to 3 attempts before failure; full operation state logged on empty response
- **Person generation**: `allow_adult`
- Output saved to `output_video.mp4` locally (or GCS URI if Veo returns a cloud path)

---

## Configuration

### `.env` File (gitignored)
Place a `.env` file in the project directory — `main.py` loads it automatically on startup:
```
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
```
No need to `export` manually each session.

### One-time GCP Setup
```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project your-gcp-project-id
```
