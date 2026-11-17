"""Choose delivery music intensity and directional footsteps from live zombie movement."""
from dataclasses import dataclass


ZOMBIE_HEARING_DISTANCE = 520.0
_PATROL_HEARING_DISTANCE = 260.0
_APPROACH_DISTANCE = 265.0
_CHASE_DISTANCE = 225.0
_CLOSE_DISTANCE = 54.0
_COMBAT_MEMORY_SECONDS = 1.1
_FOOTSTEP_PRIORITY = {"regular": 1.0, "patrol": 1.55, "heavy": 1.55}


@dataclass(frozen=True)
class EnemyAcoustics:
    source_id: int
    state: str
    distance: float
    stride: float
    pan: float
    occluded: bool
    kind: str

    @property
    def footstep_priority(self):
        if self.stride <= 1e-6:
            return 0.0
        distance_limit = _PATROL_HEARING_DISTANCE if self.kind == "patrol" else ZOMBIE_HEARING_DISTANCE
        gain = max(0.0, 1.0 - self.distance / distance_limit)
        return gain * (.65 if self.occluded else 1.0) * _FOOTSTEP_PRIORITY[self.kind]


def select_footstep_sources(enemies):
    candidates = [None, None]
    gains = [0.0, 0.0]
    for enemy in enemies:
        side = int(enemy.pan >= 0.0)
        gain = enemy.footstep_priority
        if gain > gains[side]:
            candidates[side] = enemy
            gains[side] = gain
    return tuple(enemy for enemy in candidates if enemy is not None)


def _proximity(distance, outer_distance):
    return max(0.0, min(1.0, (outer_distance - distance) / (outer_distance - _CLOSE_DISTANCE)))


class DeliveryAudioState:
    def __init__(self):
        self.reset()

    def reset(self):
        self._recent_combat = 0.0

    def update(self, dt, enemies, *, impact=0.0):
        self._recent_combat = max(0.0, self._recent_combat - dt / _COMBAT_MEMORY_SECONDS, impact)
        strongest = combined = 0.0
        combat = self._recent_combat
        for enemy in enemies:
            cover = .65 if enemy.occluded else 1.0
            approach = _proximity(enemy.distance, _APPROACH_DISTANCE) * cover
            if enemy.state == "chase":
                combat = max(combat, _proximity(enemy.distance, _CHASE_DISTANCE) * cover)
            elif enemy.state == "investigate":
                approach *= .65 if enemy.stride > 0.0 else .45
            elif enemy.state == "search":
                approach *= .40
            else:
                approach *= .32 if enemy.stride > 0.0 else .12
            strongest = max(strongest, approach)
            combined += approach
        threat = min(1.0, strongest + min(.22, (combined - strongest) * .26))
        return max(threat, combat), combat
