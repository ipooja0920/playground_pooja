# AI Weather Reporter for Storrs, CT

An AI pipeline that fetches live weather + NWS alerts for Storrs, CT, generates an 8-second anchor script, validates it, and produces a broadcast-style video featuring Maya — a consistent AI anchor — using Vertex AI Veo 3.0.

> For a deeper understanding of the architecture, design decisions, and full feature breakdown, please refer to the **[Product Specification](PRODUCT_SPEC.md)**.

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

### 4. Run the Pipeline Manually
```bash
cd GenAI/Weather_AI_AGENT
python main.py
```
The pipeline runs end-to-end: fetches weather → generates script → validates → generates Veo video → validates frame → composites overlay. `final_video.mp4` is written on success.

### 5. Schedule Automated Runs (macOS)
The pipeline is scheduled via cron to run at **8:00 am**, **6:00 pm**, and **9:00 pm EST** daily. To install the cron jobs:
```bash
(crontab -l 2>/dev/null; cat <<'EOF'
# Weather AI Agent — 8am, 6pm, 9pm EST daily
0  8 * * * /Users/pokeapokemon/playground_pooja/GenAI/Weather_AI_AGENT/run_pipeline.sh
0 18 * * * /Users/pokeapokemon/playground_pooja/GenAI/Weather_AI_AGENT/run_pipeline.sh
0 21 * * * /Users/pokeapokemon/playground_pooja/GenAI/Weather_AI_AGENT/run_pipeline.sh
EOF
) | crontab -
```
Each scheduled run retries up to **5 times** (5 min apart) on RAI filter blocks, validation failures, or network errors. Logs are written to `logs/pipeline_YYYYMMDD_HHMMSS.log`.

> ⚠️ **Mandatory for automated runs: the Mac must be on and awake.** Cron does not run if the machine is asleep — that slot is silently skipped with no retry. Keep the Mac plugged in with sleep disabled during scheduled hours, or use an app like [Amphetamine](https://apps.apple.com/us/app/amphetamine/id937984704) to prevent sleep on a schedule.

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
- **Fixed Wilbur Cross backdrop**: Wilbur Cross Building is always visible through the studio's floor-to-ceiling windows — the same base view every broadcast, with weather effects layered on top (rain streaking glass, snow falling past the window, fog rolling in, sunlight flooding through)
- **Time-of-day lighting**: The base scene adapts to when the pipeline runs — daytime is neutral, **5–7:30 pm** shifts to a warm amber twilight with campus path lights flickering on, and **8–11 pm** goes fully dark with exterior floodlights on Wilbur Cross and campus lanterns glowing
- **Weather effects on glass**: Atmospheric effects layer on top of the fixed Wilbur Cross view — rain rivulets, snow accumulation on ledges, frost on glass, lightning flashes — matching today's exact condition
- **Residual snow memory**: If there was a blizzard or heavy snow within the past **30 days**, the ground around Wilbur Cross shows deep snow accumulation; any snow within the past **7 days** leaves a lighter layer — both sourced automatically from `weather_report.csv`, with current weather effects layered on top
- **Post-production display card**: A weather card (current temp, high, low, and condition label) and a UConn NEWS channel logo are composited onto the clean Veo video using Pillow + moviepy — never baked into the AI prompt, following broadcast industry practice; the condition row is automatically hidden for **evening and night broadcasts (5 pm – 6 am EST)**
- **Anchor framing**: Maya stands slightly to the right of frame center (screen right), keeping the left side open for the weather display card
- **Post-generation frame validation**: Gemini Vision checks each rendered frame for any text overlay — retries up to 3 times if Veo hallucinates on-screen graphics
- **Feels-like temperature**: Included in the script prompt so Gemini can describe how it actually feels outside
- **Automated scheduling**: `run_pipeline.sh` runs daily at **8 am, 6 pm, and 9 pm EST** via cron, with up to 5 automatic retries on RAI blocks, validation failures, or network errors — each run logged to `logs/`

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
| `logs/` | Timestamped log files from each scheduled run (`pipeline_YYYYMMDD_HHMMSS.log`) |
