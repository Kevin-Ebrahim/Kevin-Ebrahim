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
# Snapshot of public profile data on 19 November 2026. Commit and line totals
# count distinct, author-linked commits on public default branches in Kevin's
# owned repos and repos with a credited commit contribution since signup.
SECTIONS = [
    ("kevin@omarchy", "#a7c080", [
        ("Name", "Kevin Ebrahim"),
        ("Field", "Computer Science · HPC"),
        ("OS", "Omarchy 4.5.0 · Arch Linux"),
        ("Uptime", "4y 7m 8d on GitHub"),
        ("Host", "Dell Latitude 9410"),
        ("Kernel", "Linux 7.2.15-1-omarchy"),
        ("IDE", "Neovim 0.12.6"),
        ("Languages.Programming", "Python, C++"),
        ("Languages.Computer", "HTML, CSS, TOML, YAML"),
        ("Languages.Real", "—"),
        ("Hobbies.Software", "Terminal apps, Linux customization"),
        ("Hobbies.Hardware", "HPC clusters"),
    ]),
    ("Contact", "#7fbbb3", [
        ("GitHub", "github.com/Kevin-Ebrahim"),
        ("Email.Personal", "—"),
        ("Email.Work", "—"),
        ("LinkedIn", "—"),
        ("Discord", "—"),
    ]),
    ("GitHub Stats · 19 Nov 2026", "#d699b6", [
        ("Repos", "11 public · 14 contributed to"),
        ("Stars", "0 received"),
        ("Commits", "810 on public default branches"),
        ("Followers", "9"),
        ("Lines of Code", "955,670 net"),
        ("Lines added / deleted", "+1,502,010 / −546,340"),
    ]),
]
ASSETS = Path(__file__).resolve().parents[1] / "assets"


def details(font, width):
    margin = 6
    row_height = font.size + 6
    # A mobile row can put its value on a second line. Measure the layout
    # first so longer handles and contact details fit in the finished card.
    rows = []
    y = 0
    for title, accent, fields in SECTIONS:
        if rows:
            y += 13
        rows.append((y, accent, title, None))
        y += row_height + 4
        previous_group = None
        for key, value in fields:
            group = key.partition(".")[0] if "." in key else ""
            if previous_group is not None and group != previous_group:
                y += 6
            previous_group = group
            right = width - margin
            label_width = font.getlength(key)
            if label_width + font.getlength(value) + 4 * font.getlength(" ") > right - margin:
                rows.append((y, accent, key, ""))
                y += row_height
                rows.append((y, accent, "", value))
            else:
                rows.append((y, accent, key, value))
            y += row_height

    panel = Image.new("RGB", (width, y), BACKGROUND)
    draw = ImageDraw.Draw(panel)
    for top, accent, label, value in rows:
        center = top + row_height // 2
        if value is None:
            draw.text((0, center), label, font=font, fill=FOREGROUND, anchor="lm")
            line_start = round(font.getlength(label)) + 13
            draw.line((line_start, center, width - margin, center), fill=SECTION_LINE)
            continue
        draw.text((margin, center), label, font=font, fill=accent, anchor="lm")
        draw.text((width - margin, center), value, font=font, fill=FOREGROUND, anchor="rm")
        if label and value:
            first = round(margin + font.getlength(label)) + 12
            last = round(width - margin - font.getlength(value)) - 10
            for x in range(first, last, 7):
                draw.ellipse((x, center + 2, x + 1, center + 3), fill=SECTION_LINE)
    return panel


def render(demo_file, font, mobile):
    with Image.open(demo_file) as demo:
        # The 956 × 516 upstream recording places its first text column at x=676.
        if demo.size != (956, 516):
            raise ValueError("The upstream demo layout has changed. Check the pond crop.")
        pond_box = (0, 0, 660, 516)
        if mobile:
            panel = details(font, 508)
            pond_size = (394, 308)
            base = Image.new("RGB", (540, 308 + panel.height + 18), BACKGROUND)
            pond_origin = ((base.width - pond_size[0]) // 2, 0)
            base.paste(panel, (16, 308))
        else:
            panel = details(font, 626)
            pond_size = (397, 310)
            base = Image.new("RGB", (1056, panel.height + 34), BACKGROUND)
            pond_origin = (4, (base.height - pond_size[1]) // 2)
            base.paste(panel, (414, 17))

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
    font = ImageFont.truetype(sys.argv[2] if len(sys.argv) > 2 else "JetBrainsMonoNerdFont-Regular.ttf", 18)
    for mobile in (False, True):
        render(sys.argv[1], font, mobile)
