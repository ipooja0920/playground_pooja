"""
Audio generator using Google Cloud Text-to-Speech (WaveNet) with gTTS fallback.
Handles long scripts by chunking into paragraphs.
"""

import io
import logging
import re

from config.settings import Settings

logger = logging.getLogger(__name__)

# Character replacements for TTS readability
TTS_REPLACEMENTS = {
    "°F": " degrees Fahrenheit",
    "°C": " degrees Celsius",
    "°": " degrees",
    "%": " percent",
    "mph": " miles per hour",
    "inHg": " inches of mercury",
    "UV": "U V",
    "NNE": "north-northeast",
    "NNW": "north-northwest",
    "NE": "northeast",
    "NW": "northwest",
    "ENE": "east-northeast",
    "ESE": "east-southeast",
    "SSE": "south-southeast",
    "SSW": "south-southwest",
    "SE": "southeast",
    "SW": "southwest",
    "WNW": "west-northwest",
    "WSW": "west-southwest",
}

# Maximum characters per TTS request (Cloud TTS limit)
CLOUD_TTS_CHAR_LIMIT = 5000


class AudioGenerator:
    """Generates spoken audio from weather report scripts."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, script: str) -> io.BytesIO | None:
        """Generate audio from script. Returns BytesIO of MP3 data."""
        clean_script = self._preprocess_for_speech(script)

        # Try Google Cloud TTS first
        try:
            logger.info("Attempting Google Cloud TTS (WaveNet)...")
            audio = self._generate_cloud_tts(clean_script)
            logger.info("Cloud TTS: OK")
            return audio
        except Exception as e:
            logger.warning(f"Cloud TTS failed: {e}")

        # Fallback to gTTS
        try:
            logger.info("Falling back to gTTS...")
            audio = self._generate_gtts(clean_script)
            logger.info("gTTS fallback: OK")
            return audio
        except Exception as e:
            logger.error(f"gTTS fallback also failed: {e}")
            return None

    def _preprocess_for_speech(self, text: str) -> str:
        """Replace symbols and abbreviations with spoken equivalents."""
        # Remove markdown formatting
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.+?)\*', r'\1', text)  # Italic
        text = re.sub(r'\[.*?\]', '', text)  # Stage directions [Sound Effect: ...]
        text = re.sub(r'#{1,6}\s*', '', text)  # Headers

        # Apply replacements (longest matches first to avoid partial replacements)
        for symbol, spoken in sorted(
            TTS_REPLACEMENTS.items(), key=lambda x: len(x[0]), reverse=True
        ):
            text = text.replace(symbol, spoken)

        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _generate_cloud_tts(self, text: str) -> io.BytesIO:
        """Generate audio using Google Cloud TTS with WaveNet voice."""
        from google.cloud import texttospeech
        import os

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
            self.settings.google_application_credentials
        )

        client = texttospeech.TextToSpeechClient()

        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name=self.settings.tts_voice_name,
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=self.settings.tts_speaking_rate,
            sample_rate_hertz=48000,
        )

        # Handle long scripts by chunking
        chunks = self._chunk_text(text, CLOUD_TTS_CHAR_LIMIT)
        audio_segments = []

        for i, chunk in enumerate(chunks):
            logger.info(f"Cloud TTS: processing chunk {i + 1}/{len(chunks)}...")
            synthesis_input = texttospeech.SynthesisInput(text=chunk)
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            audio_segments.append(response.audio_content)

        # Concatenate audio segments
        if len(audio_segments) == 1:
            result = io.BytesIO(audio_segments[0])
        else:
            result = self._concatenate_mp3(audio_segments)

        result.seek(0)
        return result

    def _generate_gtts(self, text: str) -> io.BytesIO:
        """Fallback: Generate audio using gTTS."""
        from gtts import gTTS

        tts = gTTS(text=text, lang="en", slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp

    @staticmethod
    def _chunk_text(text: str, max_chars: int) -> list[str]:
        """Split text into chunks at paragraph boundaries."""
        if len(text) <= max_chars:
            return [text]

        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # If single paragraph exceeds limit, split at sentences
                if len(para) > max_chars:
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    sub_chunk = ""
                    for sent in sentences:
                        if len(sub_chunk) + len(sent) + 1 > max_chars:
                            chunks.append(sub_chunk.strip())
                            sub_chunk = sent
                        else:
                            sub_chunk += " " + sent
                    current_chunk = sub_chunk
                else:
                    current_chunk = para
            else:
                current_chunk += "\n\n" + para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    @staticmethod
    def _concatenate_mp3(segments: list[bytes]) -> io.BytesIO:
        """Concatenate multiple MP3 segments using pydub."""
        try:
            from pydub import AudioSegment

            combined = AudioSegment.empty()
            for seg_bytes in segments:
                seg = AudioSegment.from_mp3(io.BytesIO(seg_bytes))
                combined += seg

            output = io.BytesIO()
            combined.export(output, format="mp3")
            output.seek(0)
            return output
        except ImportError:
            # If pydub not available, just concatenate raw bytes (may have glitches)
            logger.warning("pydub not available, concatenating raw MP3 bytes")
            output = io.BytesIO()
            for seg in segments:
                output.write(seg)
            output.seek(0)
            return output
