"""R2-A 렌더링과 독립된 단일 좀비 전투 판정."""
from dataclasses import dataclass
import math

if __package__:
    from .core import Player, Wall, move_player, PLAYER_RADIUS, WALK_SPEED
else:
    from core import Player, Wall, move_player, PLAYER_RADIUS, WALK_SPEED


ATTACK_DURATION = 0.6
ATTACK_HIT_TIME = 0.18
STUN_DURATION = 0.4
_EPSILON = 1e-12
_TIME_STEP = 0.001
_MAX_UPDATE_DT = 10.0


def _wall_blocks(start, end, wall):
    enter, leave = 0.0, 1.0
    for origin, delta, low, high in (
        (start.x, end.x - start.x, wall.x, wall.x + wall.width),
        (start.y, end.y - start.y, wall.y, wall.y + wall.depth),
    ):
        if abs(delta) <= _EPSILON:
            if origin < low - _EPSILON or origin > high + _EPSILON:
                return False
        else:
            first, last = sorted(((low - origin) / delta, (high - origin) / delta))
            enter, leave = max(enter, first), min(leave, last)
            if enter > leave + _EPSILON:
                return False
    return True


@dataclass
class Zombie(Player):
    hp: int = 5
    stun_remaining: float = 0.0

    @property
    def alive(self):
        return self.hp > 0


@dataclass
class Attack:
    angle: float
    facing: str
    elapsed: float = 0.0
    _hit_done: bool = False


class CombatWorld:
    def __init__(self):
        self.reset()

    def reset(self):
        self.player = Player()
        self.walls = [Wall(400, 330, 220, 60)]
        self.zombie = Zombie(600.0, 100.0)
        self.player_hp = 3
        self.player_invulnerable_remaining = 0.0
        self.attack = None
        self.result = "playing"

    def start_attack(self, facing="front_right"):
        self._resolve_result()
        if self.attack is not None or self.result != "playing" or self.player_hp <= 0:
            return False
        self.attack = Attack(self.player.aim_angle, facing)
        return True

    def _resolve_result(self):
        if self.player_hp <= 0:
            self.result = "defeated"
            self.attack = None
        elif not self.zombie.alive:
            self.result = "cleared"

    def _target_in_strike(self, angle):
        dx, dy = self.zombie.x - self.player.x, self.zombie.y - self.player.y
        distance = math.hypot(dx, dy)
        if distance > 80.0 + _EPSILON:
            return False
        if distance > _EPSILON and abs(math.remainder(
                math.atan2(dy, dx) - angle, math.tau)) > math.radians(50) + _EPSILON:
            return False
        return not any(_wall_blocks(self.player, self.zombie, wall) for wall in self.walls)

    def _move_player(self, dt, axis_x, axis_y, speed):
        if dt > 0:
            move_player(self.player, axis_x, axis_y, dt * speed / WALK_SPEED, self.walls)

    def _move_zombie(self, dt):
        dx, dy = self.player.x - self.zombie.x, self.player.y - self.zombie.y
        distance = math.hypot(dx, dy)
        if distance > 2 * PLAYER_RADIUS:
            self.zombie.aim_angle = math.atan2(dy, dx)
            travel_time = min(dt, (distance - 2 * PLAYER_RADIUS) / WALK_SPEED)
            move_player(self.zombie, dx, dy, travel_time, self.walls)

    def _contact_damage(self):
        distance = math.hypot(self.player.x - self.zombie.x, self.player.y - self.zombie.y)
        if (self.player_invulnerable_remaining == 0 and distance <= 2 * PLAYER_RADIUS + _EPSILON
                and not any(_wall_blocks(self.player, self.zombie, wall) for wall in self.walls)):
            self.player_hp = max(0, self.player_hp - 1)
            self.player_invulnerable_remaining = 1.0
            self._resolve_result()

    def _advance_player_attack(self, dt, axis_x, axis_y):
        attack = self.attack
        if attack is None:
            self._move_player(dt, axis_x, axis_y, WALK_SPEED)
            return False
        end = attack.elapsed + dt
        for boundary in (ATTACK_HIT_TIME, ATTACK_DURATION):
            if abs(end - boundary) <= _EPSILON:
                end = boundary
        active_dt = min(dt, max(0.0, ATTACK_DURATION - attack.elapsed))
        before_hit = (min(active_dt, max(0.0, ATTACK_HIT_TIME - attack.elapsed))
                      if not attack._hit_done else active_dt)
        self._move_player(before_hit, axis_x, axis_y, 60.0)
        hit = False
        if not attack._hit_done and end >= ATTACK_HIT_TIME:
            attack._hit_done = True
            if self._target_in_strike(attack.angle):
                self.zombie.hp -= 1
                self.zombie.stun_remaining = STUN_DURATION
                hit = True
        self._resolve_result()
        if self.result == "playing":
            self._move_player(active_dt - before_hit, axis_x, axis_y, 60.0)
            self._move_player(dt - active_dt, axis_x, axis_y, WALK_SPEED)
        attack.elapsed = min(ATTACK_DURATION, end)
        if attack.elapsed >= ATTACK_DURATION:
            self.attack = None
        return hit

    def update(self, dt, axis_x=0.0, axis_y=0.0):
        self.player.moved = self.zombie.moved = False
        if not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
            return
        player_origin = (self.player.x, self.player.y)
        zombie_origin = (self.zombie.x, self.zombie.y)
        remaining = min(dt, _MAX_UPDATE_DT)
        # 준비 중 추격/접촉도 진행하며 명중 tick에서는 피격을 먼저 처리한다.
        while remaining > _EPSILON:
            tick = min(remaining, _TIME_STEP)
            self._update_tick(tick, axis_x, axis_y)
            remaining -= tick
            if self.result != "playing" and self.attack is None:
                break
        self.player.moved = (self.player.x, self.player.y) != player_origin
        self.zombie.moved = (self.zombie.x, self.zombie.y) != zombie_origin

    def _update_tick(self, dt, axis_x, axis_y):
        self._resolve_result()
        if self.result != "playing":
            # 처치한 공격의 회복만 끝까지 진행하고 새 입력/이동은 중단한다.
            if self.result == "cleared" and self.attack is not None:
                self.attack.elapsed = min(ATTACK_DURATION, self.attack.elapsed + dt)
                if self.attack.elapsed >= ATTACK_DURATION - _EPSILON:
                    self.attack = None
            return
        immunity = self.player_invulnerable_remaining - dt
        self.player_invulnerable_remaining = immunity if immunity > _EPSILON else 0.0
        hit = self._advance_player_attack(dt, axis_x, axis_y)
        if not hit and self.result == "playing":
            previous_stun = self.zombie.stun_remaining
            remaining = previous_stun - dt
            self.zombie.stun_remaining = remaining if remaining > _EPSILON else 0.0
            if self.zombie.stun_remaining == 0:
                self._move_zombie(max(0.0, dt - previous_stun))
                self._contact_damage()
