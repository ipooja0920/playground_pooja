"""
Video generator using Google Veo with MoviePy + Pillow fallback.
"""

import io
import logging
import os
import tempfile
from datetime import datetime

from config.settings import Settings
from models.schemas import NormalizedWeather

logger = logging.getLogger(__name__)

# Weather-condition to Veo prompt mapping
CONDITION_PROMPTS = {
    "clear": "A beautiful sunny day in a New England college town, blue sky, warm light, aerial view of green campus grounds",
    "sunny": "A beautiful sunny day in a New England college town, blue sky, warm light, aerial view of green campus grounds",
    "partly cloudy": "A partly cloudy sky over a New England town, scattered clouds, sunlight breaking through, campus buildings",
    "cloudy": "Overcast sky over a New England college town in winter, grey clouds, bare trees, moody atmospheric",
    "overcast": "Heavy overcast skies over a small Connecticut town, dim light, quiet streets",
    "rain": "Rain falling on a New England college campus, wet sidewalks, puddles reflecting lights, umbrellas",
    "light rain": "Light drizzle falling on autumn leaves in a small Connecticut town, misty atmosphere",
    "heavy rain": "Heavy downpour in a New England town, roads flooding slightly, windshield wipers, dramatic sky",
    "snow": "Snow falling gently on a New England college campus, white-covered trees, peaceful winter scene",
    "light snow": "Light snowflakes drifting over a Connecticut town, dusting on rooftops, cozy winter atmosphere",
    "heavy snow": "Heavy snowfall blanketing a New England town, deep snow on roads, plows working, winter storm",
    "fog": "Dense fog rolling through a Connecticut college town, misty campus buildings, low visibility",
    "wind": "Strong winds blowing through bare trees in a New England town, leaves swirling, dramatic sky",
    "thunderstorm": "Dramatic thunderstorm over a New England town, lightning in the distance, dark clouds",
}


class VideoGenerator:
    """Generates weather report videos using Veo or fallback."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(
        self, audio_fp: io.BytesIO, weather: NormalizedWeather
    ) -> io.BytesIO | None:
        """Generate video. Tries Veo first, falls back to title card."""
        # Try Veo first
        try:
            logger.info("Attempting Google Veo video generation...")
            video = self._generate_veo(audio_fp, weather)
            if video:
                logger.info("Veo video generation: OK")
                return video
        except Exception as e:
            logger.warning(f"Veo failed: {e}")

        # Fallback to MoviePy + Pillow
        if self.settings.veo_fallback:
            try:
                logger.info("Falling back to MoviePy + Pillow title card...")
                video = self._generate_title_card_video(audio_fp, weather)
                logger.info("MoviePy fallback: OK")
                return video
            except Exception as e:
                logger.error(f"MoviePy fallback also failed: {e}")

        return None

    def _generate_veo(
        self, audio_fp: io.BytesIO, weather: NormalizedWeather
    ) -> io.BytesIO | None:
        """Generate video using Google Veo API."""
        import google.generativeai as genai

        genai.configure(api_key=self.settings.google_api_key)

        # Build a weather-contextual prompt
        condition_lower = weather.condition_text.lower()
        visual_prompt = CONDITION_PROMPTS.get(
            condition_lower,
            f"A {condition_lower} day in Storrs, Connecticut, "
            f"New England college town atmosphere, cinematic",
        )

        # Add temperature context
        if weather.temperature_f < 32:
            visual_prompt += ", winter cold, frost visible, breath mist in air"
        elif weather.temperature_f > 85:
            visual_prompt += ", summer heat, sun glare, heat shimmer on roads"

        visual_prompt += (
            ". Professional weather broadcast quality, "
            "smooth cinematic camera movement, 1080p, photorealistic"
        )

        logger.info(f"Veo prompt: {visual_prompt[:100]}...")

        try:
            # Use Gemini's Veo model for video generation
            veo_model = genai.GenerativeModel("veo-2.0-generate-001")

            # Generate video from prompt
            response = veo_model.generate_content(
                visual_prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="video/mp4",
                ),
            )

            if response and response.candidates:
                # Extract video bytes from response
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        video_bytes = part.inline_data.data

                        # Now merge audio with the Veo video
                        return self._merge_audio_with_video(
                            video_bytes, audio_fp
                        )

            logger.warning("Veo returned no video data")
            return None

        except Exception as e:
            logger.warning(f"Veo generation error: {e}")
            raise

    def _merge_audio_with_video(
        self, video_bytes: bytes, audio_fp: io.BytesIO
    ) -> io.BytesIO:
        """Merge audio track with Veo-generated video using MoviePy."""
        from moviepy.editor import VideoFileClip, AudioFileClip, vfx

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "veo_video.mp4")
            audio_path = os.path.join(tmpdir, "audio.mp3")
            output_path = os.path.join(tmpdir, "final.mp4")

            # Write temp files
            with open(video_path, "wb") as f:
                f.write(video_bytes)
            with open(audio_path, "wb") as f:
                f.write(audio_fp.getvalue())

            # Load clips
            video_clip = VideoFileClip(video_path)
            audio_clip = AudioFileClip(audio_path)

            # Loop or trim video to match audio duration
            if video_clip.duration < audio_clip.duration:
                video_clip = video_clip.fx(vfx.loop, duration=audio_clip.duration)
            else:
                video_clip = video_clip.subclip(0, audio_clip.duration)

            # Set audio
            final = video_clip.set_audio(audio_clip)
            final.write_videofile(
                output_path, fps=24, codec="libx264", audio_codec="aac"
            )

            # Read back
            with open(output_path, "rb") as f:
                result = io.BytesIO(f.read())

            result.seek(0)
            return result

    def _generate_title_card_video(
        self, audio_fp: io.BytesIO, weather: NormalizedWeather
    ) -> io.BytesIO:
        """Fallback: generate a title-card video using Pillow + MoviePy."""
        from PIL import Image, ImageDraw, ImageFont
        from moviepy.editor import AudioFileClip, ImageClip

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")
            image_path = os.path.join(tmpdir, "card.png")
            output_path = os.path.join(tmpdir, "output.mp4")

            # Write audio
            with open(audio_path, "wb") as f:
                f.write(audio_fp.getvalue())

            # Create title card image
            img = Image.new("RGB", (1920, 1080), color=(15, 15, 60))
            d = ImageDraw.Draw(img)

            # Load fonts
            try:
                font_xl = ImageFont.truetype("Arial Bold.ttf", 96)
                font_lg = ImageFont.truetype("Arial.ttf", 72)
                font_md = ImageFont.truetype("Arial.ttf", 48)
                font_sm = ImageFont.truetype("Arial.ttf", 36)
            except IOError:
                font_xl = ImageFont.load_default()
                font_lg = font_xl
                font_md = font_xl
                font_sm = font_xl

            # Draw gradient-ish decorative bars
            for i in range(5):
                y = 200 + i * 2
                alpha = 255 - i * 40
                d.rectangle(
                    [(100, y), (1820, y + 1)],
                    fill=(100, 100, 255),
                )

            # Title
            d.text(
                (960, 100),
                "☀ WEATHER REPORT ☀",
                fill=(255, 255, 255),
                anchor="mm",
                font=font_md,
            )

            # Location (big)
            d.text(
                (960, 280),
                weather.location_name.upper(),
                fill=(255, 220, 50),
                anchor="mm",
                font=font_xl,
            )

            # Temperature
            d.text(
                (960, 430),
                f"{weather.temperature_f}°F",
                fill=(255, 255, 255),
                anchor="mm",
                font=font_xl,
            )

            # Feels like
            d.text(
                (960, 530),
                f"Feels like {weather.feels_like_f}°F",
                fill=(200, 200, 200),
                anchor="mm",
                font=font_md,
            )

            # Condition
            d.text(
                (960, 650),
                weather.condition_text,
                fill=(180, 220, 255),
                anchor="mm",
                font=font_lg,
            )

            # Details row
            details = (
                f"Wind: {weather.wind_direction} {weather.wind_speed_mph} mph  |  "
                f"Humidity: {weather.humidity_pct}%"
            )
            d.text(
                (960, 780), details, fill=(180, 180, 180), anchor="mm", font=font_sm
            )

            # Date
            date_str = weather.report_date.strftime("%A, %B %d, %Y")
            d.text(
                (960, 950), date_str, fill=(150, 150, 150), anchor="mm", font=font_sm
            )

            img.save(image_path)

            # Build video
            audio_clip = AudioFileClip(audio_path)
            image_clip = ImageClip(image_path).set_duration(audio_clip.duration)
            image_clip = image_clip.set_audio(audio_clip)
            image_clip.write_videofile(
                output_path, fps=24, codec="libx264", audio_codec="aac"
            )

            with open(output_path, "rb") as f:
                result = io.BytesIO(f.read())

            result.seek(0)
            return result
