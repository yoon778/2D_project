"""Single delivery across the town and its connected alleys."""
from dataclasses import dataclass
import json
import math
from pathlib import Path

if __package__:
    from .combat import CombatWorld, Zombie
    from .core import Player, Wall, wall_blocks
else:
    from combat import CombatWorld, Zombie
    from core import Player, Wall, wall_blocks


TOWN_SIZE = (3600, 2400)
TOWN_ROADS = json.loads((Path(__file__).resolve().parent / "assets/neighborhood/roads.json")
                        .read_text(encoding="utf-8"))
PLAYER_START = (145.0, 145.0)
ZOMBIE_START = (675.0, 345.0)
ZOMBIE_STARTS = (
    ZOMBIE_START, (485, 475), (120, 565), (785, 690),
    (1020, 190), (1180, 335), (1420, 240), (1520, 490),
    (1100, 590), (955, 960), (1160, 815), (1450, 960),
    (2020, 485), (2475, 380), (2865, 155), (3255, 525),
    (2260, 932), (2930, 915), (2020, 1335), (2420, 1510),
    (3070, 1740), (2315, 1895), (2765, 2070), (3255, 2080),
)
INTERACTION_RANGE = 42.0
_BUILDINGS = ((690, 145, 180, 130),
              (165, 765, 330, 220), (610, 815, 270, 215), (800, 385, 205, 220),
              (1090, 145, 260, 135), (1120, 405, 270, 125),
              (1320, 615, 240, 240), (1050, 940, 285, 145))

# House fronts follow the roads and leave alleys between the blocks.
_WEST_HOUSES = (
    (1870, 210), (2550, 210), (3160, 210),
    (1740, 650), (3150, 650),
    (2790, 1060), (3110, 1060),
    (2110, 1450), (1770, 2000), (2550, 2000),
)
_EAST_HOUSES = (
    (1510, 210), (2150, 210), (2820, 210),
    (2070, 650), (2680, 650), (2290, 1060),
    (1760, 1450), (2540, 1450), (3000, 1450),
    (2110, 2000), (2850, 2000),
)


@dataclass
class NeighborhoodWall(Wall):
    texture: str
    height: int = 110
    oblique: bool = False


@dataclass(frozen=True)
class StreetProp:
    x: float
    y: float
    texture: str


# Group everyday objects where they belong, leaving the middle of the footpaths open.
_STREET_PROPS = {
    "mailbox": ((119, 278), (484, 200), (1534, 174), (1843, 612), (2122, 1968)),
    "planter": ((184, 277), (395, 211), (554, 211), (1848, 1045), (2050, 1045), (2340, 1762)),
    "bicycle": ((472, 173), (2110, 1038), (2190, 1767), (2930, 1980)),
    "trash-bags": ((329, 178), (520, 173), (655, 507), (1844, 1024), (2690, 1816)),
    "metal-bin": ((239, 248), (600, 223), (652, 522), (1690, 915), (2092, 1044), (3128, 1435)),
    "recycling-bin": ((249, 499), (597, 238), (1500, 192), (1837, 1024), (2359, 1770), (2736, 1814)),
}


class DeliveryWorld(CombatWorld):
    clear_on_zombie_death = False
    sprint_speed = 210.0
    world_size = TOWN_SIZE
    pickup = (172.0, 155.0)
    destination = (3380.0, 2240.0)
    props = tuple(StreetProp(x, y, texture) for texture, positions in _STREET_PROPS.items() for x, y in positions)
    streetlights = (
        (240, 525), (710, 659), (1380, 890), (1620, 1200),
        (1960, 990), (2660, 110), (3290, 530), (3290, 1350),
        (2290, 1750), (2730, 1935), (3330, 2130),
    )

    def reset(self):
        super().reset()
        self.player = Player(*PLAYER_START)
        self.zombies = [Zombie(*position) for position in ZOMBIE_STARTS]
        self.walls = [
            NeighborhoodWall(88, 305, 140, 190, "west-house", oblique=True),
            NeighborhoodWall(310, 225, 275, 200, "east-house", oblique=True),
            NeighborhoodWall(345, 164, 100, 12, "fence", height=38),
            NeighborhoodWall(370, 99, 112, 44, "parked-car", height=36),
            NeighborhoodWall(2380, 101, 112, 44, "abandoned-car", height=36),
            NeighborhoodWall(2140, 1019, 112, 44, "abandoned-car", height=36),
            # The wrecks cut across the eastern road. The house side has a narrow bypass.
            NeighborhoodWall(3332, 730, 112, 44, "abandoned-car", height=36),
            NeighborhoodWall(3468, 752, 112, 44, "abandoned-car", height=36),
            NeighborhoodWall(578, 458, 60, 34, "dumpster", height=28),
            NeighborhoodWall(1768, 1008, 60, 34, "dumpster", height=28),
            NeighborhoodWall(2668, 1775, 60, 34, "dumpster", height=28),
            *(NeighborhoodWall(*building, "workshop") for building in _BUILDINGS),
            *(NeighborhoodWall(x, y, 140, 190, "west-house") for x, y in _WEST_HOUSES),
            *(NeighborhoodWall(x, y, 275, 200, "east-house") for x, y in _EAST_HOUSES),
            NeighborhoodWall(1820, 1060, 260, 160, "shop"),
            NeighborhoodWall(2210, 1780, 140, 52, "bus-stop", height=68),
        ]
        self.parcel = "waiting"

    @property
    def next_stop(self):
        return self.pickup if self.parcel == "waiting" else self.destination

    def can_interact(self):
        if self.result != "playing" or self.player_hp <= 0:
            return False
        origin = (self.player.x, self.player.y)
        stop = self.next_stop
        return (math.dist(origin, stop) <= INTERACTION_RANGE
                and not any(wall_blocks(origin, stop, wall) for wall in self.walls))

    def interact(self):
        self._resolve_result()
        if not self.can_interact():
            return False
        if self.parcel == "waiting":
            self.parcel = "carrying"
        else:
            self.parcel = "delivered"
            self.result = "delivered"
            self.attack = None
            self._resolve_result()
        return True
