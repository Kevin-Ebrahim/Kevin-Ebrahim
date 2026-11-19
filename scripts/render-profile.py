"""Render the desktop and mobile SVGs from the classic Koi Fetch recording.

Run: python scripts/render-profile.py ../koi-fetch/docs/demo.gif
Optionally pass a monospace TTF path as the second argument.
"""

import json
from pathlib import Path
import sys
import textwrap
from xml.etree import ElementTree as ET

from PIL import Image, ImageFont

from pond import pond_art

BACKGROUND = "#2c343a"
FOREGROUND = "#d3c6aa"
SECTION_LINE = "#58666a"
SECTION_GAP = 16
ASSETS = Path(__file__).resolve().parents[1] / "assets"


def profile_sections(stats):
    streak = stats["longest_streak"]
    day_unit = "day" if streak == 1 else "days"
    return {
        "Profile": ("#a7c080", [
            ("Name", "Kevin Ebrahim"),
            ("Field", "Computer science"),
            ("University", "University of the Witwatersrand"),
            ("Editor", "Neovim"),
            ("OS", "Arch Linux"),
        ]),
        "Languages": ("#83c092", [
            ("Programming", "Python, C++, TypeScript, Bash"),
            ("Exploring", "Rust"),
        ]),
        "Interests": ("#dbbc7f", [
            ("Software", "Linux, FOSS, security"),
            ("Hardware", "Servers, networking, HPC"),
            ("Side quests", "Games, ricing, tinkering"),
        ]),
        "Projects": ("#7fbbb3", [
            ("Wits World", "Campus exploration game"),
            ("Specimen", "3D puzzle-platformer"),
            ("VitaQ", "Clinic booking and queues"),
            ("Miru", "Anime TUI"),
        ]),
        "GitHub stats": ("#d699b6", [
            ("Repos", f"{stats['public_repos']:,} public"),
            ("Commits", f"{stats['commits']:,}"),
            ("Followers", f"{stats['followers']:,}"),
            ("Longest streak", f"{streak:,} {day_unit}"),
            ("Active days", f"{stats['active_days_365']} in the past year"),
        ]),
    }


# Each field has a 20 × 20 stroke icon. Paths keep the terminal symbols
# visible in an embedded SVG, including on machines without a Nerd Font.
ICONS = {
    "Name": "M3 17c0-3 3-5 7-5s7 2 7 5 M13 6a3 3 0 1 1-6 0 3 3 0 1 1 6 0Z",
    "Field": "M6 5h8v10H6z M8 2v3m4-3v3M8 15v3m4-3v3M3 8h3m-3 4h3m8-4h3m-3 4h3",
    "University": "M1.5 7 10 3l8.5 4-8.5 4z M5 9v5q5 4 10 0V9m3-2v6",
    "Editor": "m3 13 9-9 4 4-9 9-5 1z M10 6l4 4",
    "OS": "M3 3h14v11H3z M1 17h18",
    "Programming": "m6 5-5 5 5 5m8-10 5 5-5 5m-3-12L8 17",
    "Exploring": "M18 10a8 8 0 1 1-16 0 8 8 0 1 1 16 0Z m-5-3-2 5-4 1 2-5z",
    "Software": "M1.5 3.5h17v13h-17z M2 7.5h16M5 5.5h.2m2 0h.2",
    "Hardware": "M2 3h16v6H2z M2 11h16v6H2z M5 6h1m2 0h1m-4 8h1m2 0h1",
    "Side quests": "M6 6h8q2.5 0 3.2 3l1.2 5q.6 4-2.4 2l-3-3H7l-3 3q-3 2-2.4-2l1.2-5Q3.5 6 6 6Z M6 8v4m-2-2h4m4-1h.3m1.8 2h.3",
    "Wits World": "m2 4 5-2 6 3 5-2v13l-5 2-6-3-5 2z M7 2v13m6-10v13",
    "Specimen": "m10 2 8 4.5v8L10 19l-8-4.5v-8z M2 6.5l8 4.5 8-4.5M10 11v8",
    "VitaQ": "M7.5 2.5h5v5h5v5h-5v5h-5v-5h-5v-5h5z",
    "Miru": "M2 3.5h16v13H2z M8 7l5 3-5 3z",
    "Repos": "M4 3h12v14H5.5a2 2 0 0 1 0-4H16 M4 15V3m3 3h5",
    "Commits": "M2 10h4m8 0h4M14 10a4 4 0 1 1-8 0 4 4 0 1 1 8 0Z",
    "Followers": "M11 6a3 3 0 1 1-6 0 3 3 0 1 1 6 0Z M2 17q0-5 6-5t6 5m2-11v6m-3-3h6",
    "Longest streak": "M11 1.5c1 5-4 6-3 10 2-1 3-2 4-5 4 3 5 6 3 9a6 6 0 0 1-11-2C3 9 8 7 11 1.5Z",
    "Active days": "M3 4h14v13H3z M6 2v4m8-4v4M3 8h14m-11 3h2m3 0h2m-7 3h2",
}


def text_at(parent, x, y, value, font, colour, **attrs):
    element = ET.SubElement(parent, "text", x=str(x), y=str(y), fill=colour,
                            textLength=f"{font.getlength(value):.2f}",
                            lengthAdjust="spacingAndGlyphs", **attrs)
    element.text = value


def column(sections, titles, width, font, min_section_height=0):
    """Draw open terminal frames with values aligned inside each section."""
    group = ET.Element("g")
    label_x = 51
    y = 0
    for title in titles:
        accent, fields = sections[title]
        key_width = max(font.getlength(f"{key}:") for key, _ in fields)
        value_x = label_x + round(key_width) + 12
        wrap_at = int((width - value_x - 6) / font.getlength("M"))
        section = ET.SubElement(group, "g")
        middle = width / 2
        gap = font.getlength(title) / 2 + 8
        header_y = y + 10
        border = f"M1 {header_y + 8}v-8H{middle-gap:.1f} M{middle+gap:.1f} {header_y}H{width-1}v8"
        text_at(section, middle, y + 16, title, font, "#9caeac", **{"text-anchor": "middle"})
        section_top = y
        y += 42
        rows = [(label, textwrap.wrap(value, width=wrap_at)) for label, value in fields]
        line_height = 25
        natural_bottom = y + line_height * sum(len(lines) for _, lines in rows) - 7
        bottom = max(natural_bottom, section_top + min_section_height - 1)
        extra = bottom - natural_bottom
        branches = []
        for index, (label, lines) in enumerate(rows):
            # Spread spare height between fields, keeping wrapped lines together.
            baseline = y + extra * index // max(1, len(rows) - 1)
            center_y = baseline - 6
            branches.append(center_y)
            ET.SubElement(section, "path", d=ICONS[label],
                          transform=f"translate(25 {center_y-9}) scale(.9)",
                          fill="none", stroke=accent, **{"stroke-width": "1.6",
                          "stroke-linecap": "round", "stroke-linejoin": "round"})
            text_at(section, label_x, baseline, f"{label}:", font, accent)
            for line_number, line in enumerate(lines):
                text_at(section, value_x, baseline + line_number * line_height, line, font, FOREGROUND)
            y += len(lines) * line_height
        tree = f"M18 {branches[0]}H8V{branches[-1]}"
        tree += "".join(f"M8 {center}h10" for center in branches[1:])
        ET.SubElement(section, "path", d=tree, fill="none", stroke=accent,
                      opacity=".76", **{"stroke-width": "1.5"})
        border += f" M1 {bottom-8}v8H{width-1}v-8"
        ET.SubElement(section, "path", d=border, fill="none", stroke=SECTION_LINE,
                      **{"stroke-width": "1.5"})
        y = bottom + 1 + SECTION_GAP
    return group, y - SECTION_GAP


def render(shapes, font, sections, mobile):
    if mobile:
        width = 500
        panel, panel_height = column(sections, sections, width - 32, font)
        panel_y = 316
        height = panel_y + panel_height + 16
        panels = [(panel, 16, panel_y)]
        pond_box = (53, 0, 394, 308)
    else:
        width = 1100
        profile, profile_height = column(sections, ["Profile", "Languages", "Projects"], 568, font)
        stats, stats_height = column(sections, ["GitHub stats"], 568, font)
        interests, interests_height = column(sections, ["Interests"], 480, font, min_section_height=stats_height)
        upper_height = max(375, profile_height)
        lower_y = 18 + upper_height + SECTION_GAP
        height = lower_y + max(interests_height, stats_height) + 18
        panels = [(profile, 514, 18), (interests, 18, lower_y), (stats, 514, lower_y)]
        pond_box = (18, 18 + (upper_height - 375) // 2, 480, 375)

    svg = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width=str(width), height=str(height),
                     viewBox=f"0 0 {width} {height}", role="img", **{"aria-labelledby": "title",
                     "font-family": "'JetBrains Mono','JetBrainsMono Nerd Font',monospace",
                     "font-size": str(font.size)})
    ET.SubElement(svg, "title", id="title").text = "Kevin Ebrahim’s profile with an animated Koi Fetch pond"
    ET.SubElement(svg, "rect", width="100%", height="100%", fill=BACKGROUND)
    px, py, pw, ph = pond_box
    pond = ET.SubElement(svg, "svg", x=str(px), y=str(py), width=str(pw), height=str(ph),
                         viewBox="0 0 660 516", preserveAspectRatio="none", **{"aria-hidden": "true"})
    pond.append(shapes)
    for panel, x, y in panels:
        panel.set("transform", f"translate({x} {y})")
        svg.append(panel)
    ET.indent(svg)
    filename = "profile-mobile.svg" if mobile else "profile.svg"
    ET.ElementTree(svg).write(ASSETS / filename, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    font = ImageFont.truetype(sys.argv[2] if len(sys.argv) > 2 else "JetBrainsMonoNerdFont-Regular.ttf", 18)
    sections = profile_sections(json.loads((ASSETS / "github-stats.json").read_text()))
    with Image.open(sys.argv[1]) as demo:
        shapes = pond_art(demo)
    for mobile in (False, True):
        render(shapes, font, sections, mobile)
