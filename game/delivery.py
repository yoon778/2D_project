"""Single delivery across the town and its connected alleys."""
from dataclasses import dataclass
import math

if __package__:
    from .combat import CombatWorld, Zombie
    from .core import Player, Wall, wall_blocks
else:
    from combat import CombatWorld, Zombie
    from core import Player, Wall, wall_blocks


TOWN_SIZE = (3600, 2400)
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
ALLEY_PROP = (265.0, 245.0)
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


class DeliveryWorld(CombatWorld):
    clear_on_zombie_death = False
    sprint_speed = 210.0
    world_size = TOWN_SIZE
    pickup = (172.0, 155.0)
    destination = (3380.0, 2240.0)
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
            NeighborhoodWall(88, 305, 140, 190, "west-house"),
            NeighborhoodWall(310, 225, 275, 200, "east-house"),
            NeighborhoodWall(345, 164, 100, 12, "fence", height=38),
            *(Wall(*building) for building in _BUILDINGS),
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
