"""Native-resolution HUD for an active delivery."""
import ctypes
import math

import pico2d.pico2d as p

if __package__:
    from .combat import MAX_STAMINA
else:
    from combat import MAX_STAMINA


TEXT = (244, 239, 225)
TEAL = (123, 221, 192)
AMBER = (255, 191, 106)
SAFE_GREEN = (168, 226, 120)
WAYPOINT = (222, 174, 255)
HEALTH = (237, 146, 129)
PANEL = (22, 29, 27, 230)
FRAME = (112, 123, 112, 200)
TRACK = (67, 61, 53, 255)
KEYCAP = (225, 217, 196, 255)
KEY_TEXT = (30, 28, 24)
SEPARATOR = (126, 120, 101, 150)
MAX_HEALTH = 3
MARGIN = 24
UTILITY_SIZE = 40
PANEL_GAP = 10
VITALS_WIDTH = 204
VITALS_HEIGHT = 98
SMALL = 15
BODY = 18
TITLE = 26
HINT_WINDOW = 60.0
HINT_DURATION = 5.0
PICKUP_CONTROLS = "WASD 이동 · 마우스 조준 · 좌클릭 공격"
HINT_TEXT = {"E": "택배 수령 · 길게 누르기", "M": "지도에서 배송지 확인", "Ctrl": "발소리를 줄여 지나가기"}
INTERACTION_LABELS = {
    "pickup": (HINT_TEXT["E"], "택배 수령 중", TEAL),
    "deliver": ("택배 전달 · 길게 누르기", "택배 전달 중", TEAL),
    "gate": ("철문 열기 · 길게 누르기 · 소음", "철문 여는 중 · 소음", AMBER),
}


def fill(x, y, width, height, color):
    p.SDL_SetRenderDrawColor(p.renderer, *color)
    bounds = p.SDL_Rect(x, y, width, height)
    p.SDL_RenderFillRect(p.renderer, ctypes.byref(bounds))


def panel(x, y, width, height, border=FRAME):
    fill(x, y, width, height, PANEL)
    p.SDL_SetRenderDrawColor(p.renderer, *border)
    bounds = p.SDL_Rect(x, y, width, height)
    p.SDL_RenderDrawRect(p.renderer, ctypes.byref(bounds))


def trace(x, y, points, color):
    p.SDL_SetRenderDrawColor(p.renderer, *color, 255)
    vertices = (p.SDL_Point * len(points))(*(p.SDL_Point(x + dx, y + dy) for dx, dy in points))
    p.SDL_RenderDrawLines(p.renderer, vertices, len(vertices))


class PlayHUD:
    def __init__(self, font_path, width, height):
        self.width, self.height = width, height
        self._fonts = {}
        self._labels = {}
        self._attack_label = None
        self._waypoint_label = None
        self.reset_delivery()
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
        # Dynamic attack-count text is released when starting the next delivery.
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
        x, y = MARGIN + UTILITY_SIZE + PANEL_GAP, MARGIN
        panel(MARGIN, y, UTILITY_SIZE, UTILITY_SIZE, (*TEAL, 220))
        fill(MARGIN + 11, y + 17, 18, 6, (*TEXT, 255))
        fill(MARGIN + 17, y + 11, 6, 18, (*TEXT, 255))

        map_y = y + UTILITY_SIZE + 8
        panel(MARGIN, map_y, UTILITY_SIZE, UTILITY_SIZE)
        trace(MARGIN + 8, map_y + 8, ((0, 4), (7, 0), (14, 4), (21, 0), (21, 17),
                                    (14, 21), (7, 17), (0, 21), (0, 4)), TEXT)
        trace(MARGIN + 8, map_y + 8, ((7, 0), (7, 17)), TEXT)
        trace(MARGIN + 8, map_y + 8, ((14, 4), (14, 21)), TEXT)
        fill(MARGIN + 24, map_y + 24, 16, 16, KEYCAP)
        self._text("M", MARGIN + 32, map_y + 32, SMALL, KEY_TEXT, align="center")

        panel(x, y, VITALS_WIDTH, VITALS_HEIGHT)
        self._text("체력", x + 12, y + 19, BODY)
        self._text(f"{world.player_hp} / {MAX_HEALTH}", x + VITALS_WIDTH - 12, y + 19, BODY, align="right")
        for index in range(MAX_HEALTH):
            color = (*HEALTH, 255) if index < world.player_hp else TRACK
            fill(x + 12 + 61 * index, y + 34, 57, 10, color)
        self._text("스태미나", x + 12, y + 63, BODY)
        track_width = VITALS_WIDTH - 24
        fill(x + 12, y + 82, track_width, 5, TRACK)
        stamina = round(track_width * world.stamina / MAX_STAMINA)
        if stamina:
            fill(x + 12, y + 82, stamina, 5, (*TEAL, 255))

    def _objective(self, world):
        stop_count = len(world.contract.stops)
        width, height = (212 if stop_count > 1 else 184), 68
        if world.contract.return_point is not None:
            width = 212
        x, y = self.width - MARGIN - width, MARGIN
        if world.returning:
            accent = AMBER if world.return_blocked else SAFE_GREEN
            guidance = "추격을 끊고 복귀" if world.return_blocked else "도착하면 자동 완료"
            panel(x, y, width, height)
            fill(x, y, 3, height, (*accent, 255))
            self._text("안전지점 복귀", x + 14, y + 24, TITLE, accent)
            self._text(guidance, x + 14, y + 50, SMALL)
            return
        panel(x, y, width, height)
        fill(x, y, 3, height, (*TEAL, 255))
        waiting = world.parcel == "waiting"
        self._text("택배 수령" if waiting else "택배 전달", x + 14, y + 17, SMALL, TEAL)
        if stop_count > 1:
            self._text(f"{len(world.completed_stops)} / {stop_count}", x + width - 14, y + 17,
                       SMALL, TEAL, align="right")
        if world.contract.return_point is not None:
            place = "상점 근처 거점" if waiting else world.contract.stops[0].name
        else:
            place = "남서쪽 거점" if waiting else world.contract.name
        self._text(place, x + 14, y + 45, TITLE)

    def _keycap(self, key, x, y, width):
        fill(x, y, width, 24, KEYCAP)
        self._text(key, x + width // 2, y + 12, BODY, KEY_TEXT, align="center")

    def _draw_pickup_controls(self):
        width = self._label(PICKUP_CONTROLS, BODY, TEXT)[1] + 28
        center = self.width // 2
        panel(center - width // 2, MARGIN, width, 36)
        self._text(PICKUP_CONTROLS, center, MARGIN + 18, BODY, align="center")

    def _waypoint(self, direction, number):
        dx, dy = direction
        distance = math.hypot(dx, dy)
        if not distance:
            return
        dx, dy = dx / distance, dy / distance
        label = f"경유지 {number} 방향"
        if self._waypoint_label != label:
            previous = self._labels.pop((self._waypoint_label, SMALL, WAYPOINT), None)
            if previous is not None:
                p.SDL_DestroyTexture(previous[0])
            self._waypoint_label = label
        width = 144 + 9 * len(str(number))
        x, y = self.width - MARGIN - width, MARGIN + 76
        panel(x, y, width, 32)
        tail = round(-8 * dx), round(-8 * dy)
        head = round(8 * dx), round(8 * dy)
        left = round(2 * dx - 4 * dy), round(2 * dy + 4 * dx)
        right = round(2 * dx + 4 * dy), round(2 * dy - 4 * dx)
        trace(x + 20, y + 16, (tail, head, left, head, right), WAYPOINT)
        self._text(label, x + 38, y + 16, SMALL, WAYPOINT)

    def _notice(self, text, color, *, sneak=False):
        x, y = MARGIN + UTILITY_SIZE + PANEL_GAP, MARGIN + VITALS_HEIGHT + 8
        width = self._label(text, SMALL, TEXT)[1] + 42
        panel(x, y, width, 32)
        if sneak:
            trace(x + 9, y + 9, ((0, 7), (7, 2), (14, 7), (7, 12), (0, 7)), color)
            trace(x + 9, y + 9, ((2, 12), (12, 2)), color)
        else:
            trace(x + 9, y + 9, ((0, 13), (7, 0), (14, 13), (0, 13)), color)
            fill(x + 16, y + 14, 1, 4, (*color, 255))
            fill(x + 16, y + 20, 1, 1, (*color, 255))
        self._text(text, x + 31, y + 16, SMALL)

    def _actions(self, actions, *, progress=None):
        if not actions:
            return
        key_widths = [max(23, self._label(key, BODY, KEY_TEXT)[1] + 12) for key, _, _ in actions]
        widths = [self._label(label, BODY, color)[1] + key_width + 30
                  for (_, label, color), key_width in zip(actions, key_widths)]
        total = sum(widths)
        x = (self.width - total) // 2
        height = 49 if progress is not None else 40
        y = self.height - MARGIN - height
        panel(x, y, total, height)
        for index, ((key, label, color), key_width, width) in enumerate(zip(actions, key_widths, widths)):
            if index:
                fill(x, y + 8, 1, 24, SEPARATOR)
            self._keycap(key, x + 10, y + 8, key_width)
            self._text(label, x + key_width + 18, y + 20, BODY, color)
            if key == "E" and progress is not None:
                track_width = width - 20
                fill(x + 10, y + 38, track_width, 4, TRACK)
                filled = round(track_width * progress)
                if filled:
                    fill(x + 10, y + 38, filled, 4, (*color, 255))
            x += width

    def reset_delivery(self):
        self._seen_hints = set()
        self._hint = None
        self._hint_until = 0.0
        self._pickup_controls_until = None
        if self._attack_label is not None:
            label = self._labels.pop((self._attack_label, BODY, TEXT), None)
            if label is not None:
                p.SDL_DestroyTexture(label[0])
            self._attack_label = None

    def dismiss_hint(self, key):
        self._seen_hints.add(key)
        if self._hint == key:
            self._hint = None

    def watch_for_sneak_hint(self, world):
        if world.sneaking:
            self.dismiss_hint("Ctrl")
        if any(zombie.alive and zombie.state == "chase" for zombie in world.zombies):
            if self._hint == "Ctrl":
                self.dismiss_hint("Ctrl")
            return False
        return "Ctrl" not in self._seen_hints and world.elapsed_play_time < HINT_WINDOW

    def _active_hint(self, world, near_visible_zombie, interaction_target):
        elapsed = world.elapsed_play_time
        if elapsed >= HINT_WINDOW:
            self._hint = None
            return None
        can_pick_up = world.parcel == "waiting" and interaction_target is not None
        if (self._hint == "E" and not can_pick_up) or elapsed >= self._hint_until:
            self._hint = None
        if self._hint is None:
            for key, available in (("E", can_pick_up), ("M", world.parcel == "carrying"),
                                   ("Ctrl", near_visible_zombie)):
                if available and key not in self._seen_hints:
                    self._seen_hints.add(key)
                    self._hint = key
                    self._hint_until = elapsed + HINT_DURATION
                    break
        return self._hint

    def draw_abandon_confirmation(self):
        fill(0, 0, self.width, self.height, (0, 0, 0, 170))
        width, height = 440, 152
        x, y = (self.width - width) // 2, (self.height - height) // 2
        center = self.width // 2
        panel(x, y, width, height, (*AMBER, 220))
        self._text("배달을 포기할까요?", center, y + 36, TITLE, align="center")
        self._text("현재 배달 진행이 초기화됩니다", center, y + 70, BODY, align="center")
        fill(x + 24, y + 95, width - 48, 1, SEPARATOR)
        self._keycap("Enter", x + 79, y + 108, 58)
        self._text("포기", x + 145, y + 120, BODY, AMBER)
        self._keycap("Esc", x + 234, y + 108, 42)
        self._text("계속하기", x + 284, y + 120, BODY)

    def draw_result(self, world):
        success = world.result == "delivered"
        accent = TEAL if success else AMBER
        extra_lines = []
        if len(world.contract.stops) > 1:
            for stop in world.contract.stops:
                completed = stop in world.completed_stops
                status = "완료" if completed else "미완료"
                extra_lines.append((f"{stop.name} · {status}", TEAL if completed else TEXT))
        if world.just_unlocked_two_stop:
            extra_lines.append(("새 계약 열림 · R에서 3번 선택", TEAL))
        extra_height = len(extra_lines) * 24
        width, height = 502, 244 + extra_height
        x, y = (self.width - width) // 2, (self.height - height) // 2
        center = self.width // 2
        panel(x, y, width, height, (*accent, 220))
        self._text("배달 성공" if success else "배달 실패", center, y + 34, TITLE, accent, align="center")
        self._attack_label = f"{world.attack_count}회"
        rows = (("배송지", world.contract.name), ("남은 체력", f"{world.player_hp} / {MAX_HEALTH}"),
                ("공격 횟수", self._attack_label),
                ("교전 없이 배달", "성공" if success and world.combat_free else "미달성"))
        for index, (label, value) in enumerate(rows):
            baseline = y + 78 + index * 30
            self._text(label, x + 28, baseline, BODY)
            self._text(value, x + width - 28, baseline, BODY, align="right")
        fill(x + 28, y + 189, width - 56, 1, SEPARATOR)
        for index, (label, color) in enumerate(extra_lines):
            self._text(label, center, y + 208 + index * 24, SMALL, color, align="center")
        self._text("Enter 같은 배송 재도전  ·  R 배달 선택  ·  Esc 종료", center, y + 216 + extra_height,
                   SMALL, align="center")

    def draw(self, world, light, aim, *, focused, alarm, near_visible_zombie=False, waypoint_direction=None):
        self._vitals(world)
        self._objective(world)
        if not focused:
            self._notice("포커스 없음 · 이동 입력 초기화", AMBER)
            return
        if world.parcel == "carrying":
            elapsed = world.elapsed_play_time
            if self._pickup_controls_until is None:
                self._pickup_controls_until = elapsed + HINT_DURATION
            if elapsed < self._pickup_controls_until:
                self._draw_pickup_controls()
        if waypoint_direction is not None:
            self._waypoint(waypoint_direction, world.first_waypoint_number)
        if alarm:
            self._notice("차량 경보", AMBER)
        elif world.sneaking:
            self._notice("잠행 · 작은 발소리", TEAL, sneak=True)

        interaction_target = world.interaction_target
        hint = self._active_hint(world, near_visible_zombie, interaction_target)
        action = world.interaction_action
        progress = world.interaction_progress if action is not None else None
        actions = [(hint, HINT_TEXT[hint], TEAL)] if hint is not None and hint != "E" else []
        if action is not None:
            _, label, color = INTERACTION_LABELS[action]
            actions.append(("E", label, color))
        elif interaction_target is not None:
            if hint == "E" or light.contains(interaction_target):
                label, _, color = INTERACTION_LABELS["pickup" if world.parcel == "waiting" else "deliver"]
                actions.append(("E", label, color))
        elif world.can_open_gate():
            label, _, color = INTERACTION_LABELS["gate"]
            actions.append(("E", label, color))
        if world.nearby_bottle is not None:
            actions.append(("F", "빈 병 줍기", TEXT))
        bottle_hint = world.bottle_throw_hint(aim, light=light)
        if bottle_hint is not None:
            actions.append(("Q", bottle_hint, AMBER if bottle_hint == "차량 경보 유인" else TEXT))
        self._actions(actions, progress=progress)
