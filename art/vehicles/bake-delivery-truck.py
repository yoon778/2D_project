"""Bake the west-facing truck and courier handoff poses (Pillow, authoring only)."""
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "game/assets"
VEHICLES = ASSETS / "vehicles"
INK = (28, 28, 34)
RUBBER = (40, 42, 44)
CHARCOAL = (49, 61, 66)
BLUE = (72, 89, 92)
PALE_BLUE = (99, 117, 118)
PAPER = (179, 160, 119)
ROOF = (204, 185, 143)
OCHRE = (165, 90, 47)
RUST = (119, 75, 52)
SAND = (153, 133, 101)


def parcel(draw, x, y, size):
    """Draw an ochre box with a paper seam and three distinct planes."""
    height = max(4, size * 2 // 3)
    draw.polygon(((x, y + 2), (x + 4, y), (x + size, y + 2), (x + size, y + height),
                  (x + size - 3, y + height + 2), (x, y + height)), fill=(89, 52, 36))
    draw.polygon(((x + 1, y + 3), (x + 4, y + 1), (x + size - 2, y + 2), (x + size - 4, y + 4)),
                 fill=(233, 182, 110))
    draw.polygon(((x + 1, y + 4), (x + size - 4, y + 5), (x + size - 4, y + height),
                  (x + 1, y + height - 1)), fill=(190, 126, 68))
    draw.line((x + size - 3, y + 2, x + size - 3, y + height), fill=(148, 91, 50))
    draw.line((x + 5, y + 2, x + 7, y + 3), fill=(251, 221, 156))
    draw.line((x + 5, y + 5, x + 5, y + height - 1), fill=(211, 159, 92))


def truck_frame(door):
    image = Image.new("RGBA", (96, 64))
    draw = ImageDraw.Draw(image)
    # Tires and frame follow one ground line across all doors.
    draw.ellipse((6, 47, 93, 63), fill=(20, 23, 26, 115))
    draw.rounded_rectangle((5, 43, 92, 55), radius=3, fill=INK)
    for x in (19, 75):
        draw.ellipse((x - 7, 46, x + 7, 61), fill=INK)
        draw.ellipse((x - 5, 48, x + 5, 59), fill=RUBBER)
        draw.ellipse((x - 3, 50, x + 3, 56), fill=(105, 104, 93))
        draw.point((x - 1, 52), fill=(183, 175, 150))

    # Far side and roof read as distinct isometric planes in spite of the small cell.
    draw.polygon(((33, 18), (43, 7), (91, 7), (95, 11), (95, 43), (86, 51), (34, 51)), fill=INK)
    draw.polygon(((35, 18), (44, 8), (90, 8), (93, 11), (85, 20), (37, 20)), fill=ROOF)
    draw.polygon(((87, 21), (94, 12), (94, 42), (87, 48)), fill=SAND)
    draw.rectangle((35, 21, 85, 49), fill=PAPER)
    draw.line((35, 21, 85, 21), fill=(226, 210, 168))
    draw.line((36, 49, 85, 49), fill=(103, 89, 68))
    draw.line((89, 22, 89, 43), fill=(126, 108, 83))
    draw.line((92, 17, 92, 41), fill=(169, 147, 107))
    draw.rectangle((35, 31, 85, 35), fill=OCHRE)
    draw.polygon(((87, 31), (94, 24), (94, 29), (87, 36)), fill=RUST)
    draw.line((36, 35, 84, 35), fill=RUST)
    draw.rectangle((58, 24, 67, 30), fill=(106, 93, 75))
    draw.line((60, 25, 65, 25, 65, 28, 60, 28, 60, 25), fill=(246, 221, 162))
    for x, y in ((46, 14), (51, 16), (71, 10), (76, 13), (77, 17), (82, 25), (42, 46), (82, 38), (70, 44)):
        draw.line((x, y, x + 3, y), fill=(169, 151, 113))

    # Cabin slopes down towards the west, with a recessed charcoal windshield.
    draw.polygon(((3, 51), (3, 38), (8, 32), (18, 18), (33, 18), (40, 22), (39, 50),
                  (29, 54), (13, 57), (6, 55)), fill=INK)
    draw.polygon(((10, 32), (19, 19), (32, 19), (37, 23), (29, 26), (16, 28)), fill=PALE_BLUE)
    draw.polygon(((10, 33), (17, 28), (30, 27), (30, 36), (8, 40)), fill=CHARCOAL)
    draw.polygon(((14, 33), (19, 30), (26, 29), (26, 33), (12, 37)), fill=(99, 127, 127))
    draw.polygon(((5, 42), (13, 38), (31, 36), (37, 32), (37, 49), (28, 51), (7, 53)), fill=BLUE)
    draw.polygon(((29, 26), (37, 24), (37, 34), (30, 36)), fill=(48, 68, 78))
    draw.line((31, 28, 35, 27, 35, 31), fill=(103, 129, 133))
    draw.line((28, 38, 28, 50), fill=CHARCOAL)
    draw.line((30, 38, 33, 37), fill=(154, 153, 122))
    draw.rectangle((4, 44, 8, 47), fill=(224, 180, 105))
    draw.line((5, 44, 8, 44), fill=(251, 216, 143))
    draw.line((5, 51, 12, 53), fill=(129, 138, 131))
    draw.rectangle((87, 43, 91, 46), fill=(168, 66, 49))
    draw.point((87, 43), fill=(242, 122, 81))
    for x in (14, 75):
        draw.line((x, 49, x + 8, 49), fill=INK)

    if door == "cab":
        draw.polygon(((23, 20), (28, 19), (34, 22), (36, 29), (26, 30), (22, 27)), fill=INK)
        draw.polygon(((23, 19), (20, 17), (17, 11), (19, 9), (25, 12), (27, 20)), fill=BLUE, outline=INK)
        draw.line((19, 13, 24, 18), fill=PALE_BLUE)
        draw.polygon(((25, 24), (30, 23), (32, 25), (31, 28), (26, 28)), fill=(159, 113, 74))
    if door in ("cargo", "cargo_empty"):
        draw.polygon(((42, 11), (66, 11), (63, 23), (41, 23)), fill=INK)
        draw.line((42, 22, 63, 22), fill=(171, 123, 77))
        draw.polygon(((43, 11), (67, 11), (73, 4), (49, 4)), fill=ROOF, outline=INK)
        draw.line((48, 7, 68, 7), fill=(232, 209, 163))
        if door == "cargo":
            parcel(draw, 45, 11, 12)
    return image


def courier_atlas():
    out = Image.new("RGBA", (320, 240))
    ink, cloth, rim = (21, 20, 27), (50, 54, 72), (85, 93, 119)
    skin, skin_light = (233, 175, 137), (255, 207, 170)
    # Source cells share foot pivot (40, 72). Preserve both boots and the bat arm in every pose.
    poses = {
        "left": (((44, 31), (38, 38), (32, 42)), ((44, 31), (35, 37), (24, 37)), ((44, 31), (35, 40), (26, 43))),
        "right": (((44, 31), (49, 40), (53, 43)), ((44, 31), (51, 36), (61, 37)), ((44, 31), (49, 40), (58, 43))),
        "front": (((52, 32), (53, 40), (51, 44)), ((52, 32), (55, 43), (51, 49)), ((52, 32), (54, 44), (48, 49))),
    }
    for row, (facing, poses_for_side) in enumerate(poses.items()):
        path = ASSETS / "player" / f"r1-consistent-{facing}-20261105.png"
        complete = Image.open(path).convert("RGBA").crop((0, 160, 80, 240))
        base = Image.open(path.with_stem(path.stem + "-empty")).convert("RGBA").crop((0, 160, 80, 240))
        for index, points in enumerate(poses_for_side):
            pose = base.copy()
            if facing == "left":
                ImageDraw.Draw(pose).polygon(((31, 40), (36, 40), (38, 43), (37, 48), (30, 49)), fill=(0, 0, 0, 0))
            elif facing == "front":
                ImageDraw.Draw(pose).polygon(((49, 43), (55, 42), (57, 46), (54, 50), (48, 50)), fill=(0, 0, 0, 0))
            draw = ImageDraw.Draw(pose)
            draw.line(points, fill=ink, width=8, joint="curve")
            draw.line(points, fill=cloth, width=5, joint="curve")
            draw.line(tuple((x, y - 1) for x, y in points), fill=rim, width=2, joint="curve")
            hand_x, hand_y = points[-1]
            if index == 2:
                parcel(draw, hand_x - 6, hand_y - 9, 12)
            draw.ellipse((hand_x - 3, hand_y - 2, hand_x + 3, hand_y + 2), fill=skin, outline=ink)
            draw.line((hand_x - 1, hand_y - 1, hand_x + 1, hand_y - 1), fill=skin_light)
            out.alpha_composite(pose, (index * 80, row * 80))
        out.alpha_composite(complete, (240, row * 80))
    return out


if __name__ == "__main__":
    VEHICLES.mkdir(parents=True, exist_ok=True)
    truck = Image.new("RGBA", (384, 64))
    for index, door in enumerate(("closed", "cab", "cargo", "cargo_empty")):
        truck.alpha_composite(truck_frame(door), (index * 96, 0))
    truck.save(VEHICLES / "delivery-truck.png")
    courier_atlas().save(VEHICLES / "courier-pickup.png")
