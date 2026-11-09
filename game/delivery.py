"""Single delivery across an alley district."""
from dataclasses import dataclass
import math

if __package__:
    from .combat import CombatWorld, Zombie
    from .core import Player, Wall, wall_blocks
else:
    from combat import CombatWorld, Zombie
    from core import Player, Wall, wall_blocks


PLAYER_START = (145.0, 145.0)
ZOMBIE_START = (675.0, 345.0)
ZOMBIE_STARTS = (ZOMBIE_START, (485, 475), (245, 615), (785, 690),
                 (1020, 190), (1180, 335), (1420, 240), (1520, 490),
                 (1100, 590), (955, 960), (1240, 825), (1450, 960))
ALLEY_PROP = (265.0, 245.0)
INTERACTION_RANGE = 42.0
_BUILDINGS = ((690, 120, 180, 155),
              (165, 765, 330, 220), (610, 815, 270, 215), (800, 385, 205, 220),
              (1090, 100, 260, 180), (1120, 405, 270, 125),
              (1320, 615, 240, 240), (1050, 940, 285, 145))


@dataclass
class NeighborhoodWall(Wall):
    texture: str
    height: int = 110


class DeliveryWorld(CombatWorld):
    clear_on_zombie_death = False
    sprint_speed = 210.0
    world_size = (1720, 1200)
    pickup = (172.0, 155.0)
    destination = (1610.0, 1080.0)

    def reset(self):
        super().reset()
        self.player = Player(*PLAYER_START)
        self.zombies = [Zombie(*position) for position in ZOMBIE_STARTS]
        self.walls = [
            NeighborhoodWall(88, 305, 140, 190, "west-house"),
            NeighborhoodWall(310, 225, 275, 200, "east-house"),
            NeighborhoodWall(345, 164, 100, 12, "fence", height=38),
            *(Wall(*building) for building in _BUILDINGS),
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
