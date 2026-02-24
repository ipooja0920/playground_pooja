import os
import numpy as np
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
from video_service import _get_weather_label

# Display card position and size — all values are fractions of video dimensions
CARD_W_FRAC = 0.17    # card width
CARD_H_FRAC = 0.20    # card height
CARD_X_FRAC = 0.03    # distance from left edge
CARD_Y_FRAC = 0.68    # distance from top edge (lower-third position)

# Colors
CARD_BG      = (8,   18,  38,  215)   # dark navy, ~84% opacity
DIVIDER_COL  = (70,  110, 170, 160)   # muted blue-grey separator
TEMP_COLOR   = (255, 255, 255, 255)   # white
LABEL_COLOR  = (185, 215, 255, 220)   # light blue-white


def _get_font(size):
    """Load a bold system font with graceful fallback to Pillow default."""
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_centered(draw, text, cx, cy, font, fill):
    """Draw text centered at (cx, cy)."""
    bb = draw.textbbox((0, 0), text, font=font)
    x = cx - (bb[0] + bb[2]) // 2
    y = cy - (bb[1] + bb[3]) // 2
    draw.text((x, y), text, font=font, fill=fill)


def _make_card(temp_c, condition_label, card_w, card_h):
    """
    Renders the weather display card as an RGBA PIL Image.

    Layout:
        TOP HALF    — current temperature in large bold white
        BOTTOM HALF — condition label in smaller blue-white
    Background: dark navy with slight transparency and rounded corners.
    """
    img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded navy background
    radius = max(6, int(card_h * 0.12))
    draw.rounded_rectangle([0, 0, card_w - 1, card_h - 1], radius=radius, fill=CARD_BG)

    mid_y = card_h // 2

    # Horizontal divider
    pad = card_w // 8
    line_w = max(1, card_h // 80)
    draw.line([(pad, mid_y), (card_w - pad, mid_y)], fill=DIVIDER_COL, width=line_w)

    # Temperature — top half center
    t_font = _get_font(max(12, card_h // 4))
    _draw_centered(draw, f"{temp_c}°C", card_w // 2, mid_y // 2, t_font, TEMP_COLOR)

    # Condition label — bottom half center
    l_font = _get_font(max(10, card_h // 7))
    label = condition_label
    bb = draw.textbbox((0, 0), label, font=l_font)
    lw = bb[2] - bb[0]
    # Truncate if wider than the card
    while lw > card_w * 0.88 and len(label) > 2:
        label = label[:-1]
        bb = draw.textbbox((0, 0), label + "…", font=l_font)
        lw = bb[2] - bb[0]
    if label != condition_label:
        label += "…"
    _draw_centered(draw, label, card_w // 2, mid_y + mid_y // 2, l_font, LABEL_COLOR)

    return img


def composite_overlay(input_path, output_path, weather_data):
    """
    Composites the weather display card onto the clean Veo video and saves
    the final broadcast-ready output.

    Args:
        input_path:   Path to the raw Veo output (e.g. output_video.mp4)
        output_path:  Destination for the composited video (e.g. final_video.mp4)
        weather_data: Dict with at least 'temp_c' and 'condition'

    Returns:
        output_path on success, None on failure.
    """
    temp_c = weather_data['temp_c']
    condition = weather_data['condition']
    condition_label = _get_weather_label(condition)

    print(f"Compositing display card: {temp_c}°C  /  {condition_label}")

    try:
        clip = VideoFileClip(str(input_path))
        W, H = int(clip.w), int(clip.h)

        card_w = int(W * CARD_W_FRAC)
        card_h = int(H * CARD_H_FRAC)
        card_x = int(W * CARD_X_FRAC)
        card_y = int(H * CARD_Y_FRAC)

        card_img = _make_card(temp_c, condition_label, card_w, card_h)
        card_arr = np.array(card_img)

        card_clip = (
            ImageClip(card_arr, duration=clip.duration)
            .with_position((card_x, card_y))
        )

        final = CompositeVideoClip([clip, card_clip])
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac" if clip.audio is not None else None,
            logger=None,
        )

        print(f"Final video saved: {os.path.abspath(str(output_path))}")
        return output_path

    except Exception as e:
        print(f"Compositor error: {e}")
        return None
