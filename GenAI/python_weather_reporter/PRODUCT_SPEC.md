# Product Specification: AI Weather Reporter (Storrs)

## Overview
A Python-based AI pipeline that fetches live weather data for Storrs, CT, stores it locally, generates an 8-second spoken weather report script, and produces a professional broadcast-style video featuring a consistent AI anchor (Maya) using Vertex AI Veo 3.0. The video is generated only after all validation tests pass.

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| **Language** | Python 3 |
| **Weather Data** | [wttr.in](https://wttr.in) (free JSON API, no key required) |
| **Local Storage** | CSV file (`weather_report.csv`) via `pandas` |
| **Script Generation** | Vertex AI — Gemini 2.0 Flash |
| **Script Validation** | Vertex AI — Gemini 2.0 Flash (LLM-assisted) |
| **Video Generation** | Vertex AI — Veo 3.0 (`veo-3.0-generate-preview`) |
| **Anchor Image** | Vertex AI — Imagen 3 (`imagen-3.0-generate-001`) |
| **GCP Auth** | Application Default Credentials (`GOOGLE_CLOUD_PROJECT` env var) |

---

## Project Files

| File | Purpose |
|------|---------|
| `main.py` | Pipeline entry point — orchestrates all steps in order |
| `weather_service.py` | Fetches weather data from wttr.in for Storrs, CT |
| `sync_weather.py` | Appends weather data to local `weather_report.csv` |
| `script_service.py` | Generates 8-second script via Gemini 2.0 Flash; reads/writes CSV and `.txt` |
| `video_service.py` | Builds the Veo 3.0 prompt and generates the video; manages Maya's reference image |
| `validator.py` | Runs all validation checks before video generation |
| `sheets_service.py` | Unused — legacy file from earlier iteration |

### Output Files (generated at runtime)
| File | Description |
|------|-------------|
| `weather_report.csv` | Appended daily — stores fetched weather history |
| `weather_script.txt` | Latest generated spoken script |
| `maya_reference.jpg` | Maya's anchor reference image (auto-generated once, reused for consistency) |
| `output_video.mp4` | Final generated video (if all tests pass) |

---

## Pipeline Data Flow

```
1. Fetch Weather     weather_service.py  →  wttr.in (condition, temp, high, low)
2. Store Locally     sync_weather.py     →  weather_report.csv (append row)
3. Read Today's Data script_service.py   →  reads latest row from CSV
4. Generate Script   script_service.py   →  Gemini 2.0 Flash → weather_script.txt
5. Build Video Prompt video_service.py   →  constructs Veo 3.0 prompt with display data
6. Validate          validator.py        →  4 checks (see below) — blocks if any FAIL
7. Generate Video    video_service.py    →  Veo 3.0 → output_video.mp4 (up to 3 retries)
```

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
- Each label (`TEMP`, `HIGH`, `LOW`) appears **exactly once**
- Weather label is mapped from the raw condition string (e.g. `"Overcast"` → `CLOUDY`, `"Light rain"` → `LIGHT RAIN`)
- The spoken script describes conditions in words only — no temperature numbers — since they are already visible on screen

---

## Overlay Graphics
- **Top-right**: `UConn News` logo badge in bold white on navy blue
- **Bottom**: Lower-third title card reading `Today's Weather Forecast` in white on semi-transparent navy bar

---

## Studio Background

The background is dynamically matched to the weather condition:

| Condition | Background |
|-----------|-----------|
| Sunny / Clear | Golden sunlight over UConn campus, Homer Babbidge Library visible |
| Overcast / Cloudy | Grey sky over UConn central green and Georgian brick buildings |
| Rain / Drizzle / Heavy Rain | Rain streaking studio windows, UConn green visible through downpour |
| Snow / Blizzard | Snow-covered campus, bare oaks, Homer Babbidge Library |
| Fog / Mist | Misty silhouette of campus buildings and tall oaks |
| Thunderstorm | Stormy sky, lightning, deep blue-grey studio lighting |
| Other | Neutral campus view, professional broadcast lighting |

---

## Validation Tests

All 4 checks run before video generation. A **hard FAIL** on any of the first two blocks video generation.

### 1. Script Validation (Hard — FAIL blocks video)
Uses **Gemini 2.0 Flash** to verify the spoken script:
- Written in English with no spelling or grammar errors
- Reflects the correct weather condition
- Any temperature numbers mentioned match actual data (current, high, or low)
- Tone is appropriate for a TV weather anchor (energetic and casual is acceptable)
- No phrase or advisory is repeated twice within the script

### 2. Prompt Validation (Hard — FAIL blocks video)
Manual + LLM checks on the Veo 3.0 prompt:
- **Manual**: Weather condition keywords present in prompt (e.g. `rain`, `snow`, `sunny`)
- **Manual**: Maya's name and anchor/reporter role present
- **Manual**: Display labels `TEMP`, `HIGH`, `LOW` each appear **exactly once** in the display data section (case-insensitive, scoped to the display string only)
- **Manual**: UConn landmark keywords present for the given condition
- **Manual**: `UConn News` overlay and `Today's Weather Forecast` title card present
- **LLM (Gemini 2.0 Flash)**: Checks for misspellings of key weather/broadcast terms only

### 3. No-Repetition Check (Soft — WARN only, does not block video)
Checks that temperature numbers shown on the studio display are not also spoken aloud in the script (viewer would simultaneously see and hear the same number).

### 4. Character Consistency Check (Soft — WARN only, does not block video)
Checks that `maya_reference.jpg` exists locally. If missing, it will be auto-generated on the next run; consistency cannot be guaranteed for that run.

---

## Script Rules
- Opens with a time-appropriate greeting: `"Good [morning/afternoon/evening], Storrs!"`
- Describes condition vividly using words, not temperature numbers
- Ends with a single punchy, weather-relevant call to action (no repetition)
- Strictly 15–20 words (~8 seconds when spoken)
- Plain text only — no stage directions, labels, or quotes

---

## Video Generation
- **Model**: Veo 3.0 (`veo-3.0-generate-preview`)
- **Format**: 16:9, 4K, 8 seconds, 1 video
- **Retries**: Up to 3 attempts before failure
- **Person generation**: `allow_adult`
- Output saved to `output_video.mp4` locally
