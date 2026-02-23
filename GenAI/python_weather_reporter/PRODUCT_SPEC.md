# Product Specification: AI Weather Reporter (Storrs)

## Daily Output Videos
Generated videos are archived on Google Drive:
**[google.com/drive → Storrs AI Weather Reporter](https://drive.google.com/drive/folders/1xDH0A_1ai49FuV9e8O05ecEJYm2UXf3m)**

---

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
| `video_service.py` | Builds the Veo 3.0 prompt and generates the video; manages Maya's reference image and UConn News logo |
| `validator.py` | Runs all validation checks before video generation |
| `sheets_service.py` | Google Sheets integration — OAuth2 helper to append weather data to a Drive spreadsheet |
| `.env` | Local secrets file (gitignored) — stores `GOOGLE_CLOUD_PROJECT` |

### Output Files (generated at runtime, gitignored)
| File | Description |
|------|-------------|
| `weather_report.csv` | Appended daily — stores fetched weather history |
| `weather_script.txt` | Latest generated spoken script |
| `maya_reference.jpg` | Maya's anchor reference image (auto-generated once via Imagen 3, reused for consistency) |
| `uconn_news_logo.png` | UConn News broadcast logo (auto-generated once via Imagen 3, reused for brand consistency) |
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
6. Validate          validator.py        →  5 checks (see below) — hard fails block video generation
7. Generate Video    video_service.py    →  Veo 3.0 → output_video.mp4 (up to 3 API retries)
8. Frame Validation  validator.py        →  Gemini Vision checks rendered frame — regenerates up to 3 times if INVALID
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

The UConn News logo (`uconn_news_logo.png`) is similarly auto-generated once via Imagen 3 and reused in every run for brand consistency — see [Overlay Graphics](#overlay-graphics).

---

## Studio Display

Each video shows a glass-textured side panel divided into **three explicit sections** (top to bottom):

```
TOP    — {temp}°C               (current temperature, large and bold)
MIDDLE — HIGH: {high}°C  LOW: {low}°C
BOTTOM — {WEATHER_LABEL}        (e.g. SUNNY, CLOUDY, LIGHT SNOW)
```

- Each section is distinct and contains **only its own content** — no cross-section duplication
- `HIGH` and `LOW` appear **exactly once** each, only in the MIDDLE section
- `TEMP:` label is never used — the bare temperature value is shown directly
- Weather label is mapped from the raw condition string (e.g. `"Overcast"` → `CLOUDY`, `"Light rain"` → `LIGHT RAIN`, `"Light snow, mist"` → `LIGHT SNOW`)
- The spoken script describes conditions in words only — no temperature numbers — since they are already visible on screen

---

## Overlay Graphics

### UConn News Logo (Top-Right)
The official `UConn News` broadcast logo is auto-generated via Imagen 3 on first run and reused every day:
- **Position**: Top-right corner, 80px padding from top and right edges
- **Size**: ~400px wide, original aspect ratio maintained
- **Style**: Bold white geometric sans-serif on deep navy blue background with subtle red accent
- **Constraints**: Static across all frames — no movement, no animation, no duplication, no color or text modification
- Logo is described in full detail in the Veo prompt and validated before every video generation

### Lower-Third Title Bar (Bottom)
A single full-width semi-transparent navy blue bar at the very bottom of the frame:
- Centered text: `Today's Weather Forecast` in bold white sans-serif (Helvetica Neue / Roboto Condensed style)
- No condition badges, extra boxes, floating labels, or duplicate title elements anywhere in the frame
- Appears **exactly once**

### Alert Banner (Extreme/Severe only)
When an active NWS Extreme or Severe alert is present, a single full-width solid red bar appears **directly below** (touching) the navy lower-third:
- Text: `WARNING: {ALERT EVENT} IN EFFECT` in bold white sans-serif — same font family as the title bar
- Appears **exactly once**, only when an active alert is present

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

All checks run before video generation. **Hard FAILs** block video generation; **Soft WARNs** are logged but do not block.

### 1. Script Validation (Hard — FAIL blocks video)
Uses **Gemini 2.0 Flash** to verify the spoken script:
- Written in English with no spelling or grammar errors
- Reflects the correct weather condition
- Any temperature numbers mentioned match actual data (current, high, or low)
- Tone is appropriate for a TV weather anchor
- No phrase or advisory is repeated twice within the script
- If an Extreme or Severe NWS alert is active: FAIL only if the alert is **completely absent** from the script

### 2. Prompt Validation (Hard — FAIL blocks video)
Manual + LLM checks on the Veo 3.0 prompt, organised into sections:

**Core checks:**
- Weather condition keywords present in prompt
- Maya's name and anchor role present
- Prompt specifies 4K resolution and 16:9 aspect ratio

**Three-section display card:**
- Three explicit sections (TOP / MIDDLE / BOTTOM) present
- TOP section contains only the current temperature — no HIGH/LOW
- MIDDLE section: `HIGH` and `LOW` each appear exactly once, values match weather data
- BOTTOM section: condition label only — no temperature values or extra labels
- `TEMP:` label must not appear anywhere (bare value shown directly)
- `HIGH:` / `LOW:` must not appear outside the display card block

**Lower-third layout (6-point check):**
- Navy blue full-width bar specified
- Explicit prohibition of condition badges, extra boxes, and floating labels
- `bold white sans-serif` typography specified
- `Today's Weather Forecast` appears exactly once
- `WARNING:` appears exactly once if alert active, zero times if no alert
- Alert bar positioned `directly below` the title bar (when applicable)

**Logo placement:**
- `UConn News` logo present in prompt, positioned in the top-right corner
- 80px padding and ~400px width specified
- Logo is static — prompt explicitly says do NOT move / resize / animate / duplicate
- Logo appears exactly once; no color changes or text modification stated

**Landmark / environment check:**
- UConn landmark keywords present for the given condition (Homer Babbidge Library, central green, etc.)
- For snowy conditions — active snowfall keyword present (`falling`, `drifting`, `swirling`, `snowflakes`, `blizzard rages`, or `curtains of snow`)

### 3. No-Repetition Check (Soft — WARN only)
Checks that temperature numbers shown on the studio display are not also spoken aloud in the script.

### 4. Character Consistency Check (Soft — WARN only)
Checks that `maya_reference.jpg` exists locally.

### 5. Logo Consistency Check (Soft — WARN only)
Checks that `uconn_news_logo.png` exists locally. If missing, it will be auto-generated on the next video run via Imagen 3.

---

## Post-Generation Frame Validation

After each video is generated, `validate_video_frame()` extracts a frame at 4 seconds via `ffmpeg` and sends it to **Gemini Vision** for strict visual inspection. This catches Veo rendering hallucinations (garbled text, wrong labels, phantom characters) that prompt-level checks cannot detect because they only inspect the instructions, not the actual rendered output.

**Rules passed to Gemini Vision are zero-tolerance:**
- No reinterpretation allowed — validate only against explicit expected values
- If unsure about any element, return INVALID
- Checks: current temp (no HIGH/LOW label), HIGH/LOW values, `UConn News` logo text, `Today's Weather Forecast` lower-third, alert banner text (if active)

If the frame is INVALID, `main.py` regenerates the video (up to **3 visual retries** — separate from the 3 Veo API retries). If all retries fail, the pipeline logs a warning and exits.

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

### Known Failure Modes

#### RAI (Responsible AI) Filtering
Veo 3.0 runs every generation request through Google's **Responsible AI (RAI)** safety system — an automated content moderation layer that screens prompts and generated videos against Google's usage policies. If the content is flagged, the operation returns `done=True` with `rai_media_filtered_count=1` and no video.

Common triggers observed in this pipeline:
- Active NWS Extreme/Severe alert overlay (e.g. `"WARNING: BLIZZARD WARNING IN EFFECT"`) combined with dramatic weather language
- The RAI filter is non-deterministic — the same prompt may pass on one run and be blocked on another

If blocked, try:
1. Waiting and retrying (RAI decisions can vary by time of day)
2. Retrying once the active weather alert has lifted
3. Submitting feedback to Google via the support code in the response (`rai_media_filtered_reasons`)

#### GCP Capacity
`veo-3.0-generate-preview` is a limited-capacity preview model. At peak times, the operation may return `done=True` with an empty response and no video (and no RAI reason given). This is a quota/capacity constraint on Google's infrastructure — not a code issue. Options to resolve:
1. Retry during off-peak hours (late night / early morning EST)
2. Change the generation location from `us-central1` to another region (e.g. `us-east4`, `europe-west4`) — capacity availability varies by region

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
