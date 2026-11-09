"""Single delivery through a small alley, using the existing combat rules."""
import math

if __package__:
    from .combat import CombatWorld, Zombie
    from .core import Player, Wall, wall_blocks
else:
    from combat import CombatWorld, Zombie
    from core import Player, Wall, wall_blocks


PLAYER_START = (145.0, 145.0)
ZOMBIE_START = (675.0, 345.0)
ALLEY_PROP = (265.0, 245.0)
INTERACTION_RANGE = 42.0
_BUILDINGS = ((88, 305, 140, 190), (310, 225, 275, 200), (690, 120, 180, 155))


class DeliveryWorld(CombatWorld):
    clear_on_zombie_death = False
    pickup = (172.0, 155.0)
    destination = (796.0, 535.0)

    def reset(self):
        super().reset()
        self.player = Player(*PLAYER_START)
        self.zombie = Zombie(*ZOMBIE_START)
        self.walls = [Wall(*building) for building in _BUILDINGS]
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
            self.attack = self.zombie.attack = None
        return True
