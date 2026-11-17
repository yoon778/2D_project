"""Geometry and landmarks for the independent delivery districts."""
from dataclasses import dataclass

if __package__:
    from .core import Wall
else:
    from core import Wall


@dataclass
class NeighborhoodWall(Wall):
    texture: str
    height: int = 110
    oblique: bool = False


@dataclass(frozen=True)
class DeliveryLayout:
    ground_file: str
    roads: dict
    walls: tuple[NeighborhoodWall, ...]
    road_labels: tuple[tuple[float, float, str], ...]
    detour_routes: tuple[tuple[tuple[float, float], ...], ...]
    streetlights: tuple[tuple[float, float], ...]
    bottle_pickups: tuple[tuple[float, float], ...]
    gate: NeighborhoodWall | None = None
    bus_switch: tuple[float, float] | None = None
    bus_speaker: tuple[float, float] | None = None
    world_size: tuple[int, int] = (2000, 1350)
    map_area: tuple[float, float, float, float] | None = None

    @property
    def gate_position(self):
        gate = self.gate
        return (gate.x + gate.width / 2, gate.y + gate.depth / 2) if gate is not None else None


def _road(*points, width):
    return {"points": points, "width": width}


REPAIR_DETOUR = ((980, 420), (300, 420), (300, 850), (980, 850))
REPAIR_YARD = DeliveryLayout(
    ground_file="neighborhood/repair-yard-ground.png",
    roads={
        "main": (
            _road((0, 110), (2000, 110), width=104),
            _road((980, 110), (980, 1120), width=88),
        ),
        "alleys": (
            _road((980, 750), (1370, 750), (1370, 845), (1485, 845), (1485, 1020), (1532, 1020), width=62),
        ),
        "main_detour": _road(*REPAIR_DETOUR, width=58),
    },
    walls=(
        NeighborhoodWall(130, 235, 180, 119, "workshop"),
        NeighborhoodWall(102, 674, 149, 172, "workshop", height=86),
        NeighborhoodWall(900, 440, 14, 181, "fence", height=38),
        NeighborhoodWall(425, 609, 510, 12, "fence", height=38),
        NeighborhoodWall(1025, 609, 975, 12, "fence", height=38),
        NeighborhoodWall(555, 470, 242, 135, "workshop"),
        NeighborhoodWall(1115, 338, 230, 192, "workshop"),
        NeighborhoodWall(1018, 637, 145, 80, "workshop", height=72),
        NeighborhoodWall(1083, 775, 242, 140, "workshop"),
        NeighborhoodWall(1410, 687, 180, 105, "workshop", height=92),
        NeighborhoodWall(1550, 960, 255, 166, "workshop"),
        NeighborhoodWall(515, 975, 268, 155, "workshop"),
        NeighborhoodWall(661, 669, 104, 43, "abandoned-car", height=36),
        NeighborhoodWall(1199, 552, 108, 42, "parked-car", height=36),
        NeighborhoodWall(1412, 1097, 61, 33, "dumpster", height=28),
    ),
    road_labels=((980, 356, "정비창 진입로"), (300, 655, "서쪽 우회로"), (1485, 1090, "부품 보관소")),
    detour_routes=(REPAIR_DETOUR,),
    streetlights=((960, 153), (941, 565), (335, 722), (1320, 732), (1485, 955)),
    bottle_pickups=((924, 155), (353, 445)),
    gate=NeighborhoodWall(935, 609, 90, 12, "iron-gate", height=38),
)


WAREHOUSE_DETOUR = ((790, 398), (495, 398), (495, 850), (790, 850))
WAREHOUSE = DeliveryLayout(
    ground_file="neighborhood/warehouse-ground.png",
    roads={
        "main": (
            _road((0, 110), (2000, 110), width=104),
            _road((960, 110), (960, 398), (790, 398), (790, 850), (1220, 850), width=92),
        ),
        "alleys": (
            _road((1220, 850), (1220, 1005), width=62),
            _road((790, 595), (790, 755), (1165, 755), (1165, 614), width=58),
        ),
        "main_detour": _road(*WAREHOUSE_DETOUR, width=62),
    },
    walls=(
        NeighborhoodWall(320, 235, 215, 130, "workshop"),
        NeighborhoodWall(222, 610, 151, 205, "workshop", height=84),
        NeighborhoodWall(570, 535, 140, 202, "workshop", height=92),
        NeighborhoodWall(945, 512, 150, 208, "workshop"),
        NeighborhoodWall(824, 788, 345, 14, "fence", height=38),
        NeighborhoodWall(1190, 395, 316, 125, "workshop"),
        NeighborhoodWall(1525, 595, 215, 142, "workshop"),
        NeighborhoodWall(700, 895, 298, 170, "workshop"),
        NeighborhoodWall(1250, 880, 300, 170, "workshop"),
        NeighborhoodWall(1010, 1110, 258, 144, "workshop"),
        NeighborhoodWall(350, 744, 60, 32, "dumpster", height=28),
        NeighborhoodWall(1492, 157, 104, 38, "parked-car", height=36),
        NeighborhoodWall(1350, 771, 108, 40, "abandoned-car", height=36),
    ),
    road_labels=((790, 548, "적재장 진입로"), (495, 653, "조용한 우회로"), (1220, 1030, "냉장 창고")),
    detour_routes=(WAREHOUSE_DETOUR,),
    streetlights=((960, 153), (755, 462), (825, 732), (1165, 740), (1190, 867)),
    bottle_pickups=((924, 155), (497, 443)),
    bus_switch=(790, 478),
    bus_speaker=(1165, 614),
)
