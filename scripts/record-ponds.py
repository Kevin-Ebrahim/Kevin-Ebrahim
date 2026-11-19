"""Record both profile ponds using the Koi Fetch sprite and Braille renderer.

PYTHONPATH=../koi-fetch/src python scripts/record-ponds.py
Uses Pillow and koi-fetch at 4a6f4cb (the classic palette and sprite).
"""

from bisect import bisect_right
from itertools import accumulate
import math
from pathlib import Path
import random
import re
from typing import NamedTuple

from PIL import Image, ImageDraw
from koi_fetch import render
from koi_fetch.cli import load_sprite
from koi_fetch.theme import ThemeColours
from koi_fetch.world import NODES

ASSETS = Path(__file__).resolve().parents[1] / "assets"
COLUMNS = 60
SECONDS, FPS = 20, 18
FRAMES = SECONDS * FPS
TAU = math.tau
BACKGROUND = (44, 52, 58)
SAGE = ("#455334", "#596e40", "#72894f", "#8fa665", "#a7c080", "#c1d39a", "#dce6bc")
MINT = ("#254f41", "#356650", "#478166", "#64a27e", "#83c092", "#a2d6ad", "#c5e9d0")
ANSI_RUN = re.compile(r"\x1b\[(\d+)m([^\x1b]*)")
DOT_BITS = ((0, 3), (1, 4), (2, 5), (6, 7))
GLYPHS = {
    chr(0x2800 + mask): [(2 + dx * 5, y) for y, bits in zip((1, 7, 13, 17), DOT_BITS)
                         for dx, bit in enumerate(bits) if mask & (1 << bit)]
    for mask in range(256)
}


class Koi(NamedTuple):
    length: int
    start: float
    beats: int
    stroke_cycle: int
    course: tuple


# Closed guide curves in pond-relative coordinates, in gold, red, blue, sage and mint order.
SCHOOL = (
    Koi(44, .771, 16, 4, ((.17, .10), (.72, .03), (.94, .21), (.59, .46), (.85, .73),
                          (.72, .95), (.24, .94), (.08, .66), (.37, .42), (.09, .26))),
    Koi(38, .750, 15, 5, ((.16, .25), (.13, .54), (.08, .83), (.35, .95), (.52, .68),
                          (.86, .51), (.93, .24), (.72, .06), (.36, .08))),
    Koi(33, .271, 18, 3, ((.23, .91), (.06, .66), (.24, .47), (.68, .32), (.88, .12),
                          (.66, .04), (.37, .19), (.54, .49), (.91, .72), (.77, .94))),
    Koi(39, .521, 20, 4, ((.12, .19), (.34, .04), (.70, .12), (.84, .39), (.54, .64),
                          (.49, .91), (.19, .96), (.08, .73), (.31, .46))),
    Koi(35, .000, 15, 5, ((.74, .94), (.93, .68), (.69, .50), (.39, .37), (.16, .12),
                          (.44, .04), (.82, .17), (.91, .40), (.49, .65), (.36, .89))),
)


class SwimPath:
    """Arc-length lookup lets the spine follow a closed spline at fixed spacing."""

    def __init__(self, course, width, height):
        self.points = []
        for i in range(len(course)):
            a, b, c, d = [course[(i + j) % len(course)] for j in (-1, 0, 1, 2)]
            for step in range(64):
                t = step / 64
                weights = ((1-t)**3, 3*t**3 - 6*t*t + 4, -3*t**3 + 3*t*t + 3*t + 1, t**3)
                self.points.append(tuple(
                    size * sum(w * p[axis] for w, p in zip(weights, (a, b, c, d))) / 6
                    for axis, size in enumerate((width, height))
                ))
        self.points.append(self.points[0])
        self.distances = list(accumulate(map(math.dist, self.points, self.points[1:]), initial=0.0))
        self.length = self.distances[-1]

    def at(self, distance):
        distance %= self.length
        i = bisect_right(self.distances, distance) - 1
        a, b = self.points[i:i + 2]
        t = (distance - self.distances[i]) / (self.distances[i + 1] - self.distances[i])
        return tuple(x + (y - x) * t for x, y in zip(a, b))


def fish_pose(path, index, fraction, size):
    koi = SCHOOL[index]
    angle = TAU * fraction
    # Vary the pace independently while completing exactly one lap.
    phase = angle * (2 + index % 2) + index
    lap = fraction + koi.start + .065 * math.sin(phase) / TAU
    speed = path.length / SECONDS * (1 + .065 * (2 + index % 2) * math.cos(phase))
    length = koi.length * size
    spacing = length / (NODES - 1)
    nodes = [path.at(lap * path.length - j * spacing) for j in range(NODES)]
    a, b, c = nodes[:3]
    turn = math.atan2(a[1] - b[1], a[0] - b[0]) - math.atan2(b[1] - c[1], b[0] - c[0])
    # The beat count is a multiple of the stroke/glide cycle, so even the
    # tips of the two tail lobes have continuous motion through the seam.
    return dict(nodes=nodes, length=length, speed=speed, turn=math.remainder(turn, TAU) * speed / spacing,
                phase=koi.beats * angle + .4 * math.sin(phase) + index, strokes=koi.stroke_cycle - 1, glide=1)


def minnows(angle, height):
    rng = random.Random(32)
    food = []
    for school in range(5):
        phase = angle + school * TAU / 5
        x = COLUMNS * (1 + .64 * math.cos(phase + .4 * math.sin(2 * phase)))
        y = 2 * height * (1 + .68 * math.sin(phase + school))
        for _ in range(8):
            offset = rng.uniform(0, TAU)
            food.append(dict(x=x + rng.uniform(-8, 8) + 2 * math.sin(2 * angle + offset),
                             y=y + rng.uniform(-6, 6) + math.cos(3 * angle + offset),
                             depth=rng.random(), glint=.3 + .2 * math.sin(2 * angle + offset), alive=True))
    return food


def palettes():
    classic = [[tuple(map(int, code.split(";")[2:])) for code in ramp[1:]]
               for ramp in ThemeColours("classic").colours]
    greens = [[tuple(bytes.fromhex(hexcode[1:])) for hexcode in ramp] for ramp in (SAGE, MINT)]
    palette = [BACKGROUND, *dict.fromkeys(rgb for ramp in classic + greens for rgb in ramp)]
    codes = [(0, *(palette.index(rgb) for rgb in ramp)) for ramp in classic + greens]
    # Koi Fetch paints three fish colours per pass. In the second pass only
    # the two green fish contribute ink; the pond already contains the water.
    clear = (0,) * 8
    return palette, codes[:5], [*codes[5:], clear, clear, clear]


def paint(draw, lines):
    for row, line in enumerate(lines):
        col = 0
        for code, run in ANSI_RUN.findall(line):
            ink = int(code)
            start = col
            col += len(run)
            if not ink:
                continue
            for index, char in enumerate(run, start):
                left, top = 11 * index, 22 * row
                if char == "-":
                    draw.line((left + 5, top + 5, left + 10, top + 5), fill=ink)
                for dx, dy in GLYPHS.get(char, ()):
                    x, y = left + dx, top + dy
                    draw.rectangle((x - 1, y - 1, x + 1, y + 1), fill=ink)


def record(filename, height):
    rows = math.ceil(height / 22)
    paths = [SwimPath(koi.course, 2 * COLUMNS, height / 5.5) for koi in SCHOOL]
    sprite = load_sprite()
    palette, classic, greens = palettes()
    gif_palette = bytes(channel for rgb in palette for channel in rgb)
    def frame_at(fraction):
        angle = TAU * fraction
        poses = [fish_pose(path, i, fraction, min(1, rows / 31)) for i, path in enumerate(paths)]
        image = Image.new("P", (COLUMNS * 11, height))
        image.putpalette(gif_palette)
        draw = ImageDraw.Draw(image)
        # Native water glints run at .8 rad/s. Fit three cycles into the recording.
        for fish, inks, food in [(poses[:3], classic, minnows(angle, rows)), (poses[3:], greens, [])]:
            for colour, swimmer in enumerate(fish):
                swimmer["colour"] = colour
            paint(draw, render.pond(3 * angle / .8, sprite, fish, food, inks, COLUMNS, rows))
        return image

    # GIF delays use centiseconds. Sample [0, 1) so the first pose is never held twice.
    frames = [frame_at(n / FRAMES) for n in range(FRAMES)]
    if frames[0].tobytes() != frame_at(1).tobytes() or frames[-1].tobytes() != frame_at(-1 / FRAMES).tobytes():
        raise ValueError(f"{filename} does not join continuously at the loop boundary")
    boundaries = [round(n * 100 / FPS) for n in range(FRAMES + 1)]
    delays = [10 * (b - a) for a, b in zip(boundaries, boundaries[1:])]
    frames[0].save(ASSETS / filename, save_all=True, append_images=frames[1:],
                   duration=delays, loop=0, disposal=1, optimize=True)


if __name__ == "__main__":
    record("koi-portrait.gif", 1078)
    record("koi-landscape.gif", 516)
