"""Delivery contracts across the town and its connected alleys."""
from dataclasses import dataclass
import json
import math
from pathlib import Path

if __package__:
    from .combat import ATTACK_RANGE, ZOMBIE_APPEARANCES, CombatWorld, Zombie
    from .core import PLAYER_RADIUS, Player, Wall, wall_blocks, wall_entry
    from .zombie_navigation import can_walk_direct
else:
    from combat import ATTACK_RANGE, ZOMBIE_APPEARANCES, CombatWorld, Zombie
    from core import PLAYER_RADIUS, Player, Wall, wall_blocks, wall_entry
    from zombie_navigation import can_walk_direct


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
MAX_WAYPOINTS = 8
_WAYPOINT_REACH = 32.0
_INTERACTION_HOLD_TIMES = {"pickup": 0.50, "deliver": 1.00, "gate": 0.70}
GATE_NOISE_RANGE = 230.0
VEHICLE_ALARM_RANGE = 520.0
_VEHICLE_TEXTURES = ("parked-car", "abandoned-car")
BOTTLE_THROW_RANGE = 320.0
BOTTLE_NOISE_RANGE = 320.0
BOTTLE_FLIGHT_TIME = 0.30
_BOTTLE_STARTS = ((177, 127), (610, 628), (1660, 932), (3230, 2070))
_REAR_ALLEY_PATROL = ((3180, 2227), (3060, 2227))
_REAR_ALLEY_ZOMBIES = ((2865, 2227), _REAR_ALLEY_PATROL[0])
_SHOP_ZOMBIE_STARTS = (
    *ZOMBIE_STARTS[:16], (1865, 975), (1930, 950), (1978, 942),
    (2030, 973), (2005, 1015), *ZOMBIE_STARTS[21:],
)


@dataclass(frozen=True)
class DeliveryStop:
    name: str
    position: tuple[float, float]


@dataclass(frozen=True)
class DeliveryContract:
    name: str
    description: str
    difficulty: str
    destination: tuple[float, float]
    zombie_starts: tuple[tuple[float, float], ...]
    stops: tuple[DeliveryStop, ...] = ()

    def __post_init__(self):
        if not self.stops:
            object.__setattr__(self, "stops", (DeliveryStop(self.name, self.destination),))


_SINGLE_CONTRACTS = (
    DeliveryContract(
        "상점 앞", "가로등 아래 모여 있는 좀비 무리", "보통",
        (1958.0, 1037.0), _SHOP_ZOMBIE_STARTS,
    ),
    DeliveryContract(
        "주택 뒷문", "순찰 좀비가 오가는 어두운 골목", "어려움",
        (3149.0, 2227.0),
        (*ZOMBIE_STARTS[:-2], *_REAR_ALLEY_ZOMBIES),
    ),
)
DELIVERY_CONTRACTS = (
    *_SINGLE_CONTRACTS,
    DeliveryContract(
        "두 곳 배달", "상점 앞·주택 뒷문 순서 자유", "어려움",
        _SINGLE_CONTRACTS[0].destination,
        (*_SHOP_ZOMBIE_STARTS[:-2], *_REAR_ALLEY_ZOMBIES),
        tuple(contract.stops[0] for contract in _SINGLE_CONTRACTS),
    ),
)


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


@dataclass
class BottleFlight:
    origin: tuple[float, float]
    destination: tuple[float, float]
    elapsed: float = 0.0

    @property
    def progress(self):
        return min(1.0, self.elapsed / BOTTLE_FLIGHT_TIME)


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
    zombie_sight_half_angle = math.pi / 3
    world_size = TOWN_SIZE
    pickup = (172.0, 155.0)
    contract = DELIVERY_CONTRACTS[1]
    props = tuple(StreetProp(x, y, texture) for texture, positions in _STREET_PROPS.items() for x, y in positions)
    streetlights = (
        (240, 525), (710, 659), (1380, 890), (1620, 1200),
        (1960, 990), (2660, 110), (3290, 530), (3290, 1350),
        (2290, 1750), (2730, 1935), (3340, 2070),
    )

    def __init__(self, *, two_stop_unlocked: bool = False):
        self.two_stop_unlocked = two_stop_unlocked
        super().__init__()

    @property
    def destination(self):
        return self.contract.destination

    @property
    def available_contracts(self):
        return DELIVERY_CONTRACTS if self.two_stop_unlocked else _SINGLE_CONTRACTS

    def select_contract(self, index):
        contracts = self.available_contracts
        if not 0 <= index < len(contracts):
            return False
        self.contract = contracts[index]
        self.reset()
        return True

    def reset(self):
        super().reset()
        self._starting_player_hp = self.player_hp
        self.attack_count = 0
        self.elapsed_play_time = 0.0
        self.player = Player(*PLAYER_START)
        self.zombies = []
        has_patrol = _SINGLE_CONTRACTS[1].stops[0] in self.contract.stops
        for index, position in enumerate(self.contract.zombie_starts):
            patrol = _REAR_ALLEY_PATROL if has_patrol and position == _REAR_ALLEY_PATROL[0] else None
            self.zombies.append(Zombie(
                *position, aim_angle=math.pi if patrol else Player.aim_angle,
                state="patrol" if patrol else "idle", patrol_points=patrol,
                appearance=ZOMBIE_APPEARANCES[index % len(ZOMBIE_APPEARANCES)],
            ))
        self.gate = NeighborhoodWall(3140, 2190, 50, 12, "iron-gate", height=38)
        self.gate_position = (self.gate.x + self.gate.width / 2, self.gate.y + self.gate.depth / 2)
        self.walls = [
            NeighborhoodWall(88, 305, 140, 190, "west-house", oblique=True),
            NeighborhoodWall(310, 225, 275, 200, "east-house", oblique=True),
            NeighborhoodWall(345, 164, 100, 12, "fence", height=38),
            # Leave a 72px alley between the rear house wall and the fence.
            *(NeighborhoodWall(x, 2272, 110, 12, "fence", height=38)
              for x in (2848, 2958, 3068)),
            NeighborhoodWall(3178, 2272, 72, 12, "fence", height=38),
            NeighborhoodWall(3125, 2190, 15, 12, "fence", height=38),
            self.gate,
            NeighborhoodWall(3190, 2190, 20, 12, "fence", height=38),
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
        self._clear_interaction()
        self.waypoints: list[tuple[float, float]] = []
        self.completed_stops: set[DeliveryStop] = set()
        self.just_unlocked_two_stop = False
        self.bottle_pickups = list(_BOTTLE_STARTS)
        self.has_bottle = False
        self.bottle_flight = None
        self.bottle_impact = None
        self.vehicle_alarm = None
        self.vehicle_alarm_source = None
        self.vehicle_hit = None
        self._triggered_vehicle_alarms = set()

    @property
    def next_stop(self):
        if self.parcel == "waiting":
            return self.pickup
        remaining = self.remaining_stops
        return remaining[0].position if remaining else self.destination

    @property
    def remaining_stops(self):
        return tuple(stop for stop in self.contract.stops if stop not in self.completed_stops)

    def add_waypoint(self, position: tuple[float, float]) -> bool:
        if len(self.waypoints) >= MAX_WAYPOINTS:
            return False
        x, y = position
        width, height = self.world_size
        if not (0 <= x <= width and 0 <= y <= height):
            return False
        self.waypoints.append((x, y))
        return True

    def remove_last_waypoint(self) -> bool:
        if not self.waypoints:
            return False
        self.waypoints.pop()
        return True

    def advance_waypoint(self) -> bool:
        if not self.waypoints or self.result != "playing" or self.player_hp <= 0:
            return False
        origin = (self.player.x, self.player.y)
        target = self.waypoints[0]
        if math.dist(origin, target) > _WAYPOINT_REACH or any(
                wall_blocks(origin, target, wall) for wall in self.walls):
            return False
        self.waypoints.pop(0)
        return True

    @property
    def combat_free(self):
        return self.attack_count == 0 and self.player_hp == self._starting_player_hp

    def start_attack(self, facing="front_right", *, stationary_front_right=False):
        started = super().start_attack(facing, stationary_front_right=stationary_front_right)
        if started:
            self.attack_count += 1
        return started

    @property
    def nearby_bottle(self):
        if self.has_bottle or self.result != "playing" or self.player_hp <= 0:
            return None
        origin = (self.player.x, self.player.y)
        return min((point for point in self.bottle_pickups
                    if math.dist(origin, point) <= INTERACTION_RANGE
                    and not any(wall_blocks(origin, point, wall) for wall in self.walls)),
                   key=lambda point: math.dist(origin, point), default=None)

    def pick_up_bottle(self):
        point = self.nearby_bottle
        if point is None:
            return False
        self.bottle_pickups.remove(point)
        self.has_bottle = True
        return True

    def throw_bottle(self, target):
        destination = self._bottle_destination(target)
        if destination is None:
            return False
        self.bottle_flight = BottleFlight((self.player.x, self.player.y), destination)
        self.has_bottle = False
        return True

    def can_throw_bottle(self, target):
        return self._bottle_destination(target) is not None

    def _bottle_destination(self, target):
        if (not self.has_bottle or self.bottle_flight is not None or self.attack is not None
                or self.result != "playing" or self.player_hp <= 0):
            return None
        origin = (self.player.x, self.player.y)
        dx, dy = target[0] - origin[0], target[1] - origin[1]
        distance = math.hypot(dx, dy)
        if not math.isfinite(distance) or distance <= 1e-9:
            return None
        direction = (dx / distance, dy / distance)
        travel = min(distance, BOTTLE_THROW_RANGE)
        for start, heading, size in zip(origin, direction, self.world_size):
            if heading > 0:
                travel = min(travel, (size - PLAYER_RADIUS - start) / heading)
            elif heading < 0:
                travel = min(travel, (PLAYER_RADIUS - start) / heading)
        if travel <= 1e-9:
            return None

        def landing(length):
            return origin[0] + direction[0] * length, origin[1] + direction[1] * length

        destination = landing(travel)
        # Use zombie clearance so a bottle stopped by a wall can still be reached.
        if not can_walk_direct(origin, destination, self.walls):
            clear, blocked = 0.0, travel
            for _ in range(20):
                middle = (clear + blocked) / 2
                if can_walk_direct(origin, landing(middle), self.walls):
                    clear = middle
                else:
                    blocked = middle
            travel = clear
            destination = landing(travel)
        return destination if travel > 1e-9 else None

    def update(self, dt, axis_x=0.0, axis_y=0.0, *, facing_hint=None, sprint=False, sneak=False):
        self.bottle_impact = None
        self.vehicle_alarm = None
        self.vehicle_alarm_source = None
        self.vehicle_hit = None
        super().update(dt, axis_x, axis_y, facing_hint=facing_hint, sprint=sprint, sneak=sneak)
        if self.result != "playing":
            self.bottle_flight = None

    @staticmethod
    def _is_vehicle(wall):
        return isinstance(wall, NeighborhoodWall) and wall.texture in _VEHICLE_TEXTURES

    def _can_trigger_vehicle_alarm(self, wall):
        return (self._is_vehicle(wall)
                and (wall.x, wall.y) not in self._triggered_vehicle_alarms)

    def _trigger_vehicle_alarm(self, wall, position):
        self._triggered_vehicle_alarms.add((wall.x, wall.y))
        self.vehicle_alarm = position
        self.vehicle_alarm_source = (wall.x + wall.width / 2, wall.y + wall.depth / 2)
        self._emit_noise(VEHICLE_ALARM_RANGE, position)

    def _on_sprint_collision(self, wall):
        if self._can_trigger_vehicle_alarm(wall):
            self._trigger_vehicle_alarm(wall, (self.player.x, self.player.y))

    def _on_attack_impact(self, angle):
        origin = self.player.x, self.player.y
        dx, dy = ATTACK_RANGE * math.cos(angle), ATTACK_RANGE * math.sin(angle)
        end = origin[0] + dx, origin[1] + dy
        closest, entry = None, math.inf
        for wall in self.walls:
            fraction = wall_entry(origin, end, wall)
            if fraction is not None and fraction < entry:
                closest, entry = wall, fraction
        if not self._is_vehicle(closest):
            return
        self.vehicle_hit = (origin[0] + dx * entry, origin[1] + dy * entry)
        if not self._can_trigger_vehicle_alarm(closest):
            return
        # Keep the investigation point on the approachable side of the vehicle.
        radius = PLAYER_RADIUS
        padded = Wall(closest.x - radius, closest.y - radius,
                      closest.width + 2 * radius, closest.depth + 2 * radius)
        fraction = wall_entry(origin, end, padded)
        position = (origin[0] + dx * fraction, origin[1] + dy * fraction)
        if not can_walk_direct(origin, position, self.walls):
            position = origin
        self._trigger_vehicle_alarm(closest, position)

    def _advance_world_objects(self, dt):
        self.elapsed_play_time += dt
        flight = self.bottle_flight
        if flight is None:
            return
        flight.elapsed += dt
        if flight.elapsed >= BOTTLE_FLIGHT_TIME - 1e-9:
            self.bottle_flight = None
            self.bottle_impact = flight.destination
            self._emit_noise(BOTTLE_NOISE_RANGE, flight.destination)

    @property
    def interaction_target(self):
        if self.result != "playing" or self.player_hp <= 0:
            return None
        origin = (self.player.x, self.player.y)
        targets = ((self.pickup,) if self.parcel == "waiting"
                   else (stop.position for stop in self.remaining_stops))
        return next((target for target in targets
                     if math.dist(origin, target) <= INTERACTION_RANGE
                     and not any(wall_blocks(origin, target, wall) for wall in self.walls)), None)

    def can_interact(self):
        return self.interaction_target is not None

    def can_open_gate(self):
        if self.gate is None or self.result != "playing" or self.player_hp <= 0:
            return False
        origin = (self.player.x, self.player.y)
        return (math.dist(origin, self.gate_position) <= INTERACTION_RANGE
                and not any(wall_blocks(origin, self.gate_position, wall)
                            for wall in self.walls if wall is not self.gate))

    def _available_interaction(self):
        target = self.interaction_target
        if target is not None:
            return ("pickup" if self.parcel == "waiting" else "deliver", target)
        if self.can_open_gate():
            return "gate", self.gate_position
        return None

    def _clear_interaction(self):
        self._held_interaction = None
        self._interaction_elapsed = 0.0

    @property
    def interaction_action(self):
        return None if self._held_interaction is None else self._held_interaction[0]

    @property
    def interaction_progress(self):
        action = self.interaction_action
        return 0.0 if action is None else self._interaction_elapsed / _INTERACTION_HOLD_TIMES[action]

    def update_interaction(self, dt, *, held, pressed, moving, damaged) -> bool:
        if not held or moving or damaged:
            self._clear_interaction()
            return False
        if not pressed and self._held_interaction is None:
            return False

        interaction = self._available_interaction()
        if pressed:
            self._held_interaction = interaction
            self._interaction_elapsed = 0.0
        if interaction is None or interaction != self._held_interaction:
            self._clear_interaction()
            return False

        if math.isfinite(dt) and dt > 0:
            self._interaction_elapsed += dt
        if self._interaction_elapsed < _INTERACTION_HOLD_TIMES[interaction[0]] - 1e-9:
            return False
        self._clear_interaction()
        return self.interact()

    def interact(self):
        self._resolve_result()
        interaction = self._available_interaction()
        if interaction is None:
            return False
        action, target = interaction
        if action == "gate":
            self.walls.remove(self.gate)
            self.gate = None
            self._emit_noise(GATE_NOISE_RANGE, target)
            return True
        if action == "pickup":
            self.parcel = "carrying"
            return True
        self.completed_stops.add(next(stop for stop in self.remaining_stops if stop.position == target))
        if not self.remaining_stops:
            self.parcel = "delivered"
            self.result = "delivered"
            self.attack = None
            self._resolve_result()
            if self.contract in _SINGLE_CONTRACTS and not self.two_stop_unlocked:
                self.two_stop_unlocked = True
                self.just_unlocked_two_stop = True
        return True
