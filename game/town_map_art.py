"""Printed street-map styling for the town's real roads and footprints."""

MAP_PAPER = (237, 233, 221)
MAP_ROAD = (233, 207, 151)
MAP_ALLEY = (255, 250, 236)
MAP_BUILDING = (170, 166, 156)
MAP_WRECK = (161, 84, 64)
MAP_LANDMARK = (122, 139, 134)

_GRID = (226, 221, 208)
_PARCEL = (230, 225, 210)
_VERGE = (221, 225, 205)
_PARCEL_EDGE = (211, 205, 188)
_ALLEY_EDGE = (188, 178, 151)
_ROAD_EDGE = (166, 145, 102)
_LANE = (199, 168, 113)
_ROOF_EDGE = (123, 122, 115)
_ROOF_LIGHT = (191, 187, 174)
_ROOF_SHADOW = (145, 140, 130)
_ROOF_LINE = (153, 150, 140)
_LANDMARK_EDGE = (76, 99, 95)
_CAR_EDGE = (122, 70, 56)
_CAR_GLASS = (224, 178, 147)
_FENCE = (132, 124, 101)
_BUILDING_TYPES = {"workshop", "west-house", "east-house", "shop", "bus-stop"}
_RESIDENCES = {"west-house", "east-house"}
_LANDMARKS = {"shop", "bus-stop"}
_CARS = {"abandoned-car", "parked-car"}


def _segments(roads):
    for road in roads:
        points = road["points"]
        for start, end in zip(points, points[1:]):
            yield start, end, road["width"]
        for point in road.get("junctions", ()):
            yield point, point, road["width"] + 10


def draw_base(rectangle, draw_line, bounds, scale, world_size, roads, walls):
    """Draw the static ground layers; mission markers are drawn by the caller."""
    left, bottom, right, top = bounds
    width, height = world_size

    def box(west, south, east, north, color, *, filled=True):
        west, east = max(0, west), min(width, east)
        south, north = max(0, south), min(height, north)
        if west < east and south < north:
            rectangle(left + west * scale, bottom + south * scale,
                      (east - west) * scale, (north - south) * scale, color, filled=filled)

    rectangle(left, bottom, right - left, top - bottom, MAP_PAPER)
    for x in range(600, int(width), 600):
        sx = left + x * scale
        draw_line(sx, bottom, sx, top, *_GRID)
    for y in range(600, int(height), 600):
        sy = bottom + y * scale
        draw_line(left, sy, right, sy, *_GRID)

    # Lot margins sit behind the roads and follow the actual building blocks.
    footprints = [(wall, getattr(wall, "texture", None)) for wall in walls]
    for wall, kind in footprints:
        if kind not in _BUILDING_TYPES:
            continue
        x, y = wall.x, wall.y
        east, north = x + wall.width, y + wall.depth
        margin = 13 if kind in _RESIDENCES else 8
        box(x - margin, y - margin, east + margin, north + margin,
            _VERGE if kind in _RESIDENCES else _PARCEL)
        box(x - margin, y - margin, east + margin, north + margin, _PARCEL_EDGE, filled=False)

    minor = (*roads["alleys"], roads["main_detour"])
    street_layers = ((tuple(_segments(minor)), MAP_ALLEY, _ALLEY_EDGE, 4),
                     (tuple(_segments(roads["main"])), MAP_ROAD, _ROAD_EDGE, 5))
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
