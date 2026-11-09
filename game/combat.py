"""R2-A 렌더링과 독립된 단일 좀비 전투 판정."""
from dataclasses import dataclass, field
import math

if __package__:
    from .core import Player, Wall, move_player, wall_blocks, PLAYER_RADIUS, WALK_SPEED
    from .locomotion import is_backstep, select_facing
    from .zombie_navigation import find_route
else:
    from core import Player, Wall, move_player, wall_blocks, PLAYER_RADIUS, WALK_SPEED
    from locomotion import is_backstep, select_facing
    from zombie_navigation import find_route


ATTACK_DURATION = 0.6
ATTACK_HIT_TIME = 0.18
ATTACK_RANGE = 70.0
ATTACK_HALF_ANGLE = math.radians(30)
_STATIONARY_FRONT_RIGHT_DURATION = 0.66
_STATIONARY_FRONT_RIGHT_HIT_TIME = 0.24
STUN_DURATION = 0.70
BACKSTEP_SPEED = 65.0
SPRINT_SPEED = 135.0
MAX_STAMINA = 100.0
_SPRINT_DRAIN = 25.0
_STAMINA_RECOVERY = 20.0
_SPRINT_RECOVERY_THRESHOLD = 25.0
_STAMINA_EPSILON = 1e-8
_HIT_RECOIL_DURATION = 0.10
_HIT_RECOIL_DISTANCE = 8.0
ZOMBIE_ATTACK_DURATION = 0.8
ZOMBIE_ATTACK_HIT_TIME = 0.3
_EPSILON = 1e-12
_TIME_STEP = 0.001
_MAX_UPDATE_DT = 10.0
_ZOMBIE_SIGHT_RANGE = 230.0
_SEARCH_DURATION = 3.0
_SEARCH_TURN_SPEED = 1.5
_FOOTSTEP_SPACING = 36.0
_WALK_NOISE_RANGE = 80.0
_SPRINT_NOISE_RANGE = 260.0
_ATTACK_NOISE_RANGE = 480.0


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
    state: str = "idle"
    target: tuple[float, float] | None = None
    search_remaining: float = 0.0

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
        self.stamina = MAX_STAMINA
        self._sprint_exhausted = False
        self._footstep_distance = 0.0
        self.sprint_step = None
        self._heard_at = None
        self._investigation_route = None
        self.player_invulnerable_remaining = 0.0
        self.attack = None
        self.result = "playing"

    def start_attack(self, facing="front_right", *, stationary_front_right=False):
        self._resolve_result()
        if self.attack is not None or self.result != "playing" or self.player_hp <= 0:
            return False
        self.attack = Attack(self.player.aim_angle, facing,
                             stationary_front_right=facing == "front_right" and bool(stationary_front_right))
        self._emit_noise(_ATTACK_NOISE_RANGE)
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
        return self._player_line_clear()

    def _player_line_clear(self):
        player = (self.player.x, self.player.y)
        zombie = (self.zombie.x, self.zombie.y)
        return not any(wall_blocks(zombie, player, wall) for wall in self.walls)

    def _emit_noise(self, radius):
        position = (self.player.x, self.player.y)
        if math.dist(position, (self.zombie.x, self.zombie.y)) <= radius + _EPSILON:
            self._heard_at = position

    def _perceive_player(self):
        zombie = self.zombie
        position = (self.player.x, self.player.y)
        if (math.dist(position, (zombie.x, zombie.y)) <= _ZOMBIE_SIGHT_RANGE + _EPSILON
                and self._player_line_clear()):
            zombie.state = "chase"
            zombie.target = position
            zombie.search_remaining = 0.0
            self._investigation_route = None
        elif self._heard_at is not None or zombie.state == "chase":
            target = self._heard_at if self._heard_at is not None else zombie.target
            if zombie.state != "investigate" or zombie.target != target:
                self._investigation_route = None
            zombie.state = "investigate"
            zombie.target = target
            zombie.search_remaining = 0.0
        self._heard_at = None

    def _move_zombie_toward(self, target, dt, *, stop_distance=0.0):
        dx, dy = target[0] - self.zombie.x, target[1] - self.zombie.y
        distance = math.hypot(dx, dy)
        if distance > stop_distance + _EPSILON:
            self.zombie.aim_angle = math.atan2(dy, dx)
            travel_time = min(dt, (distance - stop_distance) / WALK_SPEED)
            move_player(self.zombie, dx, dy, travel_time, self.walls)
            return travel_time
        return 0.0

    def _investigate_and_search(self, dt):
        zombie = self.zombie
        if zombie.state == "investigate":
            if self._investigation_route is None:
                self._investigation_route = find_route((zombie.x, zombie.y), zombie.target, self.walls)
            route = self._investigation_route
            while route and dt > _EPSILON:
                waypoint = route[0]
                dt -= self._move_zombie_toward(waypoint, dt)
                if math.dist((zombie.x, zombie.y), waypoint) > 1e-7:
                    return
                route.pop(0)
            if route:
                return
            zombie.state = "search"
            zombie.search_remaining = _SEARCH_DURATION
        if zombie.state == "search":
            duration = min(dt, zombie.search_remaining)
            zombie.aim_angle = math.remainder(zombie.aim_angle + duration * _SEARCH_TURN_SPEED, math.tau)
            zombie.search_remaining -= duration
            if zombie.search_remaining <= _EPSILON:
                zombie.search_remaining = 0.0
                zombie.target = None
                zombie.state = "idle"

    def _zombie_target_in_strike(self, angle):
        dx, dy = self.player.x - self.zombie.x, self.player.y - self.zombie.y
        distance = math.hypot(dx, dy)
        if distance > 2 * PLAYER_RADIUS + _EPSILON:
            return False
        if distance > _EPSILON and abs(math.remainder(
                math.atan2(dy, dx) - angle, math.tau)) > math.radians(50) + _EPSILON:
            return False
        return self._player_line_clear()

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
        if self.zombie.attack is None and self.zombie.state != "chase":
            self._investigate_and_search(dt)
            return
        if self.zombie.attack is None and not self._start_zombie_attack():
            travel_time = self._move_zombie_toward(self.zombie.target, dt, stop_distance=2 * PLAYER_RADIUS)
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

    def update(self, dt, axis_x=0.0, axis_y=0.0, *, facing_hint=None, sprint=False):
        self.player.moved = self.zombie.moved = False
        self.zombie.recoil_offset = (0.0, 0.0)
        self.sprint_step = None
        if not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
            return
        player_origin = (self.player.x, self.player.y)
        zombie_origin = (self.zombie.x, self.zombie.y)
        facing = select_facing(self.player.aim_angle, facing_hint)
        backstep = is_backstep(facing, axis_x, axis_y)
        walk_scale = BACKSTEP_SPEED / WALK_SPEED if backstep else 1.0
        wants_sprint = sprint and not backstep and bool(axis_x or axis_y)
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
            if self._sprint_exhausted:
                until_recovered = (_SPRINT_RECOVERY_THRESHOLD - self.stamina) / _STAMINA_RECOVERY
                if until_recovered > _EPSILON:
                    tick = min(tick, until_recovered)
            elif wants_sprint and player_attack is None:
                tick = min(tick, self.stamina / _SPRINT_DRAIN)
            self._update_tick(tick, axis_x, axis_y, walk_scale, wants_sprint)
            remaining -= tick
            if self.result != "playing" and self.attack is None:
                break
        self.player.moved = (self.player.x, self.player.y) != player_origin
        self.zombie.moved = (self.zombie.x, self.zombie.y) != zombie_origin

    def _move_player_and_update_stamina(self, dt, axis_x, axis_y, walk_scale, wants_sprint):
        sprinting = wants_sprint and not self._sprint_exhausted and self.attack is None
        if self.attack is None:
            origin = (self.player.x, self.player.y)
            scale = SPRINT_SPEED / WALK_SPEED if sprinting else walk_scale
            move_player(self.player, axis_x, axis_y, dt * scale, self.walls)
            if self.player.moved:
                self._footstep_distance += math.dist(origin, (self.player.x, self.player.y))
                if self._footstep_distance >= _FOOTSTEP_SPACING - 1e-8:
                    self._footstep_distance = max(0.0, self._footstep_distance - _FOOTSTEP_SPACING)
                    self._emit_noise(_SPRINT_NOISE_RANGE if sprinting else _WALK_NOISE_RANGE)
                    if sprinting:
                        self.sprint_step = (self.player.x, self.player.y)
        if sprinting and self.player.moved:
            self.stamina = max(0.0, self.stamina - _SPRINT_DRAIN * dt)
            if self.stamina <= _STAMINA_EPSILON:
                self.stamina = 0.0
                self._sprint_exhausted = True
            return
        self.stamina = min(MAX_STAMINA, self.stamina + _STAMINA_RECOVERY * dt)
        if self._sprint_exhausted and self.stamina >= _SPRINT_RECOVERY_THRESHOLD - _STAMINA_EPSILON:
            self.stamina = max(self.stamina, _SPRINT_RECOVERY_THRESHOLD)
            self._sprint_exhausted = False

    def _update_tick(self, dt, axis_x, axis_y, walk_scale, wants_sprint):
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
        self._move_player_and_update_stamina(dt, axis_x, axis_y, walk_scale, wants_sprint)
        self._perceive_player()
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
