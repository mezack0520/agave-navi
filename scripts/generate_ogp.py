#!/usr/bin/env python3
"""
Auto-generate OGP images for event pages that don't have one.
Creates 1200x630 dark cards with event name, date, and category tags.
Run as part of GitHub Actions or locally.
"""
import os
import glob
import re
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OGP_DIR = os.path.join(REPO_ROOT, "images", "ogp")
EVENTS_DIR = os.path.join(REPO_ROOT, "events")

# OGP image dimensions
WIDTH = 1200
HEIGHT = 630

# Colors
BG_COLOR = (17, 17, 17)
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (214, 48, 49)
SUBTLE_COLOR = (150, 150, 150)

def get_font(size, bold=False):
    """Try to load a Japanese font, fallback to default."""
    font_paths = [
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()

def extract_event_info(html_path):
    """Extract event name, date, and tags from HTML."""
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Extract title from h1
    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
    title = h1_match.group(1).strip() if h1_match else os.path.basename(html_path).replace('.html', '')

    # Extract date
    date_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日[^<]*)', html)
    date_str = date_match.group(1).strip() if date_match else ""

    # Extract tags
    tags = re.findall(r'<span class="tag">([^<]+)</span>', html)

    return title, date_str, tags

def wrap_text(draw, text, font, max_width):
    """Simple text wrapping for CJK text."""
    lines = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] > max_width and current_line:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    return lines

def generate_ogp(title, date_str, tags, output_path):
    """Generate a single OGP image."""
    img = Image.new('RGB', (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Draw subtle border
    draw.rectangle([0, 0, WIDTH-1, HEIGHT-1], outline=(40, 40, 40), width=2)

    # Draw accent line at top
    draw.rectangle([0, 0, WIDTH, 4], fill=ACCENT_COLOR)

    # Site name
    site_font = get_font(20)
    draw.text((60, 40), "AGAVE EVENT NAVI", fill=SUBTLE_COLOR, font=site_font)

    # Event title
    title_font = get_font(48, bold=True)
    padding = 60
    max_text_width = WIDTH - padding * 2
    lines = wrap_text(draw, title, title_font, max_text_width)

    y = 120
    for line in lines[:3]:  # Max 3 lines
        draw.text((padding, y), line, fill=TEXT_COLOR, font=title_font)
        y += 60

    # Date
    if date_str:
        date_font = get_font(24)
        draw.text((padding, y + 20), date_str, fill=SUBTLE_COLOR, font=date_font)
        y += 60

    # Tags
    if tags:
        tag_font = get_font(20)
        tag_x = padding
        tag_y = HEIGHT - 80
        for tag in tags[:4]:
            bbox = draw.textbbox((0, 0), tag, font=tag_font)
            tw = bbox[2] - bbox[0]
            # Draw tag pill
            draw.rounded_rectangle(
                [tag_x, tag_y, tag_x + tw + 20, tag_y + 32],
                radius=4, fill=(50, 50, 50)
            )
            draw.text((tag_x + 10, tag_y + 4), tag, fill=(200, 200, 200), font=tag_font)
            tag_x += tw + 30

    # Draw agave-navi.com at bottom right
    url_font = get_font(18)
    draw.text((WIDTH - 220, HEIGHT - 50), "agave-navi.com", fill=SUBTLE_COLOR, font=url_font)

    img.save(output_path, "JPEG", quality=90)

def main():
    os.makedirs(OGP_DIR, exist_ok=True)

    event_files = glob.glob(os.path.join(EVENTS_DIR, "*.html"))
    generated = 0

    for fp in sorted(event_files):
        slug = os.path.basename(fp).replace('.html', '')
        ogp_path = os.path.join(OGP_DIR, f"{slug}.jpg")

        # Skip if OGP already exists
        if os.path.exists(ogp_path):
            continue

        title, date_str, tags = extract_event_info(fp)
        generate_ogp(title, date_str, tags, ogp_path)
        generated += 1
        print(f"Generated: {slug}.jpg")

    if generated == 0:
        print("No new OGP images needed")
    else:
        print(f"\nGenerated {generated} OGP images")

if __name__ == "__main__":
    main()
