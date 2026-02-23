import os
import time
from google import genai
from google.genai import types

# Single source of truth for the Veo model — only this constant is used for video generation
VEO_MODEL = "veo-3.0-generate-preview"

# Locked anchor character — this exact description is used everywhere to keep Maya identical
ANCHOR_CHARACTER = (
    "a photorealistic female broadcast news anchor named Maya, mid-30s, with shoulder-length "
    "chestnut brown hair worn straight and polished, warm fair complexion, sharp green eyes, "
    "and a composed confident expression. She wears a tailored royal blue blazer over a crisp "
    "white silk shirt and a matching royal blue pencil skirt — business formal attire."
)

REFERENCE_IMAGE_PATH = "maya_reference.jpg"
LOGO_PATH = "uconn_news_logo.png"


def generate_or_load_logo(project_id, location="us-central1"):
    """
    Generates the UConn News broadcast logo using Imagen 3 if it doesn't exist yet.
    The logo is stored locally and referenced in every video generation prompt for brand consistency.
    """
    if os.path.exists(LOGO_PATH):
        print(f"Using existing UConn News logo: {LOGO_PATH}")
        return LOGO_PATH

    print("Generating UConn News logo for the first time...")
    try:
        client = genai.Client(vertexai=True, project=project_id, location=location)
        logo_prompt = (
            "A professional broadcast news logo for 'UConn News'. "
            "Modern television news branding — clean, bold, and authoritative with university-style professionalism. "
            "Bold geometric sans-serif typography reading exactly 'UConn News' — no additional words, no slogons, no extra graphics. "
            "White text on a deep navy blue background with a subtle red accent bar or underline. "
            "Flat, clean, vector-style design with sharp edges — no gradients, no weather icons, no decorative elements. "
            "Horizontal layout, compact and balanced, suitable for top-corner placement in a broadcast frame. "
            "High contrast, 4K resolution, professional broadcast quality."
        )
        response = client.models.generate_images(
            model="imagen-3.0-generate-001",
            prompt=logo_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="4:3",
            ),
        )
        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
            with open(LOGO_PATH, "wb") as f:
                f.write(image_bytes)
            print(f"UConn News logo saved: {os.path.abspath(LOGO_PATH)}")
            return LOGO_PATH
    except Exception as e:
        print(f"Could not generate logo: {e}")
    return None


def generate_or_load_reference_image(project_id, location="us-central1"):
    """
    Generates Maya's reference image using Imagen 3 if it doesn't exist yet.
    The image is stored locally and reused in every video generation for character consistency.
    """
    if os.path.exists(REFERENCE_IMAGE_PATH):
        print(f"Using existing Maya reference image: {REFERENCE_IMAGE_PATH}")
        return REFERENCE_IMAGE_PATH

    print("Generating Maya reference image for the first time...")
    try:
        client = genai.Client(vertexai=True, project=project_id, location=location)
        image_prompt = (
            f"A photorealistic full-body portrait of {ANCHOR_CHARACTER} "
            "She is standing upright, facing the camera directly, in a professional "
            "broadcast studio setting. Neutral background, professional lighting, 4K quality."
        )
        response = client.models.generate_images(
            model="imagen-3.0-generate-001",
            prompt=image_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="9:16",
            ),
        )
        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
            with open(REFERENCE_IMAGE_PATH, "wb") as f:
                f.write(image_bytes)
            print(f"Maya reference image saved: {os.path.abspath(REFERENCE_IMAGE_PATH)}")
            return REFERENCE_IMAGE_PATH
    except Exception as e:
        print(f"Could not generate reference image: {e}")
    return None


def _get_weather_label(condition):
    """Maps a condition string to a clean display label for the studio screen."""
    c = condition.lower()
    if "thunder" in c or ("storm" in c and "light" not in c):
        return "STORMY"
    elif "light" in c and ("storm" in c or "thunder" in c):
        return "LIGHT STORM"
    elif "heavy rain" in c or "heavy shower" in c:
        return "HEAVY RAIN"
    elif "drizzle" in c or ("light" in c and "rain" in c):
        return "LIGHT RAIN"
    elif "rain" in c or "shower" in c:
        return "RAINY"
    elif "light snow" in c or ("light" in c and "snow" in c):
        return "LIGHT SNOW"
    elif "snow" in c or "blizzard" in c:
        return "SNOWY"
    elif "fog" in c or "mist" in c:
        return "FOGGY"
    elif "overcast" in c or "cloud" in c:
        return "CLOUDY"
    elif "sunny" in c or "clear" in c:
        return "SUNNY"
    else:
        # Strip redundant words that are already used as labels in the display
        label = condition.upper()
        for redundant in ["HIGH", "LOW", "TEMP"]:
            label = label.replace(redundant, "").strip()
        return label


def _get_studio_environment(condition):
    """Returns a visual description of the UConn Storrs campus backdrop matching today's weather."""
    c = condition.lower()
    if "thunder" in c or ("storm" in c and "light" not in c):
        return (
            "the broadcast studio's floor-to-ceiling windows frame the UConn Storrs campus under "
            "a dramatic stormy sky — the iconic Homer Babbidge Library and surrounding brick "
            "buildings are visible through heavy rain and distant lightning flashes; deep moody "
            "blue-grey studio lighting"
        )
    elif "heavy rain" in c or ("rain" in c and "light" not in c and "drizzle" not in c):
        return (
            "steady rain streaks down the studio's wide windows revealing the UConn Storrs campus "
            "— the central UConn green and Georgian-style brick academic buildings visible through "
            "the downpour; cool blue ambient studio lighting with wet-pavement reflections"
        )
    elif "drizzle" in c or ("light" in c and "rain" in c):
        return (
            "soft drizzle falls across the UConn Storrs campus visible through the studio windows "
            "— the tree-lined pathways and the Wilbur Cross Building in the misty background; "
            "cool diffused blue-grey studio lighting creating a calm quiet atmosphere"
        )
    elif "blizzard" in c or ("heavy" in c and "snow" in c):
        return (
            "through the studio's floor-to-ceiling windows a full blizzard rages across the UConn "
            "Storrs campus — thick curtains of snow are actively falling and swirling past the glass, "
            "nearly obscuring the Homer Babbidge Library and the central green in whiteout conditions; "
            "bare oak trees barely visible as snow piles up on the campus paths; "
            "cold harsh white studio lighting matching the blizzard outside"
        )
    elif "light snow" in c or ("light" in c and "snow" in c) or "patchy" in c:
        return (
            "light snowflakes drift and fall gently past the studio's wide windows, dusting the "
            "UConn Storrs campus — the Homer Babbidge Library and the central green are lightly "
            "frosted in white, bare oak trees catching the snowflakes against a soft grey sky; "
            "cool diffused white studio lighting with a quiet wintry feel"
        )
    elif "snow" in c:
        return (
            "snowflakes are actively falling past the studio's floor-to-ceiling windows across the "
            "UConn Storrs campus — the Homer Babbidge Library, the central green, and the Georgian "
            "brick buildings are blanketed in fresh snow with more falling steadily; "
            "bare oak trees heavy with snow against a flat white sky; "
            "cool soft-white studio lighting"
        )
    elif "fog" in c or "mist" in c:
        return (
            "a hazy mist rolls across the UConn Storrs campus visible through the studio windows "
            "— the silhouette of campus brick buildings and tall oaks barely visible through the "
            "atmospheric fog; soft diffused white-grey ambient lighting"
        )
    elif "overcast" in c or "cloud" in c:
        return (
            "an overcast grey sky hangs over the UConn Storrs campus visible through the studio "
            "windows — the central green and brick academic buildings under flat even cloud cover; "
            "cool diffused studio lighting with no harsh shadows"
        )
    elif "sunny" in c or "clear" in c:
        return (
            "warm golden sunlight bathes the UConn Storrs campus visible through the studio "
            "windows — the Homer Babbidge Library, the sunlit central green, and blue skies above "
            "the iconic Georgian brick buildings; bright warm-white studio lighting with a clean "
            "energetic feel"
        )
    else:
        return (
            "the UConn Storrs campus is visible through the broadcast studio's large windows — "
            "the central green and brick academic buildings under a neutral sky; "
            "professional broadcast lighting"
        )


def generate_video_prompt(weather_data, script_text):
    """
    Builds a detailed Veo prompt.
    - Maya is positioned slightly right so the background display is clearly visible on the left.
    - The studio display uses a strict three-section card (top/middle/bottom):
        TOP    — current temperature only
        MIDDLE — HIGH: value  LOW: value
        BOTTOM — weather condition only
    - Anchor appearance is locked via ANCHOR_CHARACTER for daily visual consistency.
    """
    condition = weather_data['condition']
    weather_label = _get_weather_label(condition)
    studio_env = _get_studio_environment(condition)
    temp = weather_data['temp_c']
    high = weather_data['high_c']
    low = weather_data['low_c']

    # Three-section temperature card — each section is distinct and contains only its own content
    top_text = f"{temp}°C"
    mid_text = f"HIGH: {high}°C  LOW: {low}°C"
    bottom_text = weather_label

    # Append active NWS alert overlay if Extreme or Severe
    alert = weather_data.get("alert")
    alert_overlay = ""
    if alert and alert.get("severity") in ("Extreme", "Severe"):
        alert_event = alert["event"].upper()
        alert_overlay = (
            f"Directly below the navy lower-third title bar, and touching it, is a single full-width solid red alert banner "
            f"reading 'WARNING: {alert_event} IN EFFECT' in bold white sans-serif text — "
            f"same font family as the title bar, urgent and clearly visible. "
            f"This alert bar appears exactly once and only directly beneath the navy title bar above. "
        )

    prompt = (
        f"A professional 4K 16:9 TV news broadcast shot of {ANCHOR_CHARACTER} "
        "She is positioned slightly to the right of the frame, standing upright and looking "
        "directly into the camera lens, so the studio display panel on the left side of the "
        "frame is clearly visible to viewers. "
        f"She delivers the following 8-second weather report with clear lip-sync, natural "
        f"speech rhythm, and subtle professional hand gestures: \"{script_text}\". "
        "Behind her and to her left is a sleek new-age glass-textured broadcast studio display panel "
        "divided into three clearly separated sections (top to bottom): "
        f"TOP SECTION — shows only '{top_text}' (current temperature, large and bold); "
        f"MIDDLE SECTION — shows only '{mid_text}' (HIGH on the left, LOW on the right); "
        f"BOTTOM SECTION — shows only '{bottom_text}' (weather condition). "
        "The card must contain ONLY these three sections — no extra numbers, no timestamps, "
        "no random strings, no duplicate values, HIGH and LOW each spelled correctly and shown exactly once. "
        f"Studio environment: {studio_env}. "
        "Overlay graphics: in the top-left corner of the frame is the official 'UConn News' broadcast logo — "
        "bold white sans-serif text on a deep navy blue background with a subtle red accent. "
        "Logo placement: 80px padding from the top and left edges, approximately 400px wide, "
        "maintaining its original aspect ratio. "
        "The logo is static and identical across all frames — do NOT move, resize, animate, or duplicate it. "
        "It appears exactly once in the top-left corner only, with no color changes and no text modification. "
        "At the very bottom of the frame is a single lower-third title bar: a full-width semi-transparent navy blue bar "
        "containing only the centered text 'Today's Weather Forecast' in bold white sans-serif (Helvetica Neue or Roboto Condensed style). "
        "No condition badges, no extra boxes, no floating labels, no duplicate title elements anywhere else in the frame. "
        f"{alert_overlay}"
        "The video starts immediately as she begins speaking and ends exactly at the 8-second "
        "mark as she finishes her last word — no dialogue is cut off. "
        "Camera is static and locked at eye level. "
        "4K resolution, professional broadcast quality."
    )
    return prompt


def generate_weather_video(weather_data, script_text, output_path="output_video.mp4",
                           project_id=None, location="us-central1"):
    """
    Calls Vertex AI Veo 3.0 to generate an 8-second weather report video.
    Loads (or generates) Maya's reference image and passes it as an ASSET reference
    to Veo so the anchor looks consistent across every daily video.
    """
    project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        print("Error: GOOGLE_CLOUD_PROJECT not set.")
        return None, None

    try:
        client = genai.Client(vertexai=True, project=project_id, location=location)
        prompt = generate_video_prompt(weather_data, script_text)

        print("\nGenerating video with Veo 3.0...")
        print(f"Prompt:\n{prompt}\n")

        # Generate/load Maya's reference image and UConn News logo (used for consistency checks)
        generate_or_load_reference_image(project_id, location)
        generate_or_load_logo(project_id, location)

        operation = client.models.generate_videos(
            model=VEO_MODEL,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio="16:9",
                duration_seconds=8,
                number_of_videos=1,
                person_generation="allow_adult",
            ),
        )

        for attempt in range(1, 4):  # up to 3 attempts
            if attempt > 1:
                print(f"\nRetrying video generation (attempt {attempt}/3)...")
                operation = client.models.generate_videos(
                    model=VEO_MODEL,
                    prompt=prompt,
                    config=types.GenerateVideosConfig(
                        aspect_ratio="16:9",
                        duration_seconds=8,
                        number_of_videos=1,
                        person_generation="allow_adult",
                    ),
                )

            print(f"Polling for completion (attempt {attempt}, ~2-3 min)...")
            for poll in range(40):
                time.sleep(15)
                operation = client.operations.get(operation)
                print(f"  Poll {poll + 1}: done={operation.done}")
                if operation.done is True:
                    break

            if operation.error:
                print(f"Attempt {attempt} failed with error: {operation.error}")
                if attempt == 3:
                    return None, None
                continue

            # Debug: show full operation state when done but no video returned
            print(f"  operation.done={operation.done}")
            print(f"  operation.error={operation.error}")
            print(f"  operation.response={operation.response}")
            if operation.response:
                videos = getattr(operation.response, 'generated_videos', None)
                print(f"  generated_videos={videos}")
                if videos:
                    print(f"  video[0]={videos[0]}")

            if operation.response and operation.response.generated_videos:
                video = operation.response.generated_videos[0].video

                if hasattr(video, 'video_bytes') and video.video_bytes:
                    with open(output_path, "wb") as f:
                        f.write(video.video_bytes)
                    print(f"Video saved locally: {os.path.abspath(output_path)}")
                    return output_path, prompt

                elif hasattr(video, 'uri') and video.uri:
                    print(f"Video available at GCS URI: {video.uri}")
                    print(f"Download with: gsutil cp {video.uri} {output_path}")
                    return video.uri, prompt

            print(f"Attempt {attempt} returned no video — retrying...")

        print("All 3 attempts failed. Check GCP project quota and Veo access.")
        return None, None

    except Exception as e:
        print(f"Error generating video: {e}")
        return None, None
