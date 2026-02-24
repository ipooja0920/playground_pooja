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

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     External Data Sources                    │
│          wttr.in (weather JSON)    NWS API (alerts)          │
└────────────────────┬─────────────────────┬───────────────────┘
                     │                     │
                     ▼                     ▼
             ┌───────────────────────────────────┐
             │         weather_service.py         │
             │  condition, temp, feels-like,      │
             │  high, low, booleans, alert        │
             └──────────┬────────────────┬────────┘
                        │                │
              ┌─────────▼──────┐  ┌──────▼──────────────┐
              │ sync_weather   │  │  script_service.py   │
              │   .py          │  │  reads CSV + alert   │
              │ → CSV storage  │  │  Gemini 2.0 Flash    │
              └────────────────┘  │  → 15–20 word script │
                                  └──────────┬───────────┘
                                             │ script_text
                                             ▼
                                  ┌──────────────────────┐
                                  │   video_service.py   │
                                  │  build Veo 3.0 prompt│
                                  │  Imagen 3 → maya_    │
                                  │  reference.jpg       │
                                  └──────────┬───────────┘
                                             │ prompt
                                             ▼
                                  ┌──────────────────────┐
                                  │    validator.py      │
                                  │  4 pre-gen checks    │
                                  │  (Hard FAIL blocks)  │
                                  └──────────┬───────────┘
                                             │ PASS
                                             ▼
                                  ┌──────────────────────┐
                                  │   video_service.py   │
                                  │  Veo 3.0 generate    │
                                  │  → output_video.mp4  │
                                  └──────────┬───────────┘
                                             │ video
                                             ▼
                                  ┌──────────────────────┐
                                  │    validator.py      │
                                  │  Frame check         │
                                  │  Gemini Vision →     │
                                  │  verify no text      │
                                  │  overlays in frame   │
                                  └──────────┬───────────┘
                                             │ PASS
                                             ▼
                                  ┌──────────────────────┐
                                  │   compositor.py      │
                                  │  Pillow renders card │
                                  │  moviepy composites  │
                                  │  → final_video.mp4   │
                                  └──────────────────────┘
```

**Key design decisions:**
- All AI calls go through Vertex AI — Gemini 2.0 Flash for script generation and text-based validation, Imagen 3 for the Maya reference image, Veo 3.0 for video
- Validation is split: rule-based Python checks run before generation (fast, deterministic), Gemini Vision OCR runs after (catches what prompt instructions cannot guarantee)
- The anchor's visual identity is locked via a text constant (`ANCHOR_CHARACTER`) seeded into both the Imagen reference generation and the Veo prompt — not via pixel-level image compositing
- Weather data is written to CSV before any generation so the pipeline can be re-run independently at any step
- Text overlays (temperature, condition label) are composited in post-production using Pillow + moviepy — never baked into the Veo prompt, following broadcast industry practice (chyrons and lower-thirds are always separate layers)

---

## Project Files

| File | Purpose |
|------|---------|
| `main.py` | Pipeline entry point — loads `.env`, orchestrates all steps in order |
| `weather_service.py` | Fetches weather from wttr.in + live NWS alerts for Storrs, CT |
| `sync_weather.py` | Appends weather data to local `weather_report.csv` |
| `script_service.py` | Generates 8-second script via Gemini 2.0 Flash; reads/writes CSV and `.txt` |
| `video_service.py` | Builds the Veo 3.0 prompt and generates the video; manages Maya's reference image |
| `validator.py` | Runs all validation checks before and after video generation |
| `compositor.py` | Post-production step — renders the 4-row weather display card and UConn NEWS channel logo using Pillow, then composites both onto the clean Veo video using moviepy |
| `sheets_service.py` | Google Sheets integration — OAuth2 helper to append weather data to a Drive spreadsheet |
| `.env` | Local secrets file (gitignored) — stores `GOOGLE_CLOUD_PROJECT` |

### Output Files (generated at runtime, gitignored)
| File | Description |
|------|-------------|
| `weather_report.csv` | Appended daily — stores fetched weather history |
| `weather_script.txt` | Latest generated spoken script |
| `maya_reference.jpg` | Maya's anchor reference image (auto-generated once via Imagen 3, reused for consistency) |
| `output_video.mp4` | Raw Veo output — clean video of Maya with no text overlays |
| `final_video.mp4` | Final broadcast-ready video with composited weather display card |

---

## Pipeline Data Flow

```
1. Fetch Weather     weather_service.py  →  wttr.in (condition, temp, feels-like, high, low)
                                         →  NWS API (active alerts — blizzard, winter storm, etc.)
2. Store Locally     sync_weather.py     →  weather_report.csv (append row)
3. Read Today's Data script_service.py   →  reads latest row from CSV + live NWS alert
4. Generate Script   script_service.py   →  Gemini 2.0 Flash → weather_script.txt
5. Build Video Prompt video_service.py   →  constructs clean Veo 3.0 prompt (no text overlays)
6. Validate          validator.py        →  3 checks (see below) — hard fails block video generation
7. Generate Video    video_service.py    →  Veo 3.0 → output_video.mp4 (up to 3 API retries)
8. Frame Validation  validator.py        →  Gemini Vision checks frame for any text overlay — regenerates up to 3 times if text found
9. Composite Overlay compositor.py       →  Pillow renders display card; moviepy composites → final_video.mp4
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
| `is_sunny` | wttr.in | `True` if condition contains "sunny" or "clear" |
| `is_rainy` | wttr.in | `True` if condition contains "rain" or "drizzle" |
| `is_stormy` | wttr.in | `True` if condition contains "thunder" or "storm" |
| `is_snowy` | wttr.in | `True` if condition contains "snow" or "blizzard" |
| `is_cloudy` | wttr.in | `True` if condition contains "cloud" or "overcast" |
| `is_foggy` | wttr.in | `True` if condition contains "fog" or "mist" |
| `is_hazy` | wttr.in | `True` if condition contains "haze" or "hazy" |
| `is_icy` | wttr.in | `True` if condition contains "ice", "freezing", "sleet", "frost", or "precipitation" |
| `is_windy` | wttr.in | `True` if condition contains "wind", "breezy", or "gust" |
| `alert` | NWS API | Most severe active alert dict (`event`, `headline`, `severity`) or `None` |

NWS alert severity ranking: **Extreme > Severe > Moderate > Minor**. Only Extreme and Severe alerts affect the script (must lead with or urgently mention the alert) — no visual overlay is added to the video.

---

## Anchor Character: Maya

Maya's appearance is locked via a constant `ANCHOR_CHARACTER` string in `video_service.py` and reused in every run:
- Female broadcast news anchor, mid-30s
- Shoulder-length chestnut brown hair, sharp green eyes, warm fair complexion
- Tailored royal blue blazer over a white silk shirt and matching pencil skirt

A reference image (`maya_reference.jpg`) is auto-generated via Imagen 3 on first run and reused to maintain visual consistency across daily videos.

In the Veo prompt, Maya is positioned **slightly to the right of frame center** (screen right, from the viewer's perspective), looking directly into the camera — leaving the left side open for the weather display card.

---

## Display Card (Post-Production Composite)

After Veo generates the clean Maya video, `compositor.py` renders a **weather display card** and composites it onto the upper-left area of the frame using Pillow (card rendering) and moviepy (video compositing). The result is saved as `final_video.mp4`.

Card layout — four rows:

```
┌────────────────────┐
│      -2°C          │  ← current temperature, large bold white
│ ─────────────────  │  ← horizontal divider
│  HIGH: 0°C         │  ← today's forecast high, smaller blue-white
│  LOW:  -5°C        │  ← today's forecast low, smaller blue-white
│  SUNNY             │  ← condition label, smaller blue-white (omitted when unknown)
└────────────────────┘
```

- **Background**: dark navy (`#08122A`), ~84% opacity, rounded corners
- **Position**: upper-left area (`6%` from left, `14%` from top), sized proportionally to video dimensions (`26%` width × `62%` height)
- **Temperature**: always the raw `temp_c` value with `°C` suffix, displayed in large bold white
- **High / Low**: `high_c` and `low_c` from the weather data, displayed as `HIGH: X°C` / `LOW: X°C`
- **Condition label**: mapped from the raw condition string via `_get_weather_label()` (e.g. `"Overcast"` → `CLOUDY`, `"Light rain"` → `LIGHT RAIN`, `"Light snow, mist"` → `LIGHT SNOW`); the row is omitted entirely when the condition is `"unknown"`
- Label is auto-truncated with `…` if it would overflow the card width
- The Veo prompt explicitly tells the model **not** to render any text overlays — the display card is always a post-production layer, never baked into the AI-generated footage

---

## Channel Logo (Post-Production Composite)

`compositor.py` also renders a **UConn NEWS channel logo** and composites it into the top-right corner of every frame.

Logo layout:

```
┌─────────────────────┬───┐
│       UConn         │   │  ← navy blue background, white bold text
│       NEWS          │   │  ← red vertical stripe on right edge
└─────────────────────┴───┘
```

- **Background**: UConn navy blue (`#003865`), near-opaque
- **Red stripe**: right-edge vertical stripe (~12% of logo width), UConn red (`#C8102E`)
- **Position**: top-right corner with a `2%` margin from both the right and top edges
- **Size**: `12%` of video width × `10%` of video height

---

## Studio Background

**Base view (always present):** The studio's floor-to-ceiling windows look out directly onto **Wilbur Cross Building** — UConn's landmark red-brick Georgian building with arched windows, a pitched slate roof, and tall oaks lining the path in front. This is the fixed backdrop in every broadcast.

The base lighting shifts automatically based on the **time of day** when the pipeline runs:

| Time of Day | Base Lighting |
|-------------|--------------|
| Daytime (default) | Neutral sky behind Wilbur Cross; standard broadcast lighting |
| **Evening (5:00 pm – 7:30 pm)** | Warm amber-orange twilight deepening behind the building; campus path lights flickering on along the oak-lined walkways |
| **Night (8:00 pm – 11:00 pm)** | Fully dark outside; Wilbur Cross lit by exterior floodlights against a deep navy sky; warm amber campus lanterns glowing; studio interior bright against the dark glass |

Weather-specific **effects** are then layered on top of the active base to match today's conditions:

| Condition | Effect on the Wilbur Cross view |
|-----------|--------------------------------|
| Sunny / Clear | Warm golden sunlight floods through the glass; sharp shadows on the brick facade; blue skies behind |
| Overcast / Cloudy | Flat grey cloud cover over the building; diffused cool studio lighting; no shadows |
| Light Rain / Drizzle | Soft drizzle beads and trickles down the glass; tree-lined paths glistening; cool blue-grey lighting |
| Heavy Rain | Steady rain streams and rivulets run down the glass; Wilbur Cross visible through downpour; wet-pavement reflections |
| Thunderstorm | Sheets of water on the glass; lightning flashes illuminate the building; deep moody blue-grey lighting |
| **Light / Patchy Snow** | Snowflakes **drifting and falling** gently past the glass; dusting on ledges and oak branches; soft grey winter sky |
| **Moderate Snow** | Snowflakes **actively falling** past the glass; building blanketed; flat white sky; cool soft-white lighting |
| **Blizzard / Heavy Snow** | Thick curtains of snow **swirling** past the glass in near-whiteout; snow on ledges; bare oaks bending; harsh cold white lighting |
| Fog / Mist | Wilbur Cross visible only as a soft silhouette through the haze on the glass; diffused white-grey lighting |
| Icy / Wintry Mix | Freezing precipitation ticking on the glass; frost and ice on the building; glazed oak branches; bleak grey sky |
| Other | Clear view of Wilbur Cross under a neutral sky; professional broadcast lighting |

---

## Validation Tests

Pre-generation checks (1–3) run before video is created. **Hard FAILs** block video generation; **Soft WARNs** are logged but do not block. Post-generation check (4) runs after each video and triggers a visual retry if it fails.

### 1. Script Validation (Hard — FAIL blocks video)
Uses **Gemini 2.0 Flash** to verify the spoken script:
- Written in English with no spelling or grammar errors
- Reflects the correct weather condition
- Any temperature numbers mentioned match actual data (current, high, or low)
- Tone is appropriate for a TV weather anchor
- No phrase or advisory is repeated twice within the script
- If an Extreme or Severe NWS alert is active: FAIL only if the alert is **completely absent** from the script

### 2. Prompt Validation (Hard — FAIL blocks video)
Rule-based checks on the Veo 3.0 prompt:

**Core checks:**
- Weather condition keywords present in prompt
- Maya's name and anchor role present
- Prompt specifies 4K resolution and 16:9 aspect ratio

**No-text enforcement:**
- Prompt must **not** contain display card instructions (`TOP SECTION`, `BOTTOM SECTION`, `TEMP:` label)
- Prompt must include an explicit no-text directive (one of: `"no text overlays"`, `"no on-screen graphics"`, `"no chyrons"`, `"no display panels"`)

**Landmark / environment check:**
- UConn landmark keywords present for the given condition (Homer Babbidge Library, central green, etc.)
- For snowy conditions — active snowfall keyword present (`falling`, `drifting`, `swirling`, `snowflakes`, `blizzard rages`, or `curtains of snow`)

### 3. Character Consistency Check (Soft — WARN only)
Checks that `maya_reference.jpg` exists locally.

### 4. Frame Validation (Post-gen — FAIL triggers visual retry)
After each video is generated, `validate_video_frame()` extracts a frame at 4 seconds via `ffmpeg` and sends it to **Gemini Vision**. The model is asked whether any on-screen text is visible (temperature values, chyrons, lower-thirds, display cards, or any graphic overlay). Since Veo is explicitly told to render no text, any text detected is a Veo hallucination.

- Returns **PASS** if Gemini responds `"NO TEXT"` — frame is clean
- Returns **FAIL** if Gemini responds `"TEXT FOUND: <description>"` — triggers a visual retry

If the frame check fails, `main.py` regenerates the video (up to **3 visual retries** — separate from the 3 Veo API retries).

If all visual retries fail, the pipeline logs a warning and exits without compositing.

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
- Dramatic wintry weather language (blizzard, whiteout, dangerous conditions) combined with active NWS alert content in the script
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

---

## Limitations

### 1. GCP Capacity Constraints
`veo-3.0-generate-preview` is a limited-capacity preview model hosted on Google Cloud. At peak times, generation requests can return `done=True` with an empty response and no video — no error code, no RAI reason. This is a quota constraint on Google's infrastructure, not a code bug, and cannot be resolved from the application side.

**Recommended approach:** Change the generation region from `us-central1` to another supported region (e.g. `us-east4`, `europe-west4`) — capacity availability varies by region and time of day. Alternatively, retry during off-peak hours (late night / early morning EST).

---

### 2. RAI (Responsible AI) Filtering
Veo 3.0 applies Google's Responsible AI safety filter to every generation request. The filter is **non-deterministic** — the same prompt can pass on one run and be blocked on another, even without any content changes. When blocked, the operation returns `rai_media_filtered_count=1` with a support code but no video.

Observed in this pipeline: dramatic wintry language (blizzard, whiteout, dangerous conditions) combined with active NWS alert content in the script can trigger the filter.

**Recommended approach:** Wait and retry — RAI decisions vary by time of day. If a specific NWS alert is active and consistently causing blocks, retry once the alert has lifted. Report persistent false positives to Google using the support code from the response (`rai_media_filtered_reasons`).

---

### 3. Text and Logo Fidelity in Veo 3.0
Veo 3.0, like most video generation models, is not designed to faithfully reproduce specific text strings, logos, or brand assets. It interprets visual and textual descriptions rather than rendering them with pixel-level precision. In practice this means:
- Temperature values on the display card may be garbled, substituted with letters, or rendered inconsistently across frames
- Brand logos described in the prompt are "hallucinated" by the model — the output is an artistic interpretation, not an accurate reproduction
- Text that looks correct in one generation attempt may differ in the next

The pipeline's frame validation step (Gemini Vision OCR on the rendered video) catches temperature rendering errors and triggers a visual retry. However, the underlying limitation is a model constraint, not a prompt or validation issue.

**Recommended approach:** Treat text overlays and branded graphics as a **post-production layer** — not something to fight the AI over. This is how professional broadcast studios work: chyrons, lower-thirds, and graphics are always composited as separate layers on top of the video, never baked into the live-action footage. For production use, generate the clean Maya video with Veo, then composite temperature, condition label, and any branding using a video editing library (e.g. `moviepy`, `ffmpeg`, Adobe After Effects) as a separate step after generation.
