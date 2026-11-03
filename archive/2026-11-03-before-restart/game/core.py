"""First delivery/combat prototype, independent of graphics and audio."""

from dataclasses import dataclass
from heapq import heappop, heappush
from math import atan2, ceil, hypot, pi, radians, tau


WIDTH = 1280
HEIGHT = 720


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float


@dataclass
class Actor:
    x: float
    y: float
    angle: float = 0.0
    hp: int = 3
    max_hp: int = 3
    radius: float = 18.0
    invulnerable: float = 0.0
    stun: float = 0.0
    state: str = "idle"


@dataclass
class Event:
    kind: str
    x: float
    y: float


@dataclass
class Noise:
    x: float
    y: float
    radius: float
    time: float


def circle_overlaps_rect(x: float, y: float, radius: float, rect: Rect) -> bool:
    nearest_x = max(rect.x, min(x, rect.x + rect.w))
    nearest_y = max(rect.y, min(y, rect.y + rect.h))
    return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 < radius ** 2


def segment_intersects_rect(
    x1: float, y1: float, x2: float, y2: float, rect: Rect
) -> bool:
    """Closed segment versus axis-aligned rectangle, including its boundary."""
    enter, leave = 0.0, 1.0
    for start, delta, low, high in (
        (x1, x2 - x1, rect.x, rect.x + rect.w),
        (y1, y2 - y1, rect.y, rect.y + rect.h),
    ):
        if abs(delta) < 1e-12:
            if not low <= start <= high:
                return False
        else:
            first, last = sorted(((low - start) / delta, (high - start) / delta))
            enter, leave = max(enter, first), min(leave, last)
            if enter > leave:
                return False
    return True


def has_line_of_sight(
    x1: float, y1: float, x2: float, y2: float, walls: list[Rect]
) -> bool:
    return not any(segment_intersects_rect(x1, y1, x2, y2, wall) for wall in walls)


def move_circle(
    x: float, y: float, radius: float, dx: float, dy: float, walls: list[Rect]
) -> tuple[float, float]:
    """Move in small increments, allowing sliding without crossing walls."""
    steps = max(1, ceil(max(abs(dx), abs(dy)) / min(radius, 8.0)))
    for _ in range(steps):
        next_x = max(radius, min(WIDTH - radius, x + dx / steps))
        if not any(circle_overlaps_rect(next_x, y, radius, wall) for wall in walls):
            x = next_x
        next_y = max(100.0 + radius, min(636.0 - radius, y + dy / steps))
        if not any(circle_overlaps_rect(x, next_y, radius, wall) for wall in walls):
            y = next_y
    return x, y


def find_path(start, target, radius: float, walls: list[Rect]):
    """Shortest visible corner route for this small, fixed rectangle map."""
    expanded = [Rect(w.x - radius + 0.01, w.y - radius + 0.01,
                     w.w + radius * 2 - 0.02, w.h + radius * 2 - 0.02)
                for w in walls]

    def free(point):
        x, y = point
        return (radius <= x <= WIDTH - radius
                and 100 + radius <= y <= 636 - radius
                and not any(circle_overlaps_rect(x, y, radius, wall) for wall in walls))

    def clear(first, last):
        # Exact swept-circle clearance also accepts valid positions beside a
        # rounded building corner (an expanded AABB would not).
        dx, dy = last[0] - first[0], last[1] - first[1]
        length_squared = dx * dx + dy * dy
        for wall in walls:
            if segment_intersects_rect(*first, *last, wall):
                return False
            if any(circle_overlaps_rect(*point, radius, wall) for point in (first, last)):
                return False
            for x, y in ((wall.x, wall.y), (wall.x + wall.w, wall.y),
                         (wall.x, wall.y + wall.h), (wall.x + wall.w, wall.y + wall.h)):
                fraction = (max(0.0, min(1.0, ((x - first[0]) * dx + (y - first[1]) * dy)
                                         / length_squared)) if length_squared else 0.0)
                distance_squared = ((x - first[0] - fraction * dx) ** 2
                                    + (y - first[1] - fraction * dy) ** 2)
                if distance_squared < radius * radius - 1e-6:
                    return False
        return True

    # A player's smaller body can make a sound slightly nearer a wall than the
    # zombie can stand. Investigate the nearest reachable edge instead.
    if not free(target):
        x, y = target
        candidates = [(max(radius, min(WIDTH - radius, x)),
                       max(100 + radius, min(636 - radius, y)))]
        for wall in expanded:
            candidates.extend([(wall.x - 1, y), (wall.x + wall.w + 1, y),
                               (x, wall.y - 1), (x, wall.y + wall.h + 1)])
        candidates = [point for point in candidates if free(point)]
        if not candidates:
            return None
        target = min(candidates, key=lambda p: hypot(p[0] - x, p[1] - y))

    nodes = [start, target]
    for wall in expanded:
        nodes.extend(point for point in (
            (wall.x - 1, wall.y - 1), (wall.x + wall.w + 1, wall.y - 1),
            (wall.x - 1, wall.y + wall.h + 1),
            (wall.x + wall.w + 1, wall.y + wall.h + 1),
        ) if free(point))
    distances = [float("inf")] * len(nodes)
    distances[0] = 0.0
    previous = {}
    queue = [(0.0, 0)]
    while queue:
        distance, index = heappop(queue)
        if distance != distances[index]:
            continue
        if index == 1:
            path = [nodes[1]]
            while previous[index] != 0:
                index = previous[index]
                path.append(nodes[index])
            route = [point for point in reversed(path)
                     if hypot(point[0] - start[0], point[1] - start[1]) > 0.01]
            return route or [target]
        for other, point in enumerate(nodes):
            if other == index or not clear(nodes[index], point):
                continue
            candidate = distance + hypot(point[0] - nodes[index][0], point[1] - nodes[index][1])
            if candidate < distances[other]:
                distances[other] = candidate
                previous[other] = index
                heappush(queue, (candidate, other))
    return None


class Game:
    attack_duration = 0.6
    attack_hit_time = 0.18
    zombie_hit_stun = 0.4
    zombie_step_distance = 32.0
    zombie_groan_interval = 3.2
    interaction_radius = 58.0
    flashlight_range = 340.0
    flashlight_half_angle = radians(40.0)
    walk_speed = zombie_speed = 90.0
    run_speed = 135.0
    attack_move_speed = 60.0
    stamina_max = 100.0
    stamina_drain = 25.0
    stamina_recovery = 20.0
    stamina_resume = 25.0
    walk_noise_radius = 80.0
    run_noise_radius = 260.0
    attack_noise_radius = 480.0

    def __init__(self) -> None:
        self._reset("ready")

    def _reset(self, state: str) -> None:
        self.player = Actor(160.0, 160.0)
        self.zombie = Actor(390.0, 300.0, hp=5, max_hp=5, radius=20.0)
        self.walls = [Rect(500.0, 255.0, 280.0, 210.0)]
        self.pickup = (160.0, 160.0)
        self.destination = (1120.0, 565.0)
        self.carrying = False
        self.state = state
        self.time = 0.0
        self.attack_elapsed: float | None = None
        self._attack_impacted = False
        self._events: list[Event] = []
        self.stamina = self.stamina_max
        self.exhausted = False
        self._footstep_distance = 0.0
        self._noises: list[Noise] = []
        self.zombie_target: tuple[float, float] | None = None
        self._target_time = -1.0
        self._zombie_path = []
        self.search_remaining = 0.0
        self._zombie_step_travelled = 0.0
        self._zombie_groan_remaining = 1.0
        self._zombie_step_emitted = False
        self._zombie_groan_emitted = False

    def start(self) -> None:
        if self.state == "ready":
            self.restart()

    def restart(self) -> None:
        self._reset("playing")

    def swing(self) -> bool:
        if self.state != "playing" or self.player.hp <= 0 or self.attack_elapsed is not None:
            return False
        self.attack_elapsed = 0.0
        self._attack_impacted = False
        self.player.state = "attack"
        self._emit_noise("attack", self.attack_noise_radius)
        return True

    def _emit_noise(self, kind: str, radius: float) -> None:
        self._events.append(Event(kind, self.player.x, self.player.y))
        self._noises.append(Noise(self.player.x, self.player.y, radius, self.time))

    def is_visible(self, x: float, y: float) -> bool:
        """Player flashlight point visibility, shared by rendering and interaction."""
        dx, dy = x - self.player.x, y - self.player.y
        distance = hypot(dx, dy)
        if distance <= 1e-9:
            return True
        if distance > self.flashlight_range:
            return False
        difference = (atan2(dy, dx) - self.player.angle + pi) % tau - pi
        return (abs(difference) <= self.flashlight_half_angle + 1e-9
                and has_line_of_sight(self.player.x, self.player.y, x, y, self.walls))

    def interact(self) -> str | None:
        if self.state != "playing":
            return None
        if self.player.hp <= 0:
            self._lose()
            return None
        target = self.destination if self.carrying else self.pickup
        if hypot(target[0] - self.player.x, target[1] - self.player.y) > self.interaction_radius:
            return None
        if not self.is_visible(*target):
            return None
        if self.carrying:
            self.carrying = False
            self.state = "won"
            self.attack_elapsed = None
            self.player.state = "idle"
            kind = "delivered"
        else:
            self.carrying = True
            kind = "pickup"
        self._events.append(Event(kind, *target))
        return kind

    def pop_events(self) -> list[Event]:
        events, self._events = self._events, []
        return events

    def step(
        self, dt: float, move_x: float, move_y: float, running: bool,
        mouse_x: float, mouse_y: float,
    ) -> None:
        if self.state != "playing":
            return
        if self.player.hp <= 0:
            self._lose()
            return
        # A long update can resolve many simulation ticks, but must not queue a
        # burst of stale footsteps or groans for the next rendered frame.
        self._zombie_step_emitted = False
        self._zombie_groan_emitted = False
        # A slow rendered frame must not skip the impact or tunnel through a wall.
        remaining = max(0.0, dt)
        while remaining > 1e-9 and self.state == "playing":
            tick = min(remaining, 1.0 / 60.0)
            self._advance(tick, move_x, move_y, running, mouse_x, mouse_y)
            remaining -= tick

    def _advance(
        self, dt: float, move_x: float, move_y: float, running: bool,
        mouse_x: float, mouse_y: float,
    ) -> None:
        self.time += dt
        player, zombie = self.player, self.zombie
        for actor in (player, zombie):
            actor.invulnerable = max(0.0, actor.invulnerable - dt)
            actor.stun = max(0.0, actor.stun - dt)
        if mouse_x != player.x or mouse_y != player.y:
            player.angle = atan2(mouse_y - player.y, mouse_x - player.x)
        length = max(1.0, hypot(move_x, move_y))
        attacking = self.attack_elapsed is not None
        sprinting = bool(move_x or move_y) and running and not attacking and not self.exhausted and self.stamina > 0
        speed = self.attack_move_speed if attacking else self.run_speed if sprinting else self.walk_speed
        old_x, old_y = player.x, player.y
        player.x, player.y = move_circle(
            player.x, player.y, player.radius,
            move_x / length * speed * dt, move_y / length * speed * dt, self.walls,
        )
        travelled = hypot(player.x - old_x, player.y - old_y)
        moving = travelled > 1e-8
        if sprinting and moving:
            self.stamina = max(0.0, self.stamina - self.stamina_drain * travelled / speed)
            if self.stamina <= 1e-8:
                self.stamina = 0.0
                self.exhausted = True
        else:
            self.stamina = min(self.stamina_max, self.stamina + self.stamina_recovery * dt)
            if self.stamina >= self.stamina_resume:
                self.exhausted = False
        if attacking:
            player.state = "attack"
        elif moving:
            player.state = "run" if sprinting else "walk"
        else:
            player.state = "idle"
        self._footstep_distance += travelled
        if moving and self._footstep_distance >= 36.0:
            self._footstep_distance %= 36.0
            self._emit_noise("run" if sprinting else "walk",
                             self.run_noise_radius if sprinting else self.walk_noise_radius)

        if self.attack_elapsed is not None:
            self.attack_elapsed += dt
            if not self._attack_impacted and self.attack_elapsed >= self.attack_hit_time:
                self._attack_impacted = True
                self._hit()
            if self.attack_elapsed >= self.attack_duration:
                self.attack_elapsed = None

        if zombie.hp > 0:
            zombie_before = (zombie.x, zombie.y)
            self._update_zombie(dt)
            self._zombie_step_travelled += hypot(zombie.x - zombie_before[0],
                                                 zombie.y - zombie_before[1])
            if self._zombie_step_travelled >= self.zombie_step_distance:
                self._zombie_step_travelled %= self.zombie_step_distance
                if not self._zombie_step_emitted:
                    self._events.append(Event("zombie_step", zombie.x, zombie.y))
                    self._zombie_step_emitted = True
            self._zombie_groan_remaining -= dt
            if self._zombie_groan_remaining <= 1e-9:
                self._zombie_groan_remaining = self.zombie_groan_interval
                if not self._zombie_groan_emitted:
                    self._events.append(Event("zombie_groan", zombie.x, zombie.y))
                    self._zombie_groan_emitted = True
            if zombie.stun <= 0.0 and player.invulnerable <= 0.0 and hypot(
                player.x - zombie.x, player.y - zombie.y
            ) <= player.radius + zombie.radius:
                player.hp = max(0, player.hp - 1)
                player.invulnerable = 1.0
                player.stun = 0.12
                self._events.append(Event("hurt", player.x, player.y))
                if player.hp == 0:
                    self._lose()
        self._noises.clear()

    def _update_zombie(self, dt: float) -> None:
        player, zombie = self.player, self.zombie
        visible = hypot(player.x - zombie.x, player.y - zombie.y) <= 230.0 and has_line_of_sight(
            zombie.x, zombie.y, player.x, player.y, self.walls)
        if visible:
            self.zombie_target = (player.x, player.y)
            self._target_time = self.time
            self.search_remaining = 0.0
        else:
            heard = [noise for noise in self._noises
                     if noise.time >= self._target_time
                     and hypot(noise.x - zombie.x, noise.y - zombie.y) <= noise.radius]
            if heard:
                latest = max(heard, key=lambda noise: noise.time)
                self.zombie_target = (latest.x, latest.y)
                self._target_time = latest.time
                self.search_remaining = 0.0
        if zombie.stun > 0:
            zombie.state = "stunned"
            return
        if self.zombie_target is not None:
            zombie.state = "chase" if visible else "investigate"
            self._zombie_path = find_path((zombie.x, zombie.y), self.zombie_target,
                                          zombie.radius, self.walls)
            if self._zombie_path:
                waypoint = self._zombie_path[0]
                dx, dy = waypoint[0] - zombie.x, waypoint[1] - zombie.y
                distance = hypot(dx, dy)
                if distance > 0:
                    zombie.angle = atan2(dy, dx)
                    travel = min(distance, self.zombie_speed * dt)
                    zombie.x, zombie.y = move_circle(
                        zombie.x, zombie.y, zombie.radius,
                        dx / distance * travel, dy / distance * travel, self.walls)
                arrived = hypot(zombie.x - self._zombie_path[-1][0],
                                zombie.y - self._zombie_path[-1][1]) <= 2.0
            else:
                arrived = True
            if arrived and not visible:
                self.zombie_target = None
                self._zombie_path = []
                self.search_remaining = 3.0
                zombie.state = "search"
        elif self.search_remaining > 0:
            zombie.state = "search"
            zombie.angle += dt * 1.5
            self.search_remaining = max(0.0, self.search_remaining - dt)
            if self.search_remaining == 0:
                zombie.state = "idle"
        else:
            zombie.state = "idle"

    def _hit(self) -> None:
        player, zombie = self.player, self.zombie
        if zombie.hp <= 0:
            return
        dx, dy = zombie.x - player.x, zombie.y - player.y
        angle = atan2(dy, dx) if dx or dy else player.angle
        difference = (angle - player.angle + pi) % tau - pi
        if hypot(dx, dy) > 88.0 or abs(difference) > min(radians(50.0), self.flashlight_half_angle) + 1e-9:
            return
        if not has_line_of_sight(player.x, player.y, zombie.x, zombie.y, self.walls):
            return
        zombie.hp = max(0, zombie.hp - 1)
        zombie.stun = self.zombie_hit_stun
        self._events.append(Event("hit", zombie.x, zombie.y))
        zombie.state = "stunned" if zombie.hp > 0 else "dead"
        if zombie.hp == 0:
            zombie.stun = 0.0
            self.zombie_target = None
            self._zombie_path = []
            self.search_remaining = 0.0
            self._zombie_step_travelled = 0.0
            self._zombie_groan_remaining = self.zombie_groan_interval
            self._events = [event for event in self._events
                            if event.kind not in ("zombie_step", "zombie_groan")]
            self._events.append(Event("dead", zombie.x, zombie.y))

    def _lose(self) -> None:
        self.state = "lost"
        self.player.state = "dead"
        self.attack_elapsed = None
