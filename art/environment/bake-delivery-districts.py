"""Bake depot ground textures from the same road data as the in-game maps."""
import argparse
from pathlib import Path
import random
import sys

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "game"))

from delivery_layouts import INTERIOR_DELIVERY, REPAIR_YARD, WAREHOUSE


def paint_shelter_floor(rect, room):
    left, bottom = room.x, room.y
    right, top = left + room.width, bottom + room.depth
    rect(left, bottom, right, top, (89, 93, 84))

    # Alternating linoleum squares with worn patches inside the shelter.
    tiles = random.Random(3214)
    tile_size = 32
    for column, x in enumerate(range(left, right, tile_size)):
        for row, y in enumerate(range(bottom, top, tile_size)):
            tone = tiles.choice((-4, -2, 0, 2, 4))
            color = (158, 158, 137) if (column + row) % 2 == 0 else (136, 145, 127)
            rect(x + 2, y + 3, min(x + tile_size, right), min(y + tile_size, top),
                 tuple(channel + tone for channel in color))
            if tiles.randrange(6) == 0:
                rect(x + 8, y + 9, min(x + 21, right), min(y + 14, top),
                     tuple(channel - 9 for channel in color))

    door_left, door_right = room.door_bounds
    rect(door_left, bottom - 19, door_right, bottom + 22, (100, 106, 108))
    rect(door_left, bottom - 5, door_right, bottom + 6, (163, 151, 112))
    for x in range(door_left + 8, door_right, 14):
        rect(x, bottom - 3, x + 4, bottom + 2, (104, 91, 64))


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

    room = layout.interior
    if room is not None:
        rect(644, 467, 1370, 1033, (124, 127, 114))
        rect(689, 495, 1326, 1000, (111, 116, 110))
        for x in range(692, 1326, 80):
            rect(x, 495, x + 2, 1000, (101, 107, 102))
        for y in range(498, 1000, 74):
            rect(689, y, 1326, y + 4, (101, 107, 102))
    elif warehouse:
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
    if room is not None:
        paint_shelter_floor(rect, room)
    elif warehouse:
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


def shelter_shelf():
    image = Image.new("RGB", (45, 30), (54, 47, 40))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 44, 9), fill=(133, 111, 79), outline=(75, 66, 54))
    draw.line((1, 3, 43, 3), fill=(149, 126, 88))
    draw.line((1, 8, 43, 8), fill=(96, 82, 64))
    for left, right in ((1, 3), (21, 23), (41, 43)):
        draw.rectangle((left, 10, right, 29), fill=(119, 97, 72))
        draw.line((left, 11, left, 28), fill=(149, 121, 83))
    for y in (10, 19, 27):
        draw.rectangle((0, y, 44, y + 1), fill=(137, 110, 77))
    for left, top, right, bottom, color in (
        (7, 14, 16, 18, (151, 128, 88)),
        (26, 13, 36, 18, (116, 120, 97)),
        (11, 23, 18, 26, (107, 115, 109)),
        (29, 22, 39, 26, (136, 115, 84)),
    ):
        draw.rectangle((left, top, right, bottom), fill=color)
        draw.point((left + 2, top + 1), fill=(172, 155, 118))
    return image


def save_or_check(path, image, check):
    if check:
        with Image.open(path) as actual:
            assert image.size == actual.size and image.tobytes() == actual.tobytes(), path
    else:
        image.save(path, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--shelter-only", action="store_true")
    options = parser.parse_args()
    scenes = (
        (REPAIR_YARD, dict(base=(118, 124, 104), asphalt=(105, 112, 117), alley=(141, 138, 123),
                           edge=(77, 84, 81), shoulder=(156, 148, 116), stripe=(192, 160, 83))),
        (WAREHOUSE, dict(base=(123, 136, 141), asphalt=(94, 106, 115), alley=(135, 149, 148),
                          edge=(70, 82, 90), shoulder=(165, 176, 174), stripe=(201, 207, 183), warehouse=True)),
        (INTERIOR_DELIVERY, dict(base=(108, 121, 107), asphalt=(89, 101, 108), alley=(129, 134, 123),
                                 edge=(63, 75, 77), shoulder=(143, 143, 117), stripe=(189, 168, 109))),
    )
    if options.shelter_only:
        scenes = scenes[-1:]
    for layout, palette in scenes:
        save_or_check(ROOT / "game/assets" / layout.ground_file, ground(layout, **palette), options.check)
    save_or_check(ROOT / "game/assets/neighborhood/shelter-shelf.png", shelter_shelf(), options.check)


if __name__ == "__main__":
    main()
