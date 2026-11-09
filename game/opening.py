"""Three pixel-art title cards drawn from the current game's art."""
from __future__ import annotations

import pico2d.pico2d as p


DURATION = 8.0
_LAMP_START = 2.6
_ALLEY_START = 5.2
_INK = (12, 19, 26)
_DUSK = (22, 33, 41)
_STEEL = (45, 61, 67)
_PAPER = (222, 211, 180)
_AMBER = (246, 173, 82)
_WHITE = (235, 237, 224)


def _box(x, y, width, height, color):
    if width > 0 and height > 0:
        p.draw_rectangle(x, y, x + width - 1, y + height - 1, *color, filled=True)


def _shape(points, color):
    """Fill a silhouette on a four-pixel grid."""
    edges = tuple(zip(points, points[1:] + points[:1]))
    for y in range(min(y for _, y in points), max(y for _, y in points), 4):
        center = y + 2
        crossings = sorted(
            ax + (bx - ax) * (center - ay) / (by - ay)
            for (ax, ay), (bx, by) in edges
            if (ay <= center < by) or (by <= center < ay)
        )
        for left, right in zip(crossings[::2], crossings[1::2]):
            x1, x2 = round(left / 4) * 4, round(right / 4) * 4
            if x2 > x1:
                _box(x1, y, x2 - x1, 4, color)


def _waybill(font):
    _box(64, 128, 1152, 464, _DUSK)
    _shape([(64, 220), (1216, 140), (1216, 312), (64, 388)], (30, 43, 49))
    _shape([(590, 224), (977, 196), (1124, 288), (739, 310)], (16, 25, 31))
    _shape([(602, 252), (941, 252), (941, 444), (602, 444)], (125, 75, 43))
    _shape([(941, 252), (1077, 323), (1077, 515), (941, 444)], (88, 53, 37))
    _shape([(602, 444), (941, 444), (1077, 515), (738, 515)], (166, 107, 62))
    _box(744, 252, 36, 192, (161, 108, 65))
    _shape([(744, 444), (780, 444), (916, 515), (880, 515)], (200, 140, 80))
    _box(637, 282, 230, 130, (87, 57, 43))
    _box(642, 289, 224, 125, _PAPER)
    _box(655, 394, 194, 5, _AMBER)
    font.draw(657, 376, "마지막 택배", _INK)
    font.draw(657, 349, "구역 07  /  야간 배송", _INK)
    for index, width in enumerate((3, 5, 2, 7, 3, 4, 2, 6, 3, 5, 2, 4)):
        _box(657 + index * 8, 305, width, 24, (51, 47, 40))
    font.draw(109, 423, "01 / 마지막 송장", _AMBER)
    font.draw(109, 379, "남은 배송은 한 건.", _WHITE)


def _courier(player_visual, foot_x, foot_y, lit):
    frame = player_visual.metadata["frames"]["front_right"][0]
    image = player_visual.images[frame.get("source", "atlas")]
    left, top, width, height = frame["clip_topleft"]
    pivot_x, pivot_y = frame["foot_pivot_topleft"]
    scale = 5
    if not lit:
        p.SDL_SetTextureColorMod(image.texture, 91, 105, 115)
    try:
        image.clip_draw(left, image.h - top - height, width, height,
                        foot_x + (left + width / 2 - pivot_x) * scale,
                        foot_y + (pivot_y - top - height / 2) * scale,
                        width * scale, height * scale)
    finally:
        if not lit:
            p.SDL_SetTextureColorMod(image.texture, 255, 255, 255)


def _chest_lamp(font, player_visual, local):
    _box(64, 128, 1152, 464, (17, 26, 33))
    _box(64, 128, 1152, 60, (20, 31, 38))
    _box(689, 149, 249, 16, (12, 19, 24))
    lit = local >= 0.8
    if lit:
        _shape([(604, 348), (835, 204), (1092, 348), (835, 492)], (48, 48, 42))
        _shape([(685, 348), (835, 247), (1006, 348), (835, 449)], (66, 60, 45))
        _shape([(751, 348), (835, 280), (941, 348), (835, 416)], (93, 75, 50))
    _courier(player_visual, 790, 157, lit)
    if lit:
        for x, y, width, height in ((831, 351, 13, 5), (827, 347, 4, 10),
                                     (849, 352, 10, 3), (834, 365, 4, 7)):
            _box(x, y, width, height, _AMBER)
        _box(834, 351, 6, 6, (255, 231, 158))
    font.draw(109, 423, "02 / 가슴등", _AMBER)
    font.draw(109, 379, "불을 켜고 골목으로.", _WHITE)


def _alley(font, zombie_metadata):
    _box(64, 128, 1152, 464, _DUSK)
    _box(724, 240, 262, 286, (51, 67, 69))
    _shape([(634, 128), (1152, 128), (948, 361), (793, 361)], (39, 51, 54))
    _shape([(64, 128), (634, 128), (793, 361), (793, 590), (64, 590)], (22, 35, 44))
    _shape([(1216, 128), (1152, 128), (948, 361), (948, 590), (1216, 590)], (19, 31, 39))
    for x, y, width in ((226, 313, 479), (300, 357, 462), (487, 407, 303), (1010, 407, 206)):
        _box(x, y, width, 4, (31, 46, 54))
    _box(809, 473, 98, 10, (100, 110, 88))
    _shape([(811, 473), (905, 473), (958, 275), (762, 275)], (65, 78, 70))
    _shape([(772, 244), (958, 244), (909, 283), (817, 283)], (29, 41, 44))
    for y, spans in zombie_metadata["facings"]["front"]["idle"]["opaque_rows"].items():
        for left, right in spans:
            _box(865 + (left - 40) * 2, 253 + (71 - int(y)) * 2,
                 (right - left + 1) * 2, 2, _INK)
    font.draw(109, 423, "03 / 골목 끝", _AMBER)
    font.draw(109, 379, "불빛 끝에 누군가 서 있다.", _WHITE)


def draw(elapsed, font, player_visual, zombie_metadata):
    p.SDL_SetRenderDrawColor(p.renderer, *_INK, 255)
    p.SDL_RenderClear(p.renderer)
    if elapsed < _LAMP_START:
        _waybill(font)
        cut = 1
    elif elapsed < _ALLEY_START:
        _chest_lamp(font, player_visual, elapsed - _LAMP_START)
        cut = 2
    else:
        _alley(font, zombie_metadata)
        cut = 3
    font.draw(64, 648, "DEAD ROUTE   /   LAST DELIVERY", _WHITE)
    font.draw(1138, 648, f"0{cut} / 03", _PAPER)
    _box(64, 98, 1152, 4, _STEEL)
    _box(64, 98, int(1152 * elapsed / DURATION), 4, _AMBER)
    font.draw(64, 63, "야간 배송 기록", _PAPER)
    font.draw(1008, 63, "Enter  건너뛰기", _WHITE)
