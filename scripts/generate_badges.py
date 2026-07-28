#!/usr/bin/env python3
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BADGES_DIR = Path(__file__).resolve().parents[1] / "assets" / "badges"
BADGES_DIR.mkdir(parents=True, exist_ok=True)

def font(size, bold=True):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()

def make_badge(filename, bg_color, text_color, symbol, size=80):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Outer circle
    draw.ellipse([0, 0, size - 1, size - 1], fill=bg_color, outline=(255, 255, 255, 220), width=3)
    
    # Symbol
    f = font(int(size * 0.48), bold=True)
    left, top, right, bottom = draw.textbbox((0, 0), symbol, font=f)
    w = right - left
    h = bottom - top
    draw.text(((size - w) / 2 - left, (size - h) / 2 - top), symbol, fill=text_color, font=f)
    
    img.save(BADGES_DIR / filename)

if __name__ == "__main__":
    # Brilliant !! (Cyan circle)
    make_badge("brilliant.png", (38, 166, 154, 255), (255, 255, 255, 255), "!!")
    # Inaccuracy ?! (Yellow circle)
    make_badge("inaccuracy.png", (246, 191, 55, 255), (255, 255, 255, 255), "?!")
    # Mistake ? (Orange circle)
    make_badge("mistake.png", (230, 126, 34, 255), (255, 255, 255, 255), "?")
    # Winner crown circle (Green)
    make_badge("winner.png", (118, 187, 72, 255), (255, 255, 255, 255), "♔")
    # Loser red king checkmate circle (Red)
    make_badge("loser.png", (235, 64, 52, 255), (255, 255, 255, 255), "♚")
    print(f"Generated badge icons in {BADGES_DIR}")
