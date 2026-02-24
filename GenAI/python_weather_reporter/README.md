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
pip install requests pandas google-cloud-aiplatform google-genai moviepy pillow numpy
```

Also install `ffmpeg` for post-generation frame validation:
```bash
# macOS
brew install ffmpeg
# Ubuntu/Debian
sudo apt install ffmpeg
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
4. **Validate** (`validator.py`) — Runs 3 checks before video generation (see below).
5. **Generate Video** (`video_service.py`) — If all hard checks pass, Veo 3.0 generates an 8-second 16:9 4K video with no text overlays. Saved locally as `output_video.mp4`. Up to 3 API retry attempts.
6. **Frame Validation** (`validator.py`) — After each video, Gemini Vision inspects an extracted frame (via ffmpeg) for any visible text overlay. Veo is told to render none, so any text is a hallucination. If text is found, the video is regenerated (up to 3 visual retries).
7. **Composite Overlay** (`compositor.py`) — After a clean frame passes, Pillow renders two overlays: (1) a 4-row **weather display card** (current temp, high, low, condition label) in the upper-left, and (2) a **UConn NEWS channel logo** (navy blue + red stripe) in the top-right corner. moviepy composites both onto the clean video. Result saved as `final_video.mp4`.

---

## Validation Suite

| Check | Type | What It Verifies |
|-------|------|-----------------|
| **Script Validation** | Hard FAIL | Script is in English, no spelling errors, reflects correct weather, no repeated phrases; Extreme/Severe alert must appear in script |
| **Prompt Validation** | Hard FAIL | No display card instructions in prompt; explicit no-text directive present; UConn landmarks; active snowfall for snowy conditions; Maya name and anchor role; 4K/16:9 format |
| **Frame Validation** | Post-gen FAIL → retry | Gemini Vision checks whether any text overlay is visible in the rendered frame — PASS if clean, FAIL if any text detected |
| **Character Consistency** | Soft WARN | `maya_reference.jpg` exists for visual consistency across runs |

Video is only generated if all **Hard** checks pass.

---

## Key Features

- **NWS alert scripting**: When an Extreme or Severe NWS alert is active (e.g. Blizzard Warning), the script must lead with or urgently mention it
- **Snow condition differentiation**: Three distinct snowy backgrounds — blizzard/whiteout, light/patchy snow drifting, moderate snow actively falling
- **UConn campus backdrop**: Homer Babbidge Library and central green dynamically matched to the weather condition behind Maya in every shot
- **Post-production display card**: A 4-row card (current temp, high, low, condition label) and a UConn NEWS channel logo are composited onto the clean Veo video using Pillow + moviepy — never baked into the AI prompt, following broadcast industry practice
- **Anchor framing**: Maya stands slightly to the right of frame center (screen right), keeping the left side open for the weather display card
- **Post-generation frame validation**: Gemini Vision checks each rendered frame for any text overlay — retries up to 3 times if Veo hallucinates on-screen graphics
- **Feels-like temperature**: Included in the script prompt so Gemini can describe how it actually feels outside

---

## Output Files

All output files are gitignored (auto-generated at runtime):

| File | Description |
|------|-------------|
| `weather_report.csv` | Appended weather history |
| `weather_script.txt` | Latest generated script |
| `maya_reference.jpg` | Maya's anchor reference image (auto-generated once via Imagen 3) |
| `output_video.mp4` | Raw Veo output — clean video of Maya with no text overlays |
| `final_video.mp4` | Broadcast-ready video with composited weather display card and UConn NEWS logo |
