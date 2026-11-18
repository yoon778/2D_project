"""Contract dispatch sheet, in SDL screen coordinates."""
import pico2d.pico2d as p

from play_hud import BODY, PAPER_EDGE, PAPER_GREEN, PAPER_INK, PAPER_MUTED, RECEIPT_TITLE, SMALL, STAMP, TITLE
from play_hud import fill, panel, receipt_rule


CARD_RECTS = tuple((61, 153 + index * 86, 359, 76) for index in range(4))
DISPATCH_RECT = (61, 529, 359, 57)
PHOTO_RECT = (480, 51, 748, 342)
MAP_RECT = (470, 417, 398, 263)

BACKGROUND = (27, 25, 22, 255)
SHEET = (235, 218, 184, 255)
CARD = (239, 223, 192, 255)
CARD_SELECTED = (247, 232, 200, 255)
CARD_LOCKED = (225, 209, 178, 255)
FOCUS_BORDER = (138, 89, 54, 255)
DISPATCH = (52, 84, 67, 255)
DISPATCH_HOVER = (69, 104, 82, 255)
DISPATCH_DISABLED = (171, 150, 114, 255)
ROUTE_GUIDANCE = {
    1: "정비창 철문 또는 서쪽 우회",
    2: "스피커 유도 또는 서쪽 우회",
    3: "남쪽 출입구로 들어가 보급실에 배달",
    4: "관리실 다리 또는 동쪽 우회",
}


def _contains(rect, x, y):
    left, top, width, height = rect
    return left <= x < left + width and top <= y < top + height


def contract_card_at(x, y):
    return next((index for index, rect in enumerate(CARD_RECTS) if _contains(rect, x, y)), None)


def contract_dispatch_at(x, y):
    return _contains(DISPATCH_RECT, x, y)


def load_contract_previews(directory, contracts):
    previews = []
    for contract in contracts:
        path = directory / contract.preview_file
        image = p.load_image(str(path)) if path.is_file() else None
        if image is not None and p.SDL_SetTextureScaleMode(image.texture, p.SDL_ScaleModeLinear) != 0:
            raise RuntimeError(f"Contract image sampling failed: {p.SDL_GetError()!r}")
        previews.append(image)
    return previews


def draw_contract_selection(hud, contracts, available, selected, cursor, previews, draw_route, draw_pin):
    text = hud._text
    unlocked = contracts[selected] in available
    hovered = None if cursor is None else contract_card_at(*cursor)
    fill(0, 0, hud.width, hud.height, BACKGROUND)

    panel(46, 45, 404, 640, (64, 51, 39, 255), background=(48, 39, 30, 255))
    panel(42, 40, 397, 640, PAPER_EDGE, background=SHEET, accent=STAMP)
    text("DEAD ROUTE", 66, 67, SMALL, PAPER_MUTED)
    text("배송 운송장", 64, 101, RECEIPT_TITLE, PAPER_INK)
    receipt_rule(63, 137, 355)

    for index, (contract, rect) in enumerate(zip(contracts, CARD_RECTS)):
        x, y, width, _ = rect
        active, locked = index == selected, contract not in available
        border = (*STAMP, 255) if active else FOCUS_BORDER if index == hovered else PAPER_EDGE
        paper = CARD_SELECTED if active else CARD_LOCKED if locked else CARD
        panel(*rect, border, background=paper, accent=STAMP if active else None)
        fill(x + 14, y + 12, 29, 30, (*PAPER_MUTED, 255) if active else (*PAPER_EDGE[:3], 255))
        text(str(contract.number), x + 28, y + 27, BODY, SHEET[:3], align="center")
        text(contract.name, x + 54, y + 26, TITLE, PAPER_INK)
        text(f"배송 {len(contract.stops)}곳", x + 54, y + 57, SMALL, PAPER_MUTED)
        text(f"위험도 {contract.difficulty}", x + width - 14, y + 57, SMALL, PAPER_MUTED, align="right")
        if active or locked:
            text("잠김" if locked else "선택", x + width - 14, y + 26, SMALL, STAMP, align="right")

    receipt_rule(63, 504, 355)
    dispatch_hover = cursor is not None and contract_dispatch_at(*cursor)
    dispatch_color = (DISPATCH_HOVER if dispatch_hover else DISPATCH) if unlocked else DISPATCH_DISABLED
    panel(*DISPATCH_RECT, PAPER_EDGE, background=dispatch_color)
    text("출발" if unlocked else "계약 잠김", 240, 555, TITLE, SHEET[:3] if unlocked else PAPER_INK, align="center")
    if unlocked:
        text("Enter", 404, 556, SMALL, SHEET[:3], align="right")
    numbers = "·".join(str(contract.number) for contract in contracts)
    text(f"{numbers} 선택   ·   Esc 종료", 240, 648, SMALL, PAPER_MUTED, align="center")

    panel(470, 41, 768, 362, PAPER_EDGE, background=CARD_LOCKED)
    x, y, width, height = PHOTO_RECT
    image = previews[selected]
    if image is not None:
        image.draw_to_origin(x, hud.height - y - height, width, height)
    else:
        draw_route(contracts[selected], PHOTO_RECT)
    panel(*MAP_RECT, PAPER_EDGE, background=SHEET)
    draw_route(contracts[selected], (478, 425, 382, 247))

    details = (887, 417, 351, 263)
    panel(*details, PAPER_EDGE, background=SHEET)
    text("배송지", 910, 445, TITLE, PAPER_INK)
    contract = contracts[selected]
    if len(contract.stops) > 1:
        text("순서 자유", 1215, 448, SMALL, PAPER_MUTED, align="right")
    for index, stop in enumerate(contract.stops):
        row = 485 + index * 30
        draw_pin(918, hud.height - 1 - row, STAMP)
        text(stop.name, 935, row, BODY, PAPER_INK)
    if contract.truck_position is not None:
        draw_pin(918, hud.height - 1 - 575, PAPER_GREEN, pickup=True)
        text("같은 트럭으로 복귀", 935, 575, BODY, PAPER_GREEN)
    receipt_rule(910, 607, 305)
    for offset in (0, 8, 16):
        fill(910 + offset, 631, 5, 2, (*PAPER_GREEN, 255))
    text(ROUTE_GUIDANCE[contract.number], 942, 632, SMALL, PAPER_GREEN)
    text("플레이 중 M으로 지도 열기", 910, 655, SMALL, PAPER_MUTED)
