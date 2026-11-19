"""Render the README from koi-fetch's classic demo with Pillow.

Run: python scripts/render-profile.py ../koi-fetch/docs/demo.gif
Optionally pass a monospace TTF path as the second argument.
"""

from pathlib import Path
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageSequence

BACKGROUND = "#2c343a"
FOREGROUND = "#d3c6aa"
SECTION_LINE = "#58666a"
SECTIONS = [
    ("Profile", "#a7c080", [
        ("Name", "Kevin Ebrahim"),
        ("Focus", "Terminal apps and Linux tools"),
        ("Code", "Rust · Python · Go"),
    ]),
    ("Workstation", "#7fbbb3", [
        ("Machine", "Dell Latitude 9410"),
        ("Desktop", "Omarchy · Hyprland"),
        ("Tools", "kitty · Neovim"),
        ("Theme", "Everforest"),
    ]),
    ("Projects", "#d699b6", [
        ("koi-fetch", "Animated terminal koi pond"),
        ("miru", "Terminal anime browser"),
        ("gh-tune", "GitHub repository settings"),
    ]),
]
SWATCHES = ["#d3c6aa", "#a7c080", "#83c092", "#7fbbb3", "#dbbc7f", "#d699b6", "#e67e80"]
PANEL_WIDTH = 614
ASSETS = Path(__file__).resolve().parents[1] / "assets"


def details(font):
    height = sum(55 + len(rows) * 29 for _, _, rows in SECTIONS) - 11
    panel = Image.new("RGB", (PANEL_WIDTH, height), BACKGROUND)
    draw = ImageDraw.Draw(panel)
    y = 2
    for title, accent, rows in SECTIONS:
        middle = PANEL_WIDTH // 2
        gap = draw.textlength(title, font=font) / 2 + 12
        draw.line([(0, y + 19), (0, y + 11), (middle - gap, y + 11)], SECTION_LINE, 2)
        draw.line([(middle + gap, y + 11), (PANEL_WIDTH - 1, y + 11),
                   (PANEL_WIDTH - 1, y + 19)], SECTION_LINE, 2)
        draw.text((middle, y + 10), title, font=font, fill="#b1bdba", anchor="mm")
        y += 33
        for index, (label, value) in enumerate(rows):
            row_middle = y + 10
            draw.line((7, y - 5, 7, row_middle), accent, 1)
            if index + 1 < len(rows):
                draw.line((7, row_middle, 7, y + 25), accent, 1)
            draw.line((7, row_middle, 16, row_middle), accent, 1)
            draw.text((26, row_middle), label, font=font, fill=accent, anchor="lm")
            draw.text((172, row_middle), value, font=font, fill=FOREGROUND, anchor="lm")
            if label == "Theme":
                x = round(172 + draw.textlength(value, font=font)) + 18
                for swatch in SWATCHES:
                    draw.ellipse((x, row_middle - 5, x + 10, row_middle + 5), fill=swatch)
                    x += 15
            y += 29
        draw.line([(0, y - 1), (0, y + 6), (PANEL_WIDTH - 1, y + 6),
                   (PANEL_WIDTH - 1, y - 1)], SECTION_LINE, 2)
        y += 22
    return panel


def render(demo_file, panel, mobile):
    with Image.open(demo_file) as demo:
        # The 956 × 516 upstream recording places its first text column at x=676.
        if demo.size != (956, 516):
            raise ValueError("The upstream demo layout has changed. Check the pond crop.")
        pond_box = (0, 0, 660, 516)
        if mobile:
            pond_size = (500, 391)
            base = Image.new("RGB", (650, 391 + panel.height + 30), BACKGROUND)
            pond_origin = ((base.width - pond_size[0]) // 2, 0)
            base.paste(panel, (18, 396))
        else:
            pond_size = (514, 402)
            base = Image.new("RGB", (1176, panel.height + 42), BACKGROUND)
            pond_origin = (8, (base.height - pond_size[1]) // 2)
            base.paste(panel, (540, 21))

        original_water = Image.new("RGB", (660, 516), demo.convert("RGB").getpixel((0, 0)))
        water = Image.new("RGB", original_water.size, BACKGROUND)
        durations = []

        def frames():
            for frame in ImageSequence.Iterator(demo):
                durations.append(frame.info["duration"])
                pond = frame.convert("RGB").crop(pond_box)
                ink = ImageChops.difference(pond, original_water).convert("L").point([0] + [255] * 255)
                pond = Image.composite(pond, water, ink).resize(pond_size, Image.Resampling.BOX)
                card = base.copy()
                card.paste(pond, pond_origin)
                yield card

        sequence = frames()
        first = next(sequence)
        palette = first.quantize(colors=256)
        # Fix the palette across frames so stationary text keeps exactly the same pixels.
        rest = (card.quantize(palette=palette, dither=Image.Dither.NONE) for card in sequence)
        first = first.quantize(palette=palette, dither=Image.Dither.NONE)
        name = "profile-mobile.gif" if mobile else "profile.gif"
        first.save(ASSETS / name, save_all=True, append_images=rest, duration=durations,
                   loop=0, disposal=1, optimize=True)


if __name__ == "__main__":
    font = ImageFont.truetype(sys.argv[2] if len(sys.argv) > 2 else "JetBrainsMonoNerdFont-Regular.ttf", 21)
    panel = details(font)
    for mobile in (False, True):
        render(sys.argv[1], panel, mobile)
