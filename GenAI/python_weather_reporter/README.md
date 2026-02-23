# AI Weather Reporter for Storrs, CT

An AI pipeline that fetches live weather + NWS alerts for Storrs, CT, generates an 8-second anchor script, validates it, and produces a broadcast-style video featuring Maya — a consistent AI anchor — using Vertex AI Veo 3.0.

---

## 📺 Watch the Daily Forecast

Every day, Maya delivers the Storrs weather — live NWS alerts, campus backdrop, and all.
**[View daily output videos on Google Drive →](https://drive.google.com/drive/folders/1xDH0A_1ai49FuV9e8O05ecEJYm2UXf3m)**

---

## Setup

### 1. Google Cloud Credentials
- Enable **Vertex AI API** in your Google Cloud Console.
- Authenticate with Application Default Credentials:
  ```bash
  gcloud auth application-default login
  gcloud auth application-default set-quota-project your-gcp-project-id
  ```

### 2. Create a `.env` file
In the project directory, create a `.env` file (it's gitignored — never committed):
```
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
```
`main.py` loads this automatically on startup — no manual `export` needed each session.

### 3. Install Dependencies
```bash
pip install requests pandas google-cloud-aiplatform google-genai
```

### 4. Run the Pipeline
```bash
cd GenAI/python_weather_reporter
python main.py
```

---

## How It Works

1. **Weather Fetch** (`weather_service.py`) — Calls [wttr.in](https://wttr.in) for live conditions (temp, feels-like, high, low) in Storrs, CT. Also fetches the most severe active alert from the [NWS API](https://api.weather.gov) (e.g. Blizzard Warning, Winter Storm Watch). No API keys required for either.
2. **Store Locally** (`sync_weather.py`) — Appends weather data to `weather_report.csv`.
3. **Generate Script** (`script_service.py`) — Gemini 2.0 Flash generates a 15–20 word (~8s) spoken script for anchor Maya. If an Extreme or Severe NWS alert is active, the script must open with or urgently mention it. Saves to `weather_script.txt`.
4. **Validate** (`validator.py`) — Runs 4 checks before video generation (see below).
5. **Generate Video** (`video_service.py`) — If all hard checks pass, Veo 3.0 generates an 8-second 16:9 4K video. Saved locally as `output_video.mp4`. Up to 3 retry attempts.

---

## Validation Suite

| Check | Type | What It Verifies |
|-------|------|-----------------|
| **Script Validation** | Hard FAIL | Script is in English, no spelling errors, reflects correct weather, no repeated phrases; Extreme/Severe alert must appear in script |
| **Prompt Validation** | Hard FAIL | `TEMP`/`HIGH`/`LOW` each appear exactly once; correct weather condition + UConn landmarks in background; UConn Husky in logo; active snowfall keyword for snowy conditions; overlay graphics present; no misspellings in visual text |
| **No-Repetition Check** | Soft WARN | Temperature numbers not spoken aloud if already visible on the studio display |
| **Character Consistency** | Soft WARN | `maya_reference.jpg` exists for visual consistency across runs |

Video is only generated if all **Hard** checks pass.

---

## Key Features

- **NWS Alert overlay**: When a Blizzard Warning or other Extreme/Severe alert is active, a flashing red banner appears below the lower-third: `WARNING: {ALERT} IN EFFECT`
- **Snow condition differentiation**: Three distinct snowy backgrounds — blizzard/whiteout, light/patchy snow drifting, moderate snow actively falling
- **UConn branding**: Homer Babbidge Library and campus landmarks in background; `UConn News` logo with Husky mascot top-right; `Today's Weather Forecast` lower-third
- **Feels-like temperature**: Included in the script prompt so Gemini can describe how it actually feels outside

---

## Output Files

All output files are gitignored (auto-generated at runtime):

| File | Description |
|------|-------------|
| `weather_report.csv` | Appended weather history |
| `weather_script.txt` | Latest generated script |
| `maya_reference.jpg` | Maya's anchor reference image (auto-generated once via Imagen 3) |
| `output_video.mp4` | Final generated video |
