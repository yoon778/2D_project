"""Cinematic opening and delivery endings with procedural fallback art."""
from __future__ import annotations

import ctypes
from pathlib import Path

import pico2d.pico2d as p


DURATION = 8.0
ENDING_DURATION = 4.0
FAILURE_DURATION = .85
FAILURE_MOTION_RATE = .30
_ALLEY_START = 2.6
_TITLE_START = 5.2
_INK = (12, 19, 26)
_DUSK = (22, 33, 41)
_PAPER = (222, 211, 180)
_AMBER = (246, 173, 82)
_WHITE = (235, 237, 224)
_TITLE = 54
_CAPTION = 25
_SMALL = 18


class CutsceneArt:
    def __init__(self, directory):
        self._images = {}
        self._fonts = {}
        self._labels = {}
        try:
            for name in ("waybill", "alley", "delivered"):
                path = Path(directory) / f"{name}.png"
                if path.is_file():
                    image = p.load_image(str(path))
                    if p.SDL_SetTextureScaleMode(image.texture, p.SDL_ScaleModeLinear) != 0:
                        raise RuntimeError(f"Cutscene texture scale mode failed: {p.SDL_GetError()!r}")
                    self._images[name] = image
            font_path = Path(__file__).resolve().parent / "assets/ui/NotoSansKR-Regular.ttf"
            for size in (_TITLE, _CAPTION, _SMALL):
                self._fonts[size] = p.load_font(str(font_path), size)
        except Exception:
            self.close()
            raise

    def close(self):
        self._labels.clear()
        self._images.clear()
        for font in self._fonts.values():
            p.TTF_CloseFont(font.font)
        self._fonts.clear()

    def frame(self, name, zoom, focal):
        image = self._images.get(name)
        if image is None:
            return False
        scale = max(p.canvas_width / image.w, p.canvas_height / image.h) * zoom
        width, height = round(p.canvas_width / scale), round(p.canvas_height / scale)
        x, y = round((image.w - width) * focal[0]), round((image.h - height) * focal[1])
        source = p.SDL_Rect(x, y, width, height)
        if p.SDL_RenderCopy(p.renderer, image.texture, ctypes.byref(source), None) != 0:
            raise RuntimeError(f"Cutscene render failed: {p.SDL_GetError()!r}")
        return True

    def text(self, text, x, y, size, color, opacity, align):
        key = (text, size, color)
        if key not in self._labels:
            font = self._fonts[size].font
            surface = p.TTF_RenderUTF8_Blended(font, text.encode("utf-8"), p.SDL_Color(*color, 255))
            if not surface:
                raise RuntimeError(f"Cutscene text rendering failed: {p.SDL_GetError()!r}")
            try:
                texture = p.SDL_CreateTextureFromSurface(p.renderer, surface)
            finally:
                p.SDL_FreeSurface(surface)
            if not texture:
                raise RuntimeError(f"Cutscene text texture failed: {p.SDL_GetError()!r}")
            self._labels[key] = p.Image(texture)
        image = self._labels[key]
        p.SDL_SetTextureAlphaMod(image.texture, round(255 * opacity))
        offset = image.w / 2 if align == "left" else -image.w / 2 if align == "right" else 0
        image.draw(x + offset, p.canvas_height - y)


def _ease(value):
    value = max(0.0, min(value, 1.0))
    return value * value * (3 - 2 * value)


def _caption(font, art, text, x, y, size, *, color=_WHITE, opacity=1.0, align="left"):
    if opacity <= 0:
        return
    if art is not None:
        art.text(text, x, y, size, color, opacity, align)
        return
    width = sum(9 if char.isascii() else 18 for char in text)
    offset = width / 2 if align == "center" else width if align == "right" else 0
    font.draw(x - offset, p.canvas_height - y, text, color)


def _wash(opacity):
    if opacity > 0:
        p.SDL_SetRenderDrawColor(p.renderer, 4, 7, 10, round(255 * opacity))
        p.SDL_RenderFillRect(p.renderer, None)


def _caption_shade():
    width, height = p.canvas_width, p.canvas_height
    top = height - 286
    vertices = (p.SDL_Vertex * 4)(
        p.SDL_Vertex(p.SDL_FPoint(0, top), p.SDL_Color(5, 9, 13, 0), p.SDL_FPoint()),
        p.SDL_Vertex(p.SDL_FPoint(width, top), p.SDL_Color(5, 9, 13, 0), p.SDL_FPoint()),
        p.SDL_Vertex(p.SDL_FPoint(width, height), p.SDL_Color(5, 9, 13, 236), p.SDL_FPoint()),
        p.SDL_Vertex(p.SDL_FPoint(0, height), p.SDL_Color(5, 9, 13, 236), p.SDL_FPoint()),
    )
    indices = (ctypes.c_int * 6)(0, 1, 2, 0, 2, 3)
    p.SDL_RenderGeometry(p.renderer, None, vertices, len(vertices), indices, len(indices))


def _clear():
    p.SDL_SetRenderDrawColor(p.renderer, *_INK, 255)
    p.SDL_RenderClear(p.renderer)


def _skip(font, art):
    _caption(font, art, "Enter  건너뛰기", p.canvas_width - 54, p.canvas_height - 39, _SMALL,
             color=_PAPER, align="right")


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
    font.draw(657, 349, "야간 배송", _INK)
    for index, width in enumerate((3, 5, 2, 7, 3, 4, 2, 6, 3, 5, 2, 4)):
        _box(657 + index * 8, 305, width, 24, (51, 47, 40))


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


def _chest_lamp(player_visual, local):
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


def _alley(zombie_metadata=None):
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
    if zombie_metadata is not None:
        for y, spans in zombie_metadata["facings"]["front"]["idle"]["opaque_rows"].items():
            for left, right in spans:
                _box(865 + (left - 40) * 2, 253 + (71 - int(y)) * 2,
                     (right - left + 1) * 2, 2, _INK)


def draw(elapsed, font, player_visual, zombie_metadata, art=None):
    _clear()
    width, height = p.canvas_width, p.canvas_height
    if elapsed < _ALLEY_START:
        progress = _ease(elapsed / _ALLEY_START)
        if art is None or not art.frame("waybill", 1.0 + .075 * progress, (.54, .56 - .06 * progress)):
            _waybill(font)
        _caption_shade()
        _caption(font, art, "오늘 밤, 마지막 택배를 맡았다.", 76, height - 106, _CAPTION,
                 opacity=_ease((elapsed - .3) / .35))
    else:
        local = elapsed - _ALLEY_START
        progress = _ease(local / (DURATION - _ALLEY_START))
        if art is None or not art.frame("alley", 1.0 + .09 * progress, (.49 + .08 * progress, .53)):
            if elapsed < _TITLE_START:
                _chest_lamp(player_visual, local)
            else:
                _alley(zombie_metadata)
        _caption_shade()
        if elapsed < _TITLE_START:
            _caption(font, art, "불을 켜고 골목으로.", 76, height - 106, _CAPTION,
                     opacity=_ease((local - .35) / .38) * _ease((_TITLE_START - elapsed) / .46))
        else:
            reveal = _ease((elapsed - _TITLE_START) / .58)
            _wash(.59 * reveal)
            _caption(font, art, "DEAD ROUTE", width // 2, round(height * .48), _TITLE,
                     opacity=reveal, align="center")
    _wash(max(1 - _ease(elapsed / .36),
              .94 * (1 - _ease(abs(elapsed - _ALLEY_START) / .23)),
              _ease((elapsed - (DURATION - .4)) / .4)))
    _skip(font, art)


def draw_ending(elapsed, font, art, world):
    _clear()
    height = p.canvas_height
    progress = _ease(elapsed / ENDING_DURATION)
    if art is None or not art.frame("delivered", 1.0 + .07 * progress, (.53, .58)):
        _waybill(font)
    _caption_shade()
    reveal = _ease((elapsed - .48) / .38)
    stops = " · ".join(stop.name for stop in world.contract.stops)
    _caption(font, art, "배달 완료", 76, height - 172, _TITLE, opacity=reveal)
    _caption(font, art, "배송을 무사히 마쳤다.", 79, height - 109, _CAPTION, opacity=reveal)
    _caption(font, art, stops, 79, height - 67, _SMALL, color=_PAPER, opacity=reveal)
    _wash(_ease((elapsed - (ENDING_DURATION - .42)) / .42))
    _skip(font, art)


def courier_fall_progress(elapsed):
    return _ease((elapsed - .06) / .58)


def draw_defeat_overlay(elapsed, font, art):
    impact = .24 * (1 - _ease(elapsed / .18))
    if impact > 0:
        p.SDL_SetRenderDrawColor(p.renderer, 94, 17, 18, round(255 * impact))
        p.SDL_RenderFillRect(p.renderer, None)
    _wash(_ease((elapsed - .51) / (FAILURE_DURATION - .51)))
    _skip(font, art)
