"""Aged printed street-map styling for the town's roads and footprints."""

MAP_PAPER = (233, 222, 195)
MAP_ROAD = (215, 177, 112)
MAP_ALLEY = (250, 239, 211)
MAP_BUILDING = (171, 160, 139)
MAP_WRECK = (153, 75, 54)
MAP_LANDMARK = (120, 130, 110)

MAP_ICON_ATLAS_SIZE = (576, 96)
MAP_ICON_CLIPS = {
    "west-house": (0, 0, 96, 96),
    "east-house": (96, 0, 96, 96),
    "workshop": (192, 0, 96, 96),
    "shop": (288, 0, 96, 96),
    "bus-stop": (384, 0, 96, 96),
    "parked-car": (480, 0, 96, 96),
    "abandoned-car": (480, 0, 96, 96),
}

_GRID = (225, 214, 187)
_PARCEL = (225, 215, 190)
_VERGE = (218, 218, 187)
_PARCEL_EDGE = (199, 188, 158)
_ALLEY_EDGE = (142, 116, 78)
_ROAD_EDGE = (128, 91, 51)
_LANE = (146, 113, 69)
_ROOF_EDGE = (121, 109, 91)
_ROOF_LIGHT = (191, 179, 156)
_ROOF_SHADOW = (145, 127, 101)
_ROOF_LINE = (150, 137, 115)
_LANDMARK_EDGE = (74, 86, 68)
_CAR_EDGE = (122, 70, 56)
_CAR_GLASS = (224, 178, 147)
_FENCE = (132, 124, 101)
_BUILDING_TYPES = {"workshop", "west-house", "east-house", "shop", "bus-stop"}
_RESIDENCES = {"west-house", "east-house"}
_LANDMARKS = {"shop", "bus-stop"}
_CARS = {"abandoned-car", "parked-car"}

_EDGE_TONES = ((0, (196, 172, 132)), (1, (211, 190, 150)), (3, (220, 201, 167)),
               (6, (227, 211, 178)), (11, (230, 218, 187)), (16, MAP_PAPER))
_CREASE_SHADE = (223, 209, 181)
_CREASE_LIGHT = (239, 230, 204)


def place_label(anchor, width, bounds, occupied, offset, *, height=23):
    """Find nearby paper for a caption without covering another marker."""
    x, y = anchor
    left, bottom, right, top = bounds
    for dx, dy in (offset, (12, -11), (-width - 12, -11), (12, 12),
                   (-width - 12, 12), (-width / 2, 17), (-width / 2, -40),
                   (24, 42), (-width - 24, 42), (24, -65), (-width - 24, -65)):
        west = min(max(left + 4, x + dx), right - width - 4)
        south = min(max(bottom + 4, y + dy), top - height - 4)
        east, north = west + width, south + height
        if all(east + 2 < a or west - 2 > c or north + 2 < b or south - 2 > d
               for a, b, c, d in occupied):
            occupied.append((west, south, east, north))
            return west, south
    return None


def _segments(roads):
    for road in roads:
        points = road["points"]
        for start, end in zip(points, points[1:]):
            yield start, end, road["width"]
        for point in road.get("junctions", ()):
            yield point, point, road["width"] + 10


def _draw_paper(rectangle, draw_line, bounds):
    left, bottom, right, top = bounds
    width, height = right - left, top - bottom
    for inset, tone in _EDGE_TONES:
        rectangle(left + inset, bottom + inset, width - 2 * inset, height - 2 * inset, tone)

    # The fold is part of the paper, beneath the printed streets and blocks.
    fold_x = round(left + width * .5)
    fold_y = round(bottom + height * .49)
    rectangle(fold_x - 2, bottom + 5, 2, height - 10, _CREASE_SHADE)
    rectangle(fold_x, bottom + 5, 2, height - 10, _CREASE_LIGHT)
    rectangle(left + 5, fold_y - 1, width - 10, 1, _CREASE_SHADE)
    rectangle(left + 5, fold_y, width - 10, 1, _CREASE_LIGHT)

    # Sparse, broken pale fibers along the rim soften the straight edge tones.
    for fraction, length, depth in ((.07, 13, 4), (.18, 9, 2), (.34, 16, 8), (.59, 11, 5),
                                     (.73, 15, 3), (.91, 8, 6)):
        x = round(left + width * fraction)
        y = round(bottom + height * fraction)
        draw_line(x, top - depth, x + length, top - depth, *_CREASE_LIGHT)
        draw_line(right - depth, y, right - depth, y + length, *_CREASE_LIGHT)
        draw_line(left + depth + 2, y, left + depth + 2, y + length, *_CREASE_SHADE)


def draw_base(rectangle, draw_line, bounds, scale, world_size, roads, walls, *, draw_sprite=None, min_road_edge=0):
    """Draw the static ground layers; mission markers are drawn by the caller."""
    left, bottom, right, top = bounds
    width, height = world_size

    def box(west, south, east, north, color, *, filled=True):
        west, east = max(0, west), min(width, east)
        south, north = max(0, south), min(height, north)
        if west < east and south < north:
            rectangle(left + west * scale, bottom + south * scale,
                      (east - west) * scale, (north - south) * scale, color, filled=filled)

    _draw_paper(rectangle, draw_line, bounds)
    for x in range(600, int(width), 600):
        sx = left + x * scale
        draw_line(sx, bottom, sx, top, *_GRID)
    for y in range(600, int(height), 600):
        sy = bottom + y * scale
        draw_line(left, sy, right, sy, *_GRID)

    # Lot margins sit beneath the street ink and the building illustrations.
    footprints = [(wall, getattr(wall, "texture", None)) for wall in walls]
    for wall, kind in footprints:
        if kind not in _BUILDING_TYPES:
            continue
        x, y = wall.x, wall.y
        east, north = x + wall.width, y + wall.depth
        margin = 13 if kind in _RESIDENCES else 8
        box(x - margin, y - margin, east + margin, north + margin,
            _VERGE if kind in _RESIDENCES else _PARCEL)
        if draw_sprite is None:
            box(x - margin, y - margin, east + margin, north + margin, _PARCEL_EDGE, filled=False)

    minor = (*roads["alleys"], roads["main_detour"])
    min_curb = min_road_edge / scale
    street_layers = ((tuple(_segments(minor)), MAP_ALLEY, _ALLEY_EDGE, max(4, min_curb)),
                     (tuple(_segments(roads["main"])), MAP_ROAD, _ROAD_EDGE, max(5, min_curb)))
    # Draw both outlines before either fill so junctions don't have seams.
    for casing in (True, False):
        for segments, fill, edge, curb in street_layers:
            for (ax, ay), (bx, by), road_width in segments:
                half = road_width / 2 + (curb if casing else 0)
                box(min(ax, bx) - half, min(ay, by) - half,
                    max(ax, bx) + half, max(ay, by) + half, edge if casing else fill)

    for (ax, ay), (bx, by), _ in street_layers[1][0]:
        if ay == by and ax != bx:
            y = bottom + ay * scale
            for x in range(int(min(ax, bx)) + 40, int(max(ax, bx)) - 55, 80):
                draw_line(left + x * scale, y, left + (x + 32) * scale, y, *_LANE)
        elif ax == bx and ay != by:
            x = left + ax * scale
            for y in range(int(min(ay, by)) + 40, int(max(ay, by)) - 55, 80):
                draw_line(x, bottom + y * scale, x, bottom + (y + 32) * scale, *_LANE)

    for wall, kind in footprints:
        x, y = wall.x, wall.y
        east, north = x + wall.width, y + wall.depth
        if draw_sprite is not None and kind in MAP_ICON_CLIPS:
            west, south = max(0, x), max(0, y)
            icon_east, icon_north = min(width, east), min(height, north)
            if west < icon_east and south < icon_north:
                icon_w = (icon_east - west) * scale
                icon_h = (icon_north - south) * scale
                inset_x = icon_w * .04 if kind in _RESIDENCES or kind == "workshop" else 0
                inset_y = icon_h * .03 if inset_x else 0
                if draw_sprite(kind, left + west * scale + inset_x, bottom + south * scale + inset_y,
                               icon_w - 2 * inset_x, icon_h - 2 * inset_y):
                    continue
        if kind in _CARS:
            box(x, y, east, north, MAP_WRECK)
            box(x, y, east, north, _CAR_EDGE, filled=False)
            box(x + wall.width * .39, y + 8, x + wall.width * .66, north - 8, _CAR_GLASS)
        elif kind in ("fence", "iron-gate"):
            box(x, y, east, north, _FENCE)
        else:
            landmark = kind in _LANDMARKS
            box(x + 5, y - 5, east + 5, north - 5, _ROOF_SHADOW)
            box(x, y, east, north, MAP_LANDMARK if landmark else MAP_BUILDING)
            box(x, y, east, north, _LANDMARK_EDGE if landmark else _ROOF_EDGE, filled=False)
            if wall.width * scale >= 15 and wall.depth * scale >= 10:
                box(x + 6, y + 6, east - 6, y + 12, _ROOF_LINE)
                box(x + 6, north - 12, east - 6, north - 6, _ROOF_LIGHT)
                if kind in _RESIDENCES:
                    ridge_y = bottom + (y + wall.depth * .53) * scale
                    draw_line(left + (x + 15) * scale, ridge_y,
                              left + (east - 15) * scale, ridge_y, *_ROOF_LINE)
