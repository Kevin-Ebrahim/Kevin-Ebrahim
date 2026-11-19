"""Encode the Koi Fetch recording as self-contained, animated SVG paths."""

from collections import defaultdict
from itertools import accumulate, groupby
from xml.etree import ElementTree as ET

from PIL import ImageSequence


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
        element = ET.SubElement(group, "path", color="#%02x%02x%02x" % colour, d=values[0])
        if len(values) > 1:
            ET.SubElement(element, "animate", attributeName="d", calcMode="discrete",
                          dur=f"{duration}ms", repeatCount="indefinite",
                          keyTimes=";".join(times), values=";".join(values))


def pond_art(demo):
    """Read the classic recording once for both card layouts."""
    if demo.size != (956, 516):
        raise ValueError("Expected the 956 × 516 Koi Fetch recording")
    group = ET.Element("g", fill="none", stroke="currentColor", attrib={"class": "pond"})
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
    return group
