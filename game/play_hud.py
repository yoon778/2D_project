"""Native-resolution HUD for an active delivery."""
import ctypes

import pico2d.pico2d as p

if __package__:
    from .combat import MAX_STAMINA
else:
    from combat import MAX_STAMINA


TEXT = (239, 242, 233)
MUTED = (175, 190, 191)
TEAL = (112, 231, 203)
AMBER = (255, 192, 109)
HEALTH = (245, 153, 131)
PANEL = (14, 22, 27, 233)
BORDER = (93, 114, 118, 180)
TRACK = (45, 58, 63, 255)
KEYCAP = (40, 59, 63, 255)
KEY_BORDER = (102, 131, 134, 230)
MAX_HEALTH = 3
MARGIN = 24
SMALL = 15
BODY = 18
TITLE = 24


def fill(x, y, width, height, color):
    p.SDL_SetRenderDrawColor(p.renderer, *color)
    bounds = p.SDL_Rect(x, y, width, height)
    p.SDL_RenderFillRect(p.renderer, ctypes.byref(bounds))


def panel(x, y, width, height, background=PANEL, outline=BORDER):
    fill(x, y, width, height, background)
    p.SDL_SetRenderDrawColor(p.renderer, *outline)
    bounds = p.SDL_Rect(x, y, width, height)
    p.SDL_RenderDrawRect(p.renderer, ctypes.byref(bounds))


class PlayHUD:
    def __init__(self, font_path, width, height):
        self.width, self.height = width, height
        self._fonts = {}
        self._labels = {}
        try:
            for size in (SMALL, BODY, TITLE):
                font = p.TTF_OpenFont(str(font_path).encode("utf-8"), size)
                if not font:
                    raise OSError(f"HUD font could not load: {font_path}")
                self._fonts[size] = font
        except Exception:
            self.close()
            raise

    def close(self):
        for texture, _, _ in self._labels.values():
            p.SDL_DestroyTexture(texture)
        self._labels.clear()
        for font in self._fonts.values():
            p.TTF_CloseFont(font)
        self._fonts.clear()

    def _label(self, text, size, color):
        # The HUD's text comes from a fixed set of labels and four HP values.
        key = (text, size, color)
        if key not in self._labels:
            surface = p.TTF_RenderUTF8_Blended(self._fonts[size], text.encode("utf-8"), p.SDL_Color(*color, 255))
            if not surface:
                raise OSError(f"HUD text could not render: {text}")
            try:
                width, height = surface.contents.w, surface.contents.h
                texture = p.SDL_CreateTextureFromSurface(p.renderer, surface)
            finally:
                p.SDL_FreeSurface(surface)
            if not texture:
                raise OSError(f"HUD text could not create texture: {text}")
            self._labels[key] = texture, width, height
        return self._labels[key]

    def _text(self, text, x, y, size, color=TEXT, *, align="left"):
        texture, width, height = self._label(text, size, color)
        if align == "right":
            x -= width
        elif align == "center":
            x -= width // 2
        bounds = p.SDL_Rect(x, y - height // 2, width, height)
        p.SDL_RenderCopy(p.renderer, texture, None, ctypes.byref(bounds))

    def _vitals(self, world):
        x, y = MARGIN, MARGIN
        panel(x, y, 208, 108)
        self._text("체력", x + 16, y + 21, BODY)
        self._text(f"{world.player_hp} / {MAX_HEALTH}", x + 192, y + 21, BODY, align="right")
        for index in range(MAX_HEALTH):
            color = (*HEALTH, 255) if index < world.player_hp else TRACK
            fill(x + 16 + 60 * index, y + 38, 56, 9, color)
        self._text("스태미나", x + 16, y + 70, SMALL, MUTED)
        fill(x + 16, y + 86, 176, 7, TRACK)
        stamina = round(176 * world.stamina / MAX_STAMINA)
        if stamina:
            fill(x + 16, y + 86, stamina, 7, (*TEAL, 255))

    def _objective(self, world):
        x, y = self.width - MARGIN - 246, MARGIN
        panel(x, y, 246, 108)
        self._text("다음 배달 목표", x + 16, y + 23, SMALL, MUTED)
        panel(x + 169, y + 13, 22, 20, KEYCAP, KEY_BORDER)
        self._text("M", x + 180, y + 23, SMALL, align="center")
        self._text("지도", x + 199, y + 23, SMALL, MUTED)
        waiting = world.parcel == "waiting"
        self._text("택배 수령" if waiting else "택배 전달", x + 16, y + 57, TITLE, TEAL)
        self._text("남서쪽 거점" if waiting else world.contract.name, x + 16, y + 85, BODY)

    def _notice(self, text, color):
        width = self._label(text, BODY, color)[1] + 32
        panel(MARGIN, MARGIN + 120, width, 34)
        self._text(text, MARGIN + 16, MARGIN + 137, BODY, color)

    def _actions(self, actions):
        if not actions:
            return
        widths = [self._label(label, BODY, color)[1] + 56 for _, label, color in actions]
        gap = 8
        x = (self.width - sum(widths) - gap * (len(actions) - 1)) // 2
        y = self.height - MARGIN - 46
        for (key, label, color), width in zip(actions, widths):
            panel(x, y, width, 46)
            panel(x + 10, y + 9, 27, 28, KEYCAP, KEY_BORDER)
            self._text(key, x + 23, y + 23, BODY, align="center")
            self._text(label, x + 46, y + 23, BODY, color)
            x += width + gap

    def draw(self, world, light, aim, *, focused, alarm):
        self._vitals(world)
        self._objective(world)
        if not focused:
            self._notice("포커스 없음 · 이동 입력 초기화", AMBER)
            return
        if alarm:
            self._notice("차량 경보", AMBER)
        elif world.sneaking:
            self._notice("잠행 · 작은 발소리", TEAL)

        actions = []
        if world.can_interact():
            if light.contains(world.next_stop):
                action = "택배 수령" if world.parcel == "waiting" else "택배 전달"
                actions.append(("E", action, TEAL))
        elif world.can_open_gate():
            actions.append(("E", "철문 열기 · 소음", AMBER))
        if world.nearby_bottle is not None:
            actions.append(("F", "빈 병 줍기", TEXT))
        if world.can_throw_bottle(aim):
            actions.append(("Q", "병 던지기", TEXT))
        self._actions(actions)
