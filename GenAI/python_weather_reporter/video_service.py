import os
import time
from google import genai
from google.genai import types

# Locked anchor character description — never changes so Maya looks identical every day
ANCHOR_CHARACTER = (
    "a photorealistic female news anchor named Maya, mid-30s, with shoulder-length chestnut "
    "brown hair worn straight and polished, warm fair complexion, sharp green eyes, and a "
    "composed confident expression. She is standing upright in a medium-full shot, looking "
    "directly into the camera lens. She wears a tailored royal blue blazer over a crisp white "
    "silk shirt and a matching royal blue pencil skirt — business formal attire."
)


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
        return condition.upper()


def _get_studio_environment(condition):
    """Returns a visual description of the studio that reflects today's weather."""
    c = condition.lower()
    if "thunder" in c or ("storm" in c and "light" not in c):
        return (
            "the floor-to-ceiling studio glass windows reveal a dramatic stormy sky with heavy "
            "rain and distant lightning flashes; deep moody blue-grey studio lighting"
        )
    elif "heavy rain" in c or ("rain" in c and "light" not in c and "drizzle" not in c):
        return (
            "steady rain streaks flow down the tall studio glass windows; cool blue ambient "
            "studio lighting with soft city light reflections through the rain"
        )
    elif "drizzle" in c or ("light" in c and "rain" in c):
        return (
            "soft light rain drifts down the studio glass windows; cool diffused blue-grey "
            "studio lighting creating a calm, quiet atmosphere"
        )
    elif "snow" in c or "blizzard" in c:
        return (
            "gentle snowflakes drift past the floor-to-ceiling studio glass windows against "
            "a white-grey sky; soft cool-white diffused studio lighting"
        )
    elif "fog" in c or "mist" in c:
        return (
            "a hazy misty atmosphere is visible through the studio glass; soft diffused "
            "white-grey ambient lighting with a calm atmospheric glow"
        )
    elif "overcast" in c or "cloud" in c:
        return (
            "an overcast grey sky is visible through the wide studio glass windows; "
            "cool even diffused studio lighting with no harsh shadows"
        )
    elif "sunny" in c or "clear" in c:
        return (
            "warm golden sunlight streams through the studio's glass windows; "
            "bright warm-white studio lighting with a clean energetic feel"
        )
    else:
        return (
            "a sleek modern weather studio with large glass windows showing a city skyline; "
            "neutral professional broadcast lighting"
        )


def generate_video_prompt(weather_data, script_text):
    """
    Builds a detailed, production-grade Veo prompt.
    Anchor appearance is locked for visual consistency across every daily video.
    Studio display and background are dynamically generated from today's weather data.
    """
    condition = weather_data['condition']
    weather_label = _get_weather_label(condition)
    studio_env = _get_studio_environment(condition)
    temp = weather_data['temp_c']
    high = weather_data['high_c']
    low = weather_data['low_c']

    prompt = (
        f"A professional 4K 16:9 medium-full shot of {ANCHOR_CHARACTER} "
        f"She is delivering the following 8-second weather report with accurate lip-sync, "
        f"natural speech rhythm, and subtle professional hand gestures: \"{script_text}\". "
        f"Behind her is a sleek new-age glass-textured broadcast studio display showing bold "
        f"dynamic data in large text: \"TEMP: {temp}°C  |  HIGH: {high}°C  |  LOW: {low}°C  |  {weather_label}\". "
        f"Studio environment behind the glass: {studio_env}. "
        "The video starts immediately as she begins speaking and ends exactly at the 8-second "
        "mark as she finishes her last word — no dialogue is cut off. "
        "Camera is static and locked, eye-level medium-full shot showing her from head to just "
        "below the knees. Photorealistic, 4K resolution, natural skin textures, "
        "professional broadcast quality lighting."
    )
    return prompt


def generate_weather_video(weather_data, script_text, output_path="output_video.mp4",
                           project_id=None, location="us-central1"):
    """
    Calls Vertex AI Veo 3.0 to generate an 8-second weather report video.
    Saves the video locally if bytes are returned, or prints the GCS URI if not.
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

        operation = client.models.generate_videos(
            model="veo-3.0-generate-preview",
            prompt=prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio="16:9",
                duration_seconds=8,
                number_of_videos=1,
                person_generation="allow_adult",
            ),
        )

        print("Polling for completion (this takes ~2-3 minutes)...")
        for poll in range(40):
            time.sleep(15)
            operation = client.operations.get(operation)
            print(f"  Poll {poll + 1}: done={operation.done}")
            if operation.done is True:
                break

        if operation.error:
            print(f"Generation failed with error: {operation.error}")
            return None, None

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

        print("Generation did not return a video. Check GCP project quota and Veo access.")
        return None, None

    except Exception as e:
        print(f"Error generating video: {e}")
        return None, None
