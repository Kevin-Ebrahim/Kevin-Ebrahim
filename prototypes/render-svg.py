"""Build the desktop prototype with the Koi Fetch demo and JetBrains Mono font.

Run: python prototypes/render-svg.py DEMO.gif FONT.ttf prototypes/profile.svg
"""

from collections import defaultdict
from itertools import accumulate, groupby
from pathlib import Path
import json
import runpy
import sys
from xml.etree import ElementTree as ET

from PIL import Image, ImageFont, ImageSequence

ROOT = Path(__file__).resolve().parents[1]
profile = runpy.run_path(str(ROOT / "scripts/render-profile.py"))


def paths_for_grid(pixels, columns, rows, background):
    """Combine adjacent same-colour dots into a single dashed horizontal stroke."""
    paths = defaultdict(list)
    for row, y in enumerate(rows):
        col = 0
        for colour, group in groupby(pixels[x, y] for x in columns):
            length = sum(1 for _ in group)
            if colour != background:
                paths[colour].append(f"M{col} {row}h{length}")
            col += length
    return {colour: "".join(parts) for colour, parts in paths.items()}


def animate_grid(parent, frames, starts, duration, **style):
    group = ET.SubElement(parent, "g", style)
    for colour in sorted(set().union(*frames)):
        values, times = [], []
        for start, frame in zip(starts, frames):
            path = frame.get(colour, "M0 0")
            if not values or path != values[-1]:
                values.append(path)
                times.append(f"{start / duration:.7f}".rstrip("0").rstrip("."))
        element = ET.SubElement(group, "path", stroke="#%02x%02x%02x" % colour, d=values[0])
        if len(values) > 1:
            ET.SubElement(element, "animate", attributeName="d", calcMode="discrete",
                          dur=f"{duration}ms", repeatCount="indefinite",
                          keyTimes=";".join(times), values=";".join(values))


def pond(svg, demo, x, y, width, height):
    if demo.size != (956, 516):
        raise ValueError("Expected the 956 × 516 Koi Fetch recording")
    group = ET.SubElement(svg, "svg", x=str(x), y=str(y), width=str(width), height=str(height),
                          viewBox="0 0 660 516", fill="none", preserveAspectRatio="none")
    # Each 11 × 22 terminal cell has two columns of four Braille dots.
    # The dash has a separate sample in the gap between adjacent Braille cells.
    columns = [x for x in range(660) if x % 11 in (2, 7)]
    rows = [y for y in range(516) if y % 22 in (1, 7, 13, 17)]
    dots, prey, delays = [], [], []
    original_water = demo.convert("RGB").getpixel((0, 0))
    for frame in ImageSequence.Iterator(demo):
        rgb = frame.convert("RGB")
        pixels = rgb.load()
        dots.append(paths_for_grid(pixels, columns, rows, original_water))
        prey.append(paths_for_grid(pixels, range(10, 660, 11), range(5, 516, 22), original_water))
        delays.append(frame.info["duration"])
    starts = list(accumulate(delays, initial=0))[:-1]
    animate_grid(group, dots, starts, sum(delays), transform="translate(.8 1.9) scale(5.5)",
                 **{"stroke-width": ".66", "stroke-dasharray": ".59 .41"})
    animate_grid(group, prey, starts, sum(delays), transform="translate(7.6 5.65) scale(11 22)",
                 **{"stroke-width": ".067", "stroke-dasharray": ".53 .47"})


def panel(svg, font, x, y, width, sections, titles):
    """Place the current desktop card's single-line fields on the same baselines."""
    label_width = max(font.getlength(label) for title in titles for label, _ in sections[title][1])
    value_x = x + round(label_width) + 27

    def text_at(left, baseline, colour, value):
        text = ET.SubElement(svg, "text", x=str(left), y=str(baseline), fill=colour,
                             textLength=f"{font.getlength(value):.2f}", lengthAdjust="spacingAndGlyphs")
        text.text = value

    for title in titles:
        accent, fields = sections[title]
        text_at(x, y + 18, profile["FOREGROUND"], title)
        ET.SubElement(svg, "path", d=f"M{x + round(font.getlength(title)) + 13} {y + 11.5}H{x + width - 5}",
                      stroke=profile["SECTION_LINE"])
        y += 26
        for label, value in fields:
            text_at(x + 5, y + 18, accent, label)
            text_at(value_x, y + 18, profile["FOREGROUND"], value)
            y += 23
        y += 13


def render(demo_file, font_file, output):
    font = ImageFont.truetype(font_file, 18)
    sections = profile["profile_sections"](json.loads((ROOT / "assets/github-stats.json").read_text()))
    left = ["Interests"]
    right = ["Profile", "Languages", "Projects", "GitHub Stats"]
    left_height = profile["details"](font, 480, sections, left).height
    right_height = profile["details"](font, 568, sections, right).height
    stack = 375 + 12 + left_height
    height = max(stack, right_height) + 36
    top = (height - stack) // 2
    svg = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width="1100", height=str(height),
                     viewBox=f"0 0 1100 {height}", role="img", **{"aria-labelledby": "title",
                     "font-family": "'JetBrains Mono','JetBrainsMono Nerd Font',monospace", "font-size": "18"})
    ET.SubElement(svg, "title", id="title").text = "Kevin Ebrahim’s profile with an animated Koi Fetch pond"
    ET.SubElement(svg, "rect", width="100%", height="100%", fill=profile["BACKGROUND"])
    with Image.open(demo_file) as demo:
        pond(svg, demo, 18, top, 480, 375)
    panel(svg, font, 18, top + 387, 480, sections, left)
    panel(svg, font, 514, 18, 568, sections, right)
    ET.indent(svg)
    ET.ElementTree(svg).write(output, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    render(*sys.argv[1:])
