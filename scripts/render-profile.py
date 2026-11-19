"""Render the README from koi-fetch's classic demo with Pillow.

Run: python scripts/render-profile.py ../koi-fetch/docs/demo.gif
Optionally pass a monospace TTF path as the second argument.
"""

import json
from pathlib import Path
import sys
import textwrap

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageSequence

BACKGROUND = "#2c343a"
FOREGROUND = "#d3c6aa"
SECTION_LINE = "#58666a"
ASSETS = Path(__file__).resolve().parents[1] / "assets"


def profile_sections(stats):
    return {
        "kevin@omarchy": ("#a7c080", [
            ("Name", "Kevin Ebrahim"),
            ("Field", "Computer Science · HPC"),
            ("University", "Wits"),
            ("Interests", "Linux, systems, developer tools"),
            ("Community", "Wits HPC SIG"),
            ("Editor", "Neovim"),
            ("OS", "Omarchy · Arch Linux"),
        ]),
        "Languages": ("#a7c080", [
            ("Programming", "Python, C++, TypeScript"),
            ("Scripting", "Bash"),
            ("Learning", "Rust"),
        ]),
        "Interests": ("#dbbc7f", [
            ("Software", "CLI tools, Linux, automation"),
            ("Hardware", "Servers, networking, HPC"),
            ("Side Quests", "Game development, tinkering"),
        ]),
        "Currently": ("#dbbc7f", [
            ("Building", "Cerberus, a student HPC cluster"),
            ("Exploring", "Rust and systems programming"),
        ]),
        "Projects": ("#7fbbb3", [
            ("Wits World", "Location-based campus adventure"),
            ("Specimen", "3D puzzle-platformer · Three.js"),
            ("VitaQ", "Community Clinic Appointment & Queue System"),
            ("Miru", "Anime TUI · Rust"),
        ]),
        "Contact": ("#7fbbb3", [
            ("GitHub", "github.com/Kevin-Ebrahim"),
        ]),
        "GitHub Stats": ("#d699b6", [
            ("Repos", f"{stats['public_repos']:,} public"),
            ("Commits", f"{stats['commits']:,}"),
            ("Followers", f"{stats['followers']:,}"),
            ("Lines of Code", f"{stats['net_lines']:,} net"),
        ]),
    }


def details(font, width, sections, titles):
    margin = 5
    row_height = font.size + 5
    label_width = max(font.getlength(label) for title in titles for label, _ in sections[title][1])
    value_x = round(label_width) + margin + 22
    value_columns = int((width - value_x - margin) / font.getlength("M"))
    rows = []
    y = 0
    for title in titles:
        accent, fields = sections[title]
        if rows:
            y += 13
        rows.append((y, title, None, accent))
        y += row_height + 3
        for key, value in fields:
            for index, line in enumerate(textwrap.wrap(value, width=value_columns)):
                rows.append((y, key if index == 0 else "", line, accent))
                y += row_height

    panel = Image.new("RGB", (width, y), BACKGROUND)
    draw = ImageDraw.Draw(panel)
    for top, label, value, accent in rows:
        center = top + row_height // 2
        if value is None:
            draw.text((0, center), label, font=font, fill=FOREGROUND, anchor="lm")
            line_start = round(font.getlength(label)) + 13
            draw.line((line_start, center, width - margin, center), fill=SECTION_LINE)
        else:
            draw.text((margin, center), label, font=font, fill=accent, anchor="lm")
            draw.text((value_x, center), value, font=font, fill=FOREGROUND, anchor="lm")
    return panel


def render(demo_file, font, sections, mobile):
    with Image.open(demo_file) as demo:
        # The 956 × 516 upstream recording places its first text column at x=676.
        if demo.size != (956, 516):
            raise ValueError("The upstream demo layout has changed. Check the pond crop.")
        pond_box = (0, 0, 660, 516)
        if mobile:
            panel = details(font, 508, sections, sections.keys())
            pond_size = (394, 308)
            base = Image.new("RGB", (540, 308 + panel.height + 18), BACKGROUND)
            pond_origin = ((base.width - pond_size[0]) // 2, 0)
            base.paste(panel, (16, 308))
        else:
            left = details(font, 402, sections, ["Interests", "Currently"])
            right = details(font, 638, sections, ["kevin@omarchy", "Languages", "Projects", "Contact", "GitHub Stats"])
            pond_size = (408, 319)
            height = max(pond_size[1] + left.height + 12, right.height) + 36
            base = Image.new("RGB", (1100, height), BACKGROUND)
            upper_height = height - left.height - 36
            pond_origin = (14, (upper_height - pond_size[1]) // 2 + 9)
            base.paste(left, (18, height - left.height - 18))
            base.paste(right, (444, 18))

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
    stats = json.loads((ASSETS / "github-stats.json").read_text(encoding="utf-8"))
    sections = profile_sections(stats)
    for mobile in (False, True):
        render(sys.argv[1], font, sections, mobile)
