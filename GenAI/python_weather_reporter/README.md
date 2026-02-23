# AI Weather Reporter for Storrs, CT

An AI pipeline that fetches live weather for Storrs, CT, generates an 8-second anchor script, validates it, and produces a broadcast-style video featuring Maya — a consistent AI anchor — using Vertex AI Veo 3.0.

---

## Setup

### 1. Google Cloud Credentials
- Enable **Vertex AI API** in your Google Cloud Console.
- Authenticate with Application Default Credentials:
  ```bash
  gcloud auth application-default login
  ```
- Set your project environment variable:
  ```bash
  export GOOGLE_CLOUD_PROJECT=your-gcp-project-id
  ```

### 2. Install Dependencies
```bash
pip install requests pandas google-cloud-aiplatform google-genai
```

### 3. Run the Pipeline
```bash
python main.py
```

---

## How It Works

1. **Weather Fetch** (`weather_service.py`) — Calls [wttr.in](https://wttr.in) for live conditions (temp, high, low, condition) in Storrs, CT. No API key required.
2. **Store Locally** (`sync_weather.py`) — Appends weather data to `weather_report.csv`.
3. **Generate Script** (`script_service.py`) — Gemini 2.0 Flash generates a 15–20 word (~8s) spoken script for anchor Maya. Saves to `weather_script.txt`.
4. **Validate** (`validator.py`) — Runs 4 checks before video generation (see below).
5. **Generate Video** (`video_service.py`) — If all hard checks pass, Veo 3.0 generates an 8-second 16:9 video. Saved locally as `output_video.mp4`.

---

## Validation Suite

| Check | Type | What It Verifies |
|-------|------|-----------------|
| **Script Validation** | Hard FAIL | Script is in English, no spelling errors, reflects correct weather, no repeated phrases |
| **Prompt Validation** | Hard FAIL | Display shows `TEMP`, `HIGH`, `LOW` exactly once; correct weather condition in background; UConn landmarks present; overlay graphics present; no misspellings |
| **No-Repetition Check** | Soft WARN | Temperature numbers not spoken aloud if already visible on the studio display |
| **Character Consistency** | Soft WARN | `maya_reference.jpg` exists for visual consistency across runs |

Video is only generated if all **Hard** checks pass.

---

## Output Files

| File | Description |
|------|-------------|
| `weather_report.csv` | Appended weather history |
| `weather_script.txt` | Latest generated script |
| `maya_reference.jpg` | Maya's anchor reference image (auto-generated once) |
| `output_video.mp4` | Final generated video |
