import os
import numpy as np
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
from video_service import _get_weather_label

# ── Weather card ─────────────────────────────────────────────────────────────
# All values are fractions of video dimensions
CARD_W_FRAC  = 0.26   # card width
CARD_H_FRAC  = 0.62   # card height (elongated, 4 rows)
CARD_X_FRAC  = 0.06   # distance from left edge
CARD_Y_FRAC  = 0.14   # distance from top edge

# Card colors
CARD_BG      = (8,   18,  38,  215)   # dark navy, ~84% opacity
DIVIDER_COL  = (70,  110, 170, 160)   # muted blue-grey separator
TEMP_COLOR   = (255, 255, 255, 255)   # white
LABEL_COLOR  = (185, 215, 255, 220)   # light blue-white

# ── Channel logo ──────────────────────────────────────────────────────────────
# Top-right corner; values are fractions of video dimensions
LOGO_W_FRAC  = 0.12   # logo width
LOGO_H_FRAC  = 0.10   # logo height
LOGO_MARGIN  = 0.02   # gap from the right and top edges

# Logo colors
LOGO_BG      = (0,   56,  101, 245)   # UConn navy blue, near-opaque
LOGO_TEXT    = (255, 255, 255, 255)   # white
LOGO_RED     = (200, 16,  46,  255)   # UConn red


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


def _make_card(temp_c, high_c, low_c, condition_label, card_w, card_h):
    """
    Renders the weather display card as an RGBA PIL Image.

    Layout (top to bottom):
        1. Current temperature  — large bold white
           ── divider ──
        2. HIGH: {high}°C       — smaller blue-white
        3. LOW:  {low}°C        — smaller blue-white
        4. Condition label      — smaller blue-white (omitted when None)
    All rows are horizontally centered within the card.
    Background: dark navy with transparency and rounded corners.
    """
    show_condition = condition_label is not None
    n_bottom_rows = 3 if show_condition else 2

    img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded navy background
    radius = max(6, int(card_h * 0.06))
    draw.rounded_rectangle([0, 0, card_w - 1, card_h - 1], radius=radius, fill=CARD_BG)

    pad_top = int(card_h * 0.05)
    pad_bot = int(card_h * 0.04)

    # Temp section: ~28% of card height
    temp_section_h = int(card_h * 0.28)
    temp_cy = pad_top + temp_section_h // 2

    # Divider sits just below the temp section
    divider_y = pad_top + temp_section_h + int(card_h * 0.015)

    # Remaining height split equally among HIGH / LOW / condition rows
    row_start = divider_y + int(card_h * 0.025)
    remaining_h = card_h - row_start - pad_bot
    row_h = remaining_h // n_bottom_rows

    # Font sizes — temp larger, detail rows smaller
    t_font = _get_font(max(14, card_h // 5))
    s_font = _get_font(max(10, card_h // 9))

    # 1. Current temperature — centered
    _draw_centered(draw, f"{temp_c}°C", card_w // 2, temp_cy, t_font, TEMP_COLOR)

    # Horizontal divider
    pad = card_w // 10
    line_w = max(1, card_h // 120)
    draw.line([(pad, divider_y), (card_w - pad, divider_y)], fill=DIVIDER_COL, width=line_w)

    # 2. HIGH — centered
    high_cy = row_start + row_h // 2
    _draw_centered(draw, f"HIGH: {high_c}°C", card_w // 2, high_cy, s_font, LABEL_COLOR)

    # 3. LOW — centered
    low_cy = row_start + row_h + row_h // 2
    _draw_centered(draw, f"LOW:  {low_c}°C", card_w // 2, low_cy, s_font, LABEL_COLOR)

    # 4. Condition label — centered (optional)
    if show_condition:
        cond_cy = row_start + 2 * row_h + row_h // 2
        label = condition_label
        bb = draw.textbbox((0, 0), label, font=s_font)
        lw = bb[2] - bb[0]
        while lw > card_w * 0.88 and len(label) > 2:
            label = label[:-1]
            bb = draw.textbbox((0, 0), label + "…", font=s_font)
            lw = bb[2] - bb[0]
        if label != condition_label:
            label += "…"
        _draw_centered(draw, label, card_w // 2, cond_cy, s_font, LABEL_COLOR)

    return img


def _make_logo(logo_w, logo_h):
    """
    Renders the UConn NEWS channel logo as an RGBA PIL Image.

    Layout:
        ┌─────────────────────┬───┐
        │       UConn         │   │  ← blue background, white text
        │       NEWS          │   │  ← red vertical stripe on right edge
        └─────────────────────┴───┘

    The red stripe occupies ~12% of logo width on the right side.
    """
    red_w = max(4, int(logo_w * 0.12))   # red stripe width
    blue_w = logo_w - red_w               # blue area width

    img = Image.new("RGBA", (logo_w, logo_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Blue rectangle (full height, left portion)
    draw.rectangle([0, 0, blue_w - 1, logo_h - 1], fill=LOGO_BG)

    # Red vertical stripe (full height, right edge)
    draw.rectangle([blue_w, 0, logo_w - 1, logo_h - 1], fill=LOGO_RED)

    # Text rows: "UConn" at 33% height, "NEWS" at 67% height
    font = _get_font(max(10, int(logo_h * 0.42)))
    cx = blue_w // 2
    _draw_centered(draw, "UConn", cx, int(logo_h * 0.30), font, LOGO_TEXT)
    _draw_centered(draw, "NEWS",  cx, int(logo_h * 0.72), font, LOGO_TEXT)

    return img


def composite_overlay(input_path, output_path, weather_data):
    """
    Composites the weather display card and the UConn NEWS channel logo onto
    the clean Veo video and saves the final broadcast-ready output.

    Args:
        input_path:   Path to the raw Veo output (e.g. output_video.mp4)
        output_path:  Destination for the composited video (e.g. final_video.mp4)
        weather_data: Dict with 'temp_c', 'high_c', 'low_c', 'condition'

    Returns:
        output_path on success, None on failure.
    """
    temp_c = weather_data['temp_c']
    high_c = weather_data['high_c']
    low_c  = weather_data['low_c']
    condition = weather_data['condition']
    # Pass None for condition label when condition is unknown — row omitted from card
    condition_label = None if "unknown" in condition.lower() else _get_weather_label(condition)

    print(f"Compositing display card: {temp_c}°C  H:{high_c}°C  L:{low_c}°C  /  {condition_label or 'n/a'}")

    try:
        clip = VideoFileClip(str(input_path))
        W, H = int(clip.w), int(clip.h)

        # ── Weather card (lower-left) ────────────────────────────────────────
        card_w = int(W * CARD_W_FRAC)
        card_h = int(H * CARD_H_FRAC)
        card_x = int(W * CARD_X_FRAC)
        card_y = int(H * CARD_Y_FRAC)

        card_img  = _make_card(temp_c, high_c, low_c, condition_label, card_w, card_h)
        card_clip = (
            ImageClip(np.array(card_img), duration=clip.duration)
            .with_position((card_x, card_y))
        )

        # ── Channel logo (top-right) ─────────────────────────────────────────
        logo_w = int(W * LOGO_W_FRAC)
        logo_h = int(H * LOGO_H_FRAC)
        margin  = int(W * LOGO_MARGIN)
        logo_x  = W - logo_w - margin          # flush to right edge with margin
        logo_y  = margin                        # small gap from top

        logo_img  = _make_logo(logo_w, logo_h)
        logo_clip = (
            ImageClip(np.array(logo_img), duration=clip.duration)
            .with_position((logo_x, logo_y))
        )

        final = CompositeVideoClip([clip, card_clip, logo_clip])
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
