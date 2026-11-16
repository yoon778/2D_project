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
WAYPOINT = (46, 79, 122)
HEALTH = (203, 113, 88)
ENERGY = (172, 195, 143)
PANEL = (35, 30, 24, 234)
FRAME = (144, 117, 86, 218)
TRACK = (67, 61, 53, 255)
KEYCAP = (225, 217, 196, 255)
KEY_TEXT = (30, 28, 24)
SEPARATOR = (126, 120, 101, 150)
PAPER = (237, 221, 187, 255)
PAPER_EDGE = (163, 127, 85, 255)
PAPER_INK = (49, 37, 27)
PAPER_MUTED = (104, 75, 51)
PAPER_GREEN = (57, 88, 51)
STAMP = (139, 59, 45)
MAX_HEALTH = 3
MARGIN = 24
VITALS_WIDTH = 204
VITALS_HEIGHT = 95
OBJECTIVE_WIDTH = 284
OBJECTIVE_HEIGHT = 79
SMALL = 15
BODY = 18
TITLE = 26
RECEIPT_TITLE = 36
INTERACTION_LABELS = {
    "pickup": ("택배 수령 · 길게", "택배 수령 중", TEAL),
    "deliver": ("택배 전달 · 길게", "택배 전달 중", TEAL),
    "gate": ("철문 열기 · 길게", "철문 여는 중", AMBER),
    "shutter": ("셔터 닫기 · 길게", "셔터 닫는 중", AMBER),
    "bridge_key": ("관리실 열쇠 줍기 · 길게", "열쇠 줍는 중", TEAL),
    "bridge_panel": ("관리실 열기 · 길게", "관리실 여는 중", TEAL),
    "board_truck": ("트럭 탑승 · 길게", "트럭 탑승 중", TEAL),
}
PAUSE_MENU = ("계속하기", "조작법", "소리", "계약 포기", "게임 종료")
SOUND_LABELS = ("전체", "음악", "효과음")


def fill(x, y, width, height, color):
    p.SDL_SetRenderDrawColor(p.renderer, *color)
    bounds = p.SDL_Rect(x, y, width, height)
    p.SDL_RenderFillRect(p.renderer, ctypes.byref(bounds))


def panel(x, y, width, height, border=FRAME, *, background=PANEL, accent=None):
    fill(x, y, width, height, background)
    p.SDL_SetRenderDrawColor(p.renderer, *border)
    bounds = p.SDL_Rect(x, y, width, height)
    p.SDL_RenderDrawRect(p.renderer, ctypes.byref(bounds))
    if accent is not None:
        fill(x, y, 4, height, (*accent, 255))


def trace(x, y, points, color):
    p.SDL_SetRenderDrawColor(p.renderer, *color, 255)
    vertices = (p.SDL_Point * len(points))(*(p.SDL_Point(x + dx, y + dy) for dx, dy in points))
    p.SDL_RenderDrawLines(p.renderer, vertices, len(vertices))


def receipt_rule(x, y, width):
    for start in range(x, x + width - 6, 12):
        fill(start, y, 7, 1, (*PAPER_MUTED, 155))


class PlayHUD:
    def __init__(self, font_path, width, height):
        self.width, self.height = width, height
        self._fonts = {}
        self._labels = {}
        self._attack_label = None
        self._waypoint_label = None
        self.reset_delivery()
        try:
            for size in (SMALL, BODY, TITLE, RECEIPT_TITLE):
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
        x = y = MARGIN
        panel(x, y, VITALS_WIDTH, VITALS_HEIGHT)
        self._text("체력", x + 12, y + 19, BODY)
        self._text(f"{world.player_hp} / {MAX_HEALTH}", x + VITALS_WIDTH - 12, y + 19, BODY, align="right")
        for index in range(MAX_HEALTH):
            color = (*HEALTH, 255) if index < world.player_hp else TRACK
            fill(x + 12 + 61 * index, y + 34, 57, 10, color)
        self._text("스태미나", x + 12, y + 68, SMALL)
        track_x = x + 80
        track_width = VITALS_WIDTH - 92
        fill(track_x, y + 66, track_width, 5, TRACK)
        stamina = round(track_width * world.stamina / MAX_STAMINA)
        if stamina:
            fill(track_x, y + 66, stamina, 5, (*ENERGY, 255))

        if getattr(world, "route_sequence_active", False):
            return
        map_y = self.height - MARGIN - 24
        panel(x, map_y - 4, 86, 32)
        self._keycap("M", x + 5, map_y, 24)
        self._text("지도", x + 38, map_y + 12, BODY)
        panel(x + 92, map_y - 4, 101, 32)
        self._keycap("Esc", x + 97, map_y, 42)
        self._text("설정", x + 148, map_y + 12, BODY)

    def _objective(self, world):
        stop_count = len(world.contract.stops)
        x, y = self.width - MARGIN - OBJECTIVE_WIDTH, MARGIN
        panel(x, y, OBJECTIVE_WIDTH, OBJECTIVE_HEIGHT, PAPER_EDGE, background=PAPER, accent=STAMP)
        if getattr(world.contract, "truck_position", None) is not None:
            self._truck_objective(world, x, y, stop_count)
            return
        if world.returning:
            guidance = "추격을 끊고 복귀" if world.return_blocked else "도착하면 자동 완료"
            self._text(guidance, x + 16, y + 20, SMALL, STAMP if world.return_blocked else PAPER_MUTED)
            self._text("북쪽 안전지점 복귀", x + 16, y + 51, TITLE, PAPER_INK)
            return
        waiting = world.parcel == "waiting"
        self._text("택배 수령" if waiting else "택배 전달", x + 16, y + 20, SMALL, PAPER_MUTED)
        if stop_count > 1:
            self._text(f"{len(world.completed_stops)} / {stop_count}", x + OBJECTIVE_WIDTH - 14, y + 20,
                       SMALL, PAPER_MUTED, align="right")
        if world.contract.return_point is not None:
            place = "상점 근처 거점" if waiting else world.contract.stops[0].name
        else:
            place = "남서쪽 거점" if waiting else world.contract.name
        self._text(place, x + 16, y + 51, TITLE, PAPER_INK)

    def _truck_objective(self, world, x, y, stop_count):
        phase = world.mission_phase
        color = PAPER_MUTED
        if phase in ("arriving", "departing"):
            place = "트럭 도착 중" if phase == "arriving" else "트럭 출차 중"
            guidance = "Enter 건너뛰기"
        elif phase == "unloading":
            place, guidance = "트럭에서 택배 수령", "문 앞에서 E 길게"
        elif phase == "returning":
            place = "트럭으로 복귀"
            guidance = "추격을 끊고 탑승" if world.return_blocked else "문 앞에서 E 길게"
            if world.return_blocked:
                color = STAMP
        else:
            remaining = world.remaining_stops
            place = remaining[0].name if len(remaining) == 1 else "배송지 선택"
            guidance = "택배 전달"
        self._text(guidance, x + 16, y + 20, SMALL, color)
        if phase in ("delivering", "returning"):
            self._text(f"{len(world.completed_stops)} / {stop_count}", x + OBJECTIVE_WIDTH - 14, y + 20,
                       SMALL, PAPER_MUTED, align="right")
        self._text(place, x + 16, y + 51, TITLE, PAPER_INK)

    def _keycap(self, key, x, y, width):
        fill(x, y, width, 24, KEYCAP)
        self._text(key, x + width // 2, y + 12, BODY, KEY_TEXT, align="center")

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
        x, y = self.width - MARGIN - OBJECTIVE_WIDTH, MARGIN + OBJECTIVE_HEIGHT - 1
        panel(x, y, OBJECTIVE_WIDTH, 32, PAPER_EDGE, background=PAPER, accent=STAMP)
        tail = round(-8 * dx), round(-8 * dy)
        head = round(8 * dx), round(8 * dy)
        left = round(2 * dx - 4 * dy), round(2 * dy + 4 * dx)
        right = round(2 * dx + 4 * dy), round(2 * dy - 4 * dx)
        trace(x + 20, y + 16, (tail, head, left, head, right), WAYPOINT)
        self._text(label, x + 38, y + 16, SMALL, WAYPOINT)

    def _notice(self, text, color, *, sneak=False):
        x, y = MARGIN, MARGIN + VITALS_HEIGHT + 8
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

    def draw_action_prompt(self, x, y, key, label, *, progress=None):
        key_width = max(24, self._label(key, BODY, KEY_TEXT)[1] + 12)
        width = key_width + self._label(label, BODY, TEXT)[1] + 29
        height = 42 if progress is not None else 33
        padding = 8
        head_row = round(self.height - 1 - y)
        left = round(x - width / 2)
        top = head_row - height - 9
        # A head at the edge may leave no room above it. Put the badge beside it.
        if top < padding:
            side = 28
            left = round(x + side if x + side + width <= self.width - padding else x - side - width)
            top = head_row
        left = max(padding, min(self.width - width - padding, left))
        top = max(padding, min(self.height - height - padding, top))
        panel(left, top, width, height)
        self._keycap(key, left + 5, top + 4, key_width)
        self._text(label, left + key_width + 13, top + 16, BODY)
        if progress is not None:
            track_width = width - 10
            fill(left + 5, top + 33, track_width, 4, TRACK)
            filled = round(track_width * min(1.0, max(0.0, progress)))
            if filled:
                fill(left + 5, top + 33, filled, 4, (*TEAL, 255))

    def reset_delivery(self):
        if self._attack_label is not None:
            for key in tuple(self._labels):
                if key[0] == self._attack_label:
                    texture, _, _ = self._labels.pop(key)
                    p.SDL_DestroyTexture(texture)
            self._attack_label = None

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

    def _pause_sheet(self, heading, width, height):
        fill(0, 0, self.width, self.height, (0, 0, 0, 175))
        x, y = (self.width - width) // 2, (self.height - height) // 2
        fill(x + 6, y + 7, width, height, (7, 5, 3, 145))
        panel(x, y, width, height, PAPER_EDGE, background=PAPER, accent=STAMP)
        self._text(heading, x + 28, y + 33, TITLE, PAPER_INK)
        receipt_rule(x + 28, y + 58, width - 56)
        return x, y

    def draw_pause(self, page, index, volumes):
        if page == "controls":
            self._draw_controls()
        elif page == "audio":
            self._draw_audio(index, volumes)
        else:
            width, height = 444, 370
            x, y = self._pause_sheet("일시정지", width, height)
            for row, label in enumerate(PAUSE_MENU):
                top = y + 75 + row * 47
                if row == index:
                    panel(x + 27, top, width - 54, 39, PAPER_EDGE,
                          background=(224, 201, 163, 255), accent=STAMP)
                self._text(label, x + 43, top + 20, BODY, STAMP if row == index else PAPER_INK)
            receipt_rule(x + 28, y + 320, width - 56)
            self._text("↑ ↓ 선택    Enter 확인    Esc 계속하기", x + 28, y + 342, SMALL, PAPER_MUTED)

    def _draw_controls(self):
        width, height = 746, 428
        x, y = self._pause_sheet("조작법", width, height)
        left, right = x + 28, x + 386
        fill(x + 365, y + 76, 1, 273, (*PAPER_MUTED, 74))

        self._keycap("W", left + 28, y + 76, 26)
        for offset, key in enumerate("ASD"):
            self._keycap(key, left + 28 * offset, y + 102, 26)
        self._text("이동", left + 99, y + 103, BODY, PAPER_INK)
        for offset, (key, action) in enumerate((("Shift", "달리기"), ("Ctrl", "잠행"))):
            xx = left + offset * 151
            self._keycap(key, xx, y + 151, 53)
            self._text(action, xx + 64, y + 163, BODY, PAPER_INK)

        self._keycap("E", left, y + 207, 26)
        self._text("길게 눌러 수령·전달·문 조작", left + 38, y + 217, BODY, PAPER_INK)
        self._text("짧게 눌러 쪽지 읽기", left + 38, y + 244, SMALL, PAPER_MUTED)
        for offset, key in enumerate("123"):
            self._keycap(key, left + 28 * offset, y + 289, 26)
        self._text("회로 타일 회전", left + 98, y + 301, BODY, PAPER_INK)

        mouse = ((5, 5), (12, 0), (23, 0), (30, 5), (33, 13), (33, 29), (29, 36),
                 (23, 41), (12, 41), (5, 36), (2, 29), (2, 13), (5, 5))
        trace(right, y + 78, mouse, PAPER_MUTED)
        trace(right, y + 78, ((17, 1), (17, 17), (3, 17), (32, 17)), PAPER_MUTED)
        fill(right + 7, y + 85, 7, 7, (*STAMP, 210))
        self._text("마우스 조준 · 좌클릭 배트", right + 49, y + 100, BODY, PAPER_INK)
        for offset, (key, action) in enumerate((("F", "빈 병 줍기"), ("Q", "병 던지기"))):
            xx = right + offset * 156
            self._keycap(key, xx, y + 151, 26)
            self._text(action, xx + 38, y + 163, BODY, PAPER_INK)

        self._keycap("M", right, y + 207, 26)
        self._text("지도", right + 38, y + 217, BODY, PAPER_INK)
        self._text("좌클릭 경유지 추가 · 우클릭 마지막 삭제", right + 38, y + 244, SMALL, PAPER_MUTED)
        self._keycap("Space", right, y + 270, 67)
        self._text("경유지 건너뛰기", right + 79, y + 282, SMALL, PAPER_INK)
        self._keycap("R", right, y + 309, 26)
        self._text("계약 포기", right + 38, y + 321, BODY, PAPER_INK)

        receipt_rule(x + 28, y + 368, width - 56)
        self._keycap("Esc", left, y + 380, 42)
        self._text("뒤로", left + 52, y + 392, SMALL, PAPER_INK)

    def _draw_audio(self, index, volumes):
        width, height = 492, 338
        x, y = self._pause_sheet("소리", width, height)
        for row, (name, volume) in enumerate(zip(SOUND_LABELS, volumes)):
            top = y + 76 + row * 65
            if row == index:
                panel(x + 27, top, width - 54, 55, PAPER_EDGE,
                      background=(224, 201, 163, 255), accent=STAMP)
            self._text(name, x + 43, top + 27, BODY, PAPER_INK)
            bar_x, bar_width = x + 137, 215
            fill(bar_x, top + 23, bar_width, 8, (*PAPER_MUTED, 55))
            filled = round(bar_width * volume / 100)
            if filled:
                fill(bar_x, top + 23, filled, 8, (*(STAMP if row == index else PAPER_GREEN), 255))
            self._text(f"{volume}%", x + width - 44, top + 27, BODY, PAPER_INK, align="right")
        receipt_rule(x + 28, y + 275, width - 56)
        self._text("↑ ↓ 항목    ← → 조절    Esc 뒤로", x + 28, y + 305, SMALL, PAPER_MUTED)

    def draw_bridge_note(self):
        fill(0, 0, self.width, self.height, (0, 0, 0, 170))
        width, height = 500, 336
        x, y = (self.width - width) // 2, (self.height - height) // 2
        fill(x + 6, y + 7, width, height, (8, 6, 2, 150))
        panel(x, y, width, height, PAPER_EDGE, background=(232, 213, 174, 255))

        crease = x + 314
        fill(crease, y + 8, 1, height - 16, (*PAPER_MUTED, 84))
        fill(crease + 1, y + 8, 2, height - 16, (255, 242, 207, 95))
        for row in range(23):
            fill(x + width - 23 + row, y + 1 + row, 22 - row, 1, (201, 177, 140, 255))
        fill(x + 187, y - 7, 126, 21, (194, 166, 109, 221))
        fill(x + 191, y + 9, 118, 2, (151, 122, 80, 100))
        for dx, dy, stain_width in ((18, 166, 12), (20, 168, 15), (445, 86, 26), (454, 88, 15), (394, 293, 20)):
            fill(x + dx, y + dy, stain_width, 2, (*PAPER_MUTED, 43))

        left = x + 36
        self._text("다리 건너는 사람에게", left, y + 47, TITLE, PAPER_INK)
        self._text("경비초소에 관리실 열쇠를 뒀다.", left, y + 96, BODY, PAPER_INK)
        self._text("관리실에서 전원부터 모터까지 회로를 이으면", left + 2, y + 123, BODY, PAPER_INK)
        self._text("다리가 내려온다.", left, y + 150, BODY, PAPER_INK)
        self._text("모터 소리가 크다. 좀비 조심.", left + 1, y + 196, BODY, STAMP)
        self._text("급하면 동쪽 골목으로 돌아가.", left, y + 224, BODY, PAPER_INK)
        self._text("— 시설 담당", x + width - 36, y + 261, SMALL, PAPER_MUTED, align="right")

        self._keycap("E", left, y + 289, 24)
        self._text("/", left + 33, y + 301, BODY, PAPER_MUTED)
        self._keycap("Esc", left + 47, y + 289, 42)
        self._text("접기", left + 100, y + 301, BODY, PAPER_INK)

    def draw_bridge_panel(self, puzzle):
        fill(0, 0, self.width, self.height, (0, 0, 0, 175))
        width, height = 560, 364
        x, y = (self.width - width) // 2, (self.height - height) // 2
        panel(x, y, width, height, PAPER_EDGE, background=PAPER, accent=STAMP)
        self._text("다리 제어 회로", x + 30, y + 35, TITLE, PAPER_INK)
        self._text("1 · 2 · 3으로 타일을 돌려 전원과 모터 연결", x + 30, y + 69, BODY, PAPER_MUTED)
        panel(x + 30, y + 94, width - 60, 188, FRAME, background=(48, 47, 42, 255))

        left, top = x + 191, y + 145
        tile_size = 72
        centers = ((left, top + tile_size), (left, top), (left + tile_size, top))
        inactive = (178, 140, 98, 255)
        live = (*TEAL, 255)
        for cx, cy in centers:
            panel(cx - 34, cy - 34, 68, 68, FRAME, background=(68, 57, 47, 255))

        # Screen y increases downward; the circuit's port coordinates use ground y.
        for index, ((cx, cy), ports, powered) in enumerate(zip(centers, puzzle.ports, puzzle.powered), 1):
            color = live if powered else inactive
            for dx, dy in ports:
                fill(min(cx, cx + dx * 35) - 2, min(cy, cy - dy * 35) - 2,
                     abs(dx) * 35 + 5, abs(dy) * 35 + 5, color)
            fill(cx - 5, cy - 5, 11, 11, color)
            fill(cx - 30, cy - 30, 16, 18, PANEL)
            self._text(str(index), cx - 22, cy - 21, SMALL, align="center")

        source_y = centers[0][1]
        source_x = left - 93
        output_x = centers[-1][0] + 35
        fill(source_x, source_y - 2, left - 35 - source_x, 5, live)
        fill(source_x - 4, source_y - 5, 10, 11, live)
        fill(output_x, top - 2, 65, 5, inactive)
        fill(output_x + 62, top - 5, 10, 11, inactive)
        self._text("전원", source_x, source_y + 21, SMALL, TEAL, align="center")
        self._text("모터", output_x + 67, top + 21, SMALL, AMBER, align="center")

        self._text("가동하면 모터 소리에 좀비가 반응", x + 30, y + 309, SMALL, STAMP)
        self._keycap("Esc", x + width - 120, y + 330, 42)
        self._text("닫기", x + width - 69, y + 342, SMALL, PAPER_INK)

    def draw_result(self, world):
        success = world.result == "delivered"
        extra_lines = []
        if len(world.contract.stops) > 1:
            for stop in world.contract.stops:
                completed = stop in world.completed_stops
                status = "완료" if completed else "미완료"
                extra_lines.append((f"{stop.name} · {status}", PAPER_GREEN if completed else PAPER_MUTED))
        if world.just_unlocked_two_stop:
            extra_lines.append(("새 계약 열림 · R에서 3번 선택", PAPER_GREEN))
        extra_height = len(extra_lines) * 25
        width, height = 454, 303 + extra_height
        x, y = (self.width - width) // 2, (self.height - height) // 2
        center = self.width // 2
        fill(0, 0, self.width, self.height, (8, 6, 4, 130))
        fill(x + 5, y + 7, width, height, (6, 4, 2, 150))
        panel(x, y, width, height, PAPER_EDGE, background=PAPER)
        left, right = x + 27, x + width - 27
        self._text("배송 확인서", left, y + 30, SMALL, PAPER_MUTED)
        self._text("배달 성공" if success else "배달 실패", left - 1, y + 63, RECEIPT_TITLE,
                   PAPER_INK if success else STAMP)
        if getattr(world.contract, "truck_position", None) is not None:
            stamp = "출차 완료"
        else:
            stamp = "복귀 확인" if world.contract.return_point is not None else "배송 확인"
        if not success:
            stamp = "미완료"
        panel(right - 106, y + 29, 106, 35, (*STAMP, 255), background=PAPER)
        panel(right - 103, y + 32, 100, 29, (*STAMP, 185), background=PAPER)
        self._text(stamp, right - 53, y + 46, SMALL, STAMP, align="center")
        receipt_rule(left, y + 98, right - left)

        self._attack_label = f"{world.attack_count}회"
        rows = (("배송지", world.contract.name), ("남은 체력", f"{world.player_hp} / {MAX_HEALTH}"),
                ("공격 횟수", self._attack_label),
                ("교전 없이 배달", "성공" if success and world.combat_free else "미달성"))
        for index, (label, value) in enumerate(rows):
            baseline = y + 125 + index * 28
            self._text(label, left, baseline, BODY, PAPER_MUTED)
            self._text(value, right, baseline, BODY, PAPER_INK, align="right")
        receipt_rule(left, y + 231, right - left)
        for index, (label, color) in enumerate(extra_lines):
            self._text(label, center, y + 252 + index * 25, SMALL, color, align="center")
        if extra_lines:
            receipt_rule(left, y + 243 + extra_height, right - left)
        self._text("Enter 같은 배송 재도전  ·  R 배달 선택  ·  Esc 종료", center, y + 268 + extra_height,
                   SMALL, PAPER_INK, align="center")

    def draw(self, world, light, aim, *, focused, alarm, waypoint_direction=None):
        self._vitals(world)
        self._objective(world)
        if not focused:
            self._notice("포커스 없음 · 이동 입력 초기화", AMBER)
            return
        if waypoint_direction is not None:
            self._waypoint(waypoint_direction, world.first_waypoint_number)
        bridge = world.bridge_puzzle
        if alarm:
            self._notice("차량 경보", AMBER)
        elif bridge is not None and world.can_reach_bridge_panel() and not (bridge.has_key or bridge.bridge_down):
            self._notice("관리실 잠김 · 경비초소에 열쇠", AMBER)
        elif (getattr(world, "route_gimmicks_active", world.returning) and world.shutter_position is not None
              and math.dist((world.player.x, world.player.y), world.shutter_position) <= 150
              and light.contains(world.shutter_position)):
            if world.shutter_closed:
                self._notice("주차장 셔터 닫힘", TEAL)
            else:
                text = "주차장 안쪽에 병을 던져 유인" if world.has_bottle else "좀비가 들어가면 셔터 닫기"
                self._notice(text, AMBER)
        elif world.sneaking:
            self._notice("잠행 · 작은 발소리", TEAL, sneak=True)
