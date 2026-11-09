"""R2-A 렌더링과 독립된 단일 좀비 전투 판정."""
from dataclasses import dataclass, field
import math

if __package__:
    from .core import Player, Wall, move_player, PLAYER_RADIUS, WALK_SPEED
    from .locomotion import is_backstep, select_facing
else:
    from core import Player, Wall, move_player, PLAYER_RADIUS, WALK_SPEED
    from locomotion import is_backstep, select_facing


ATTACK_DURATION = 0.6
ATTACK_HIT_TIME = 0.18
ATTACK_RANGE = 70.0
ATTACK_HALF_ANGLE = math.radians(30)
_STATIONARY_FRONT_RIGHT_DURATION = 0.66
_STATIONARY_FRONT_RIGHT_HIT_TIME = 0.24
STUN_DURATION = 0.70
BACKSTEP_SPEED = 65.0
_HIT_RECOIL_DURATION = 0.10
_HIT_RECOIL_DISTANCE = 8.0
ZOMBIE_ATTACK_DURATION = 0.8
ZOMBIE_ATTACK_HIT_TIME = 0.3
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
class ZombieAttack:
    angle: float
    facing: str
    elapsed: float = 0.0
    _hit_done: bool = False


@dataclass
class Zombie(Player):
    hp: int = 5
    stun_remaining: float = 0.0
    attack: ZombieAttack | None = None
    recoil_angle: float | None = None
    recoil_offset: tuple[float, float] = field(default=(0.0, 0.0), init=False)

    @property
    def alive(self):
        return self.hp > 0


@dataclass
class Attack:
    angle: float
    facing: str
    elapsed: float = 0.0
    _hit_done: bool = False
    landed: bool = False
    stationary_front_right: bool = False

    @property
    def hit_time(self) -> float:
        return _STATIONARY_FRONT_RIGHT_HIT_TIME if self.stationary_front_right else ATTACK_HIT_TIME

    @property
    def duration(self) -> float:
        return _STATIONARY_FRONT_RIGHT_DURATION if self.stationary_front_right else ATTACK_DURATION


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

    def start_attack(self, facing="front_right", *, stationary_front_right=False):
        self._resolve_result()
        if self.attack is not None or self.result != "playing" or self.player_hp <= 0:
            return False
        self.attack = Attack(self.player.aim_angle, facing,
                             stationary_front_right=facing == "front_right" and bool(stationary_front_right))
        return True

    def _resolve_result(self):
        if self.player_hp <= 0:
            self.result = "defeated"
            self.attack = None
        elif not self.zombie.alive:
            self.result = "cleared"
        if self.result != "playing":
            self.zombie.attack = None

    def _target_in_strike(self, angle):
        dx, dy = self.zombie.x - self.player.x, self.zombie.y - self.player.y
        distance = math.hypot(dx, dy)
        if distance > ATTACK_RANGE + _EPSILON:
            return False
        if distance > _EPSILON and abs(math.remainder(
                math.atan2(dy, dx) - angle, math.tau)) > ATTACK_HALF_ANGLE + _EPSILON:
            return False
        return not any(_wall_blocks(self.player, self.zombie, wall) for wall in self.walls)

    def _move_zombie(self, dt):
        dx, dy = self.player.x - self.zombie.x, self.player.y - self.zombie.y
        distance = math.hypot(dx, dy)
        if distance > 2 * PLAYER_RADIUS:
            self.zombie.aim_angle = math.atan2(dy, dx)
            travel_time = min(dt, (distance - 2 * PLAYER_RADIUS) / WALK_SPEED)
            move_player(self.zombie, dx, dy, travel_time, self.walls)
            return travel_time
        return 0.0

    def _zombie_target_in_strike(self, angle):
        dx, dy = self.player.x - self.zombie.x, self.player.y - self.zombie.y
        distance = math.hypot(dx, dy)
        if distance > 2 * PLAYER_RADIUS + _EPSILON:
            return False
        if distance > _EPSILON and abs(math.remainder(
                math.atan2(dy, dx) - angle, math.tau)) > math.radians(50) + _EPSILON:
            return False
        return not any(_wall_blocks(self.zombie, self.player, wall) for wall in self.walls)

    def _start_zombie_attack(self):
        angle = math.atan2(self.player.y - self.zombie.y, self.player.x - self.zombie.x)
        if not self._zombie_target_in_strike(angle):
            return False
        self.zombie.aim_angle = angle
        self.zombie.attack = ZombieAttack(angle, select_facing(angle))
        return True

    def _update_zombie(self, dt):
        if dt <= _EPSILON:
            return
        if self.zombie.attack is None and not self._start_zombie_attack():
            travel_time = self._move_zombie(dt)
            if not self._start_zombie_attack():
                return
            dt -= travel_time
            if dt <= _EPSILON:
                return
        attack = self.zombie.attack
        end = attack.elapsed + dt
        for boundary in (ZOMBIE_ATTACK_HIT_TIME, ZOMBIE_ATTACK_DURATION):
            if abs(end - boundary) <= _EPSILON:
                end = boundary
        if not attack._hit_done and end >= ZOMBIE_ATTACK_HIT_TIME:
            attack._hit_done = True
            if self.player_invulnerable_remaining == 0 and self._zombie_target_in_strike(attack.angle):
                self.player_hp = max(0, self.player_hp - 1)
                self.player_invulnerable_remaining = 1.0
        attack.elapsed = min(end, ZOMBIE_ATTACK_DURATION)
        if attack.elapsed >= ZOMBIE_ATTACK_DURATION:
            self.zombie.attack = None
        self._resolve_result()

    def _advance_player_attack(self, dt):
        attack = self.attack
        if attack is None:
            return False
        hit_time, duration = attack.hit_time, attack.duration
        end = attack.elapsed + dt
        for boundary in (hit_time, duration):
            if abs(end - boundary) <= _EPSILON:
                end = boundary
        hit = False
        if not attack._hit_done and end >= hit_time:
            attack._hit_done = True
            if self._target_in_strike(attack.angle):
                self.zombie.hp -= 1
                attack.landed = True
                self.zombie.stun_remaining = STUN_DURATION
                self.zombie.attack = None
                if self.zombie.alive:
                    dx = self.zombie.x - self.player.x
                    dy = self.zombie.y - self.player.y
                    self.zombie.recoil_angle = math.atan2(dy, dx) if dx or dy else attack.angle
                hit = True
        self._resolve_result()
        attack.elapsed = min(duration, end)
        if attack.elapsed >= duration:
            self.attack = None
        return hit

    def update(self, dt, axis_x=0.0, axis_y=0.0, *, facing_hint=None):
        self.player.moved = self.zombie.moved = False
        self.zombie.recoil_offset = (0.0, 0.0)
        if not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
            return
        player_origin = (self.player.x, self.player.y)
        zombie_origin = (self.zombie.x, self.zombie.y)
        facing = select_facing(self.player.aim_angle, facing_hint)
        walk_scale = BACKSTEP_SPEED / WALK_SPEED if is_backstep(facing, axis_x, axis_y) else 1.0
        remaining = min(dt, _MAX_UPDATE_DT)
        # 준비 중 추격/접촉도 진행하며 명중 tick에서는 피격을 먼저 처리한다.
        while remaining > _EPSILON:
            tick = min(remaining, _TIME_STEP)
            # End ticks at combat events so partial external frames lose no time.
            player_attack = self.attack
            player_boundaries = (player_attack.hit_time, player_attack.duration) if player_attack is not None else ()
            for attack, boundaries in ((player_attack, player_boundaries),
                    (self.zombie.attack, (ZOMBIE_ATTACK_HIT_TIME, ZOMBIE_ATTACK_DURATION))):
                if attack is not None:
                    for boundary in boundaries:
                        until = boundary - attack.elapsed
                        if until > _EPSILON:
                            tick = min(tick, until)
            for timer in (self.zombie.stun_remaining, self.player_invulnerable_remaining):
                if timer > _EPSILON:
                    tick = min(tick, timer)
            self._update_tick(tick, axis_x, axis_y, walk_scale)
            remaining -= tick
            if self.result != "playing" and self.attack is None:
                break
        self.player.moved = (self.player.x, self.player.y) != player_origin
        self.zombie.moved = (self.zombie.x, self.zombie.y) != zombie_origin

    def _update_tick(self, dt, axis_x, axis_y, walk_scale):
        self._resolve_result()
        if self.result != "playing":
            # 처치한 공격의 회복만 끝까지 진행하고 새 입력/이동은 중단한다.
            if self.result == "cleared" and self.attack is not None:
                duration = self.attack.duration
                self.attack.elapsed = min(duration, self.attack.elapsed + dt)
                if self.attack.elapsed >= duration - _EPSILON:
                    self.attack = None
            return
        immunity = self.player_invulnerable_remaining - dt
        self.player_invulnerable_remaining = immunity if immunity > _EPSILON else 0.0
        if self.attack is None:
            move_player(self.player, axis_x, axis_y, dt * walk_scale, self.walls)
        hit = self._advance_player_attack(dt)
        if self.zombie.stun_remaining > 0:
            self.zombie.attack = None
        if not hit and self.result == "playing":
            previous_stun = self.zombie.stun_remaining
            remaining = previous_stun - dt
            if self.zombie.recoil_angle is not None:
                recoil_left = previous_stun - (STUN_DURATION - _HIT_RECOIL_DURATION)
                recoil_dt = min(dt, max(0.0, recoil_left))
                angle = self.zombie.recoil_angle
                x, y = self.zombie.x, self.zombie.y
                move_player(self.zombie, math.cos(angle), math.sin(angle),
                            recoil_dt * _HIT_RECOIL_DISTANCE / (_HIT_RECOIL_DURATION * WALK_SPEED),
                            self.walls)
                dx, dy = self.zombie.recoil_offset
                self.zombie.recoil_offset = (dx + (self.zombie.x - x), dy + (self.zombie.y - y))
                if recoil_left - dt <= _EPSILON:
                    self.zombie.recoil_angle = None
            self.zombie.stun_remaining = remaining if remaining > _EPSILON else 0.0
            if self.zombie.stun_remaining == 0:
                self._update_zombie(max(0.0, dt - previous_stun))
