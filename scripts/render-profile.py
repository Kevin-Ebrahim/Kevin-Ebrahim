"""Render the desktop and mobile SVGs from portrait and landscape Koi Fetch recordings.

Run: python scripts/render-profile.py [landscape.gif] [monospace.ttf]
The checked-in landscape recording is used by default.
"""

import json
from pathlib import Path
import sys
import textwrap
from typing import NamedTuple
from xml.etree import ElementTree as ET

from PIL import Image, ImageFont

from pond import pond_art

BACKGROUND = "#2c343a"
FOREGROUND = "#d3c6aa"
SECTION_LINE = "#58666a"
SECTION_GAP = 16
ASSETS = Path(__file__).resolve().parents[1] / "assets"
LIGHT_STYLE = Path(__file__).with_name("profile-light.css")


class LineChanges(NamedTuple):
    additions: int
    deletions: int


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
            ("Lines of code", LineChanges(stats["additions"], stats["deletions"])),
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
    "Lines of code": "m6 6-4 4 4 4m8-8 4 4-4 4m-3-11L8 17",
}


def text_at(parent, x, y, value, font, colour, **attrs):
    element = ET.SubElement(parent, "text", x=str(x), y=str(y), fill=colour,
                            textLength=f"{font.getlength(value):.2f}",
                            lengthAdjust="spacingAndGlyphs", **attrs)
    element.text = value
    return element


def draw_line_changes(section, x, y, width, font, changes):
    net = f"{changes.additions - changes.deletions:,}"
    added, deleted = f"+{changes.additions:,}", f"−{changes.deletions:,}"
    detail = f"({added}, {deleted})"
    prefix = net + " "
    if x + font.getlength(prefix + detail) > width - 8:
        text_at(section, x, y, net, font, FOREGROUND, **{"class": "value"})
        y += 25
        x = min(x, width - 8 - font.getlength(detail))
        prefix = ""
    text = text_at(section, x, y, prefix + detail, font, FOREGROUND, **{"class": "value"})
    text.text = prefix + "("
    for value, style, colour, suffix in [(added, "added", "#a7c080", ", "), (deleted, "deleted", "#e67e80", ")")]:
        span = ET.SubElement(text, "tspan", fill=colour, attrib={"class": style})
        span.text, span.tail = value, suffix
    return y + 25


def column(sections, width, font):
    """Draw open terminal frames with values aligned inside each section."""
    group = ET.Element("g")
    label_x = 51
    y = 0
    for title, (accent, fields) in sections.items():
        key_width = max(font.getlength(f"{key}:") for key, _ in fields)
        value_x = label_x + round(key_width) + 12
        wrap_at = int((width - value_x - 6) / font.getlength("M"))
        section = ET.SubElement(group, "g", color=accent, attrib={"class": title.lower().replace(" ", "-")})
        if title == "GitHub stats":
            ET.SubElement(section, "desc").text = (
                "Commits are unique authored commits "
                "on the public default branches scanned. Lines of code shows net lines "
                "(additions minus deletions) in those commits, excluding merges."
            )
        middle = width / 2
        gap = font.getlength(title) / 2 + 8
        header_y = y + 10
        border = f"M1 {header_y + 8}v-8H{middle-gap:.1f} M{middle+gap:.1f} {header_y}H{width-1}v8"
        text_at(section, middle, y + 16, title, font, "#9caeac", **{"class": "heading", "text-anchor": "middle"})
        y += 42
        branches = []
        for label, value in fields:
            center_y = y - 6
            branches.append(center_y)
            ET.SubElement(section, "path", d=ICONS[label],
                          transform=f"translate(25 {center_y-9}) scale(.9)",
                          fill="none", stroke="currentColor", **{"stroke-width": "1.6",
                          "stroke-linecap": "round", "stroke-linejoin": "round"})
            text_at(section, label_x, y, f"{label}:", font, "currentColor")
            if isinstance(value, LineChanges):
                y = draw_line_changes(section, value_x, y, width, font, value)
            else:
                for line in textwrap.wrap(value, width=wrap_at):
                    text_at(section, value_x, y, line, font, FOREGROUND, **{"class": "value"})
                    y += 25
        tree = f"M18 {branches[0]}H8V{branches[-1]}"
        tree += "".join(f"M8 {center}h10" for center in branches[1:])
        ET.SubElement(section, "path", d=tree, fill="none", stroke="currentColor",
                      opacity=".76", **{"stroke-width": "1.5"})
        bottom = y - 7
        border += f" M1 {bottom-8}v8H{width-1}v-8"
        ET.SubElement(section, "path", d=border, fill="none", stroke=SECTION_LINE,
                      **{"class": "frame", "stroke-width": "1.5"})
        y = bottom + 1 + SECTION_GAP
    return group, y - SECTION_GAP


def render(recording, font, sections, mobile):
    if mobile:
        width = 500
        panel, panel_height = column(sections, width - 32, font)
        panel_x, panel_y = 16, 316
        height = panel_y + panel_height + 16
        pond_box = (53, 0, 394, 308)
    else:
        width = 1100
        panel, panel_height = column(sections, 568, font)
        height = panel_height + 36
        panel_x, panel_y = 514, 18
        pond_box = (18, 0, 480, height)

    svg = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width=str(width), height=str(height),
                     viewBox=f"0 0 {width} {height}", role="img", **{"aria-labelledby": "title",
                     "font-family": "'JetBrains Mono','JetBrainsMono Nerd Font',monospace",
                     "font-size": str(font.size)})
    ET.SubElement(svg, "title", id="title").text = "Kevin Ebrahim’s profile with an animated Koi Fetch pond"
    ET.SubElement(svg, "style").text = LIGHT_STYLE.read_text(encoding="utf-8")
    ET.SubElement(svg, "rect", width="100%", height="100%", fill=BACKGROUND, attrib={"class": "canvas"})
    px, py, pw, ph = pond_box
    pond = ET.SubElement(svg, "svg", x=str(px), y=str(py), width=str(pw), height=str(ph),
                         viewBox=f"0 0 660 {recording.height}",
                         preserveAspectRatio="none" if mobile else "xMidYMid meet", **{"aria-hidden": "true"})
    pond.append(pond_art(recording))
    panel.set("transform", f"translate({panel_x} {panel_y})")
    svg.append(panel)
    ET.indent(svg)
    filename = "profile-mobile.svg" if mobile else "profile.svg"
    ET.ElementTree(svg).write(ASSETS / filename, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    font = ImageFont.truetype(sys.argv[2] if len(sys.argv) > 2 else "JetBrainsMonoNerdFont-Regular.ttf", 18)
    sections = profile_sections(json.loads((ASSETS / "github-stats.json").read_text()))
    with Image.open(ASSETS / "koi-portrait.gif") as portrait:
        render(portrait, font, sections, mobile=False)
    with Image.open(sys.argv[1] if len(sys.argv) > 1 else ASSETS / "koi-landscape.gif") as landscape:
        render(landscape, font, sections, mobile=True)
