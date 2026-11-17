"""Bake depot ground textures from the same road data as the in-game maps."""
import argparse
from pathlib import Path
import random
import sys

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "game"))

from delivery_layouts import REPAIR_YARD, WAREHOUSE


def ground(layout, *, base, asphalt, alley, edge, shoulder, stripe, warehouse=False):
    width, height = layout.world_size
    image = Image.new("RGB", (round(width / 2), round(height * .3)), base)
    draw = ImageDraw.Draw(image)
    rows = image.height

    def rect(left, bottom, right, top, fill):
        x, y = round(left / 2), rows - round(top * .3)
        draw.rectangle((x, y, max(x, round(right / 2) - 1), max(y, rows - round(bottom * .3) - 1)), fill=fill)

    def paint(routes, extra, color):
        for route in routes:
            half = route["width"] / 2 + extra
            for (ax, ay), (bx, by) in zip(route["points"], route["points"][1:]):
                if ax != bx and ay != by:
                    raise ValueError(f"District roads must follow the axes: {route}")
                rect(min(ax, bx) - half, min(ay, by) - half, max(ax, bx) + half, max(ay, by) + half, color)

    if warehouse:
        for x in range(100, width, 140):
            rect(x, 210, x + 2, height, (103, 116, 122))
        for y in range(215, height, 125):
            rect(0, y, width, y + 3, (103, 116, 122))
    else:
        rect(80, 228, 440, 1040, (125, 126, 107))
        rect(1030, 278, 1740, 690, (101, 111, 104))
        rect(1090, 691, 1685, 925, (127, 128, 111))

    main = layout.roads["main"]
    lanes = (*layout.roads["alleys"], layout.roads["main_detour"])
    for extra, color in ((13, shoulder), (4, edge)):
        paint((*main, *lanes), extra, color)
    paint(main, 0, asphalt)
    paint(lanes, 0, alley)

    # Keep the truck road and pedestrian markings aligned with the road centerline.
    road_y = main[0]["points"][0][1]
    for x in range(28, width - 24, 80):
        rect(x, road_y - 1, x + 34, road_y + 2, stripe)
    if warehouse:
        for x in (715, 745, 775, 805, 835, 865):
            rect(x, 838, x + 8, 863, stripe)
        for y in (879, 900, 921, 942, 963, 984):
            rect(1240, y, 1264, y + 6, (184, 176, 106))
    else:
        gate_x, gate_y = layout.gate_position
        for x in range(round(gate_x - 40), round(gate_x + 35), 14):
            rect(x, gate_y - 47, x + 7, gate_y - 34, stripe)
        for x in range(1140, 1310, 36):
            rect(x, 716, x + 3, 746, stripe)

    # Small, repeatable grains read as drawn pixel material under the lights.
    grain = random.Random(20261117)
    pixels = image.load()
    for y in range(rows):
        for x in range(image.width):
            adjustment = grain.choice((-6, -3, -1, 0, 0, 0, 1, 3, 5))
            pixels[x, y] = tuple(channel + adjustment for channel in pixels[x, y])
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()
    scenes = (
        (REPAIR_YARD, dict(base=(118, 124, 104), asphalt=(105, 112, 117), alley=(141, 138, 123),
                           edge=(77, 84, 81), shoulder=(156, 148, 116), stripe=(192, 160, 83))),
        (WAREHOUSE, dict(base=(123, 136, 141), asphalt=(94, 106, 115), alley=(135, 149, 148),
                          edge=(70, 82, 90), shoulder=(165, 176, 174), stripe=(201, 207, 183), warehouse=True)),
    )
    for layout, palette in scenes:
        path = ROOT / "game/assets" / layout.ground_file
        image = ground(layout, **palette)
        if options.check:
            with Image.open(path) as actual:
                assert image.size == actual.size and image.tobytes() == actual.tobytes(), path
        else:
            image.save(path, optimize=True)


if __name__ == "__main__":
    main()
