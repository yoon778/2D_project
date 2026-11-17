"""Delivery contracts across the town and its connected alleys."""
from dataclasses import dataclass, replace
import json
import math
from pathlib import Path

if __package__:
    from .combat import ATTACK_RANGE, HEAVY_ZOMBIE_APPEARANCE, HEAVY_ZOMBIE_HP, ZOMBIE_APPEARANCES, CombatWorld, Zombie
    from .core import PLAYER_RADIUS, Player, Wall, wall_blocks, wall_entry
    from .delivery_layouts import REPAIR_YARD, WAREHOUSE, DeliveryLayout, NeighborhoodWall
    from .zombie_navigation import can_walk_direct
else:
    from combat import ATTACK_RANGE, HEAVY_ZOMBIE_APPEARANCE, HEAVY_ZOMBIE_HP, ZOMBIE_APPEARANCES, CombatWorld, Zombie
    from core import PLAYER_RADIUS, Player, Wall, wall_blocks, wall_entry
    from delivery_layouts import REPAIR_YARD, WAREHOUSE, DeliveryLayout, NeighborhoodWall
    from zombie_navigation import can_walk_direct


TOWN_SIZE = (3600, 2400)
TOWN_ROADS = json.loads((Path(__file__).resolve().parent / "assets/neighborhood/roads.json")
                        .read_text(encoding="utf-8"))
PLAYER_START = (145.0, 145.0)
TOWN_PICKUP = (172.0, 155.0)
ZOMBIE_START = (675.0, 345.0)
INTERACTION_RANGE = 42.0
MAX_WAYPOINTS = 8
_WAYPOINT_REACH = 32.0
_INTERACTION_HOLD_TIMES = {
    "pickup": 0.50, "deliver": 1.00, "gate": 0.70, "shutter": 0.70,
    "bridge_key": 0.50, "bridge_panel": 0.70, "board_truck": 0.70,
    "bus_broadcast": 0.70, "front_gate": 0.70,
}
TRUCK_ARRIVAL_SECONDS = 1.20
TRUCK_PARKING_SECONDS = 0.30
TRUCK_DISEMBARK_SECONDS = 0.50
TRUCK_BOARDING_SECONDS = 0.50
TRUCK_DEPARTURE_SECONDS = 1.50
_TRUCK_SEQUENCE = {
    "arriving": (TRUCK_ARRIVAL_SECONDS, "parking"),
    "parking": (TRUCK_PARKING_SECONDS, "disembarking"),
    "disembarking": (TRUCK_DISEMBARK_SECONDS, None),
    "boarding": (TRUCK_BOARDING_SECONDS, "departing"),
    "departing": (TRUCK_DEPARTURE_SECONDS, None),
}
_TRUCK_EXIT_THREAT_RANGE = 100.0
_TRUCK_TRAVEL = 720.0
_TRUCK_SIZE = (96, 34)
GATE_NOISE_RANGE = 230.0
FRONT_GATE_NOISE_RANGE = 120.0
BUS_BROADCAST_NOISE_RANGE = 310.0
BUS_BROADCAST_COOLDOWN = 12.0
_SHUTTER_NOISE_RANGE = 95.0
BRIDGE_MOTOR_NOISE_RANGE = 280.0
VEHICLE_ALARM_RANGE = 520.0
_VEHICLE_TEXTURES = ("parked-car", "abandoned-car")
BOTTLE_THROW_RANGE = 320.0
BOTTLE_NOISE_RANGE = 320.0
BOTTLE_FLIGHT_TIME = 0.30
_BOTTLE_STARTS = ((177, 127), (610, 628), (1660, 932), (3230, 2070))
REAR_ALLEY_LISTEN_POINT = (3230, 2170)
_REAR_ALLEY_PATROL = ((3180, 2227), (3060, 2227))
_REAR_ALLEY_ZOMBIES = ((2865, 2227), _REAR_ALLEY_PATROL[0])
_TOWN_APPROACH_ZOMBIES = (ZOMBIE_START, (485, 475), (120, 565), (1020, 190), (1180, 335), (955, 960))
_SHOP_ZOMBIE_STARTS = ((1865, 975), (1930, 950), (1978, 942), (2030, 973), (2005, 1015))
_ROUND_TRIP_SHOP_STARTS = (*_SHOP_ZOMBIE_STARTS[:2], (2038, 938), *_SHOP_ZOMBIE_STARTS[3:])
_ROUND_TRIP_SHOP_HEADINGS = {
    (1865, 975): -3 * math.pi / 4,
    (1930, 950): math.pi,
    (2038, 938): math.radians(75),
}
# The longer northern approach staggers the arrivals after a swing.
_SHOP_SIDE_PATROLS = {
    (2130, 1200): ((2130, 1200), (2160, 1200)),
    (1995, 1250): ((1995, 1250), (2035, 1250)),
}
_FRONT_HOME_ZOMBIE_START = (2898, 1984)
_BUS_EAST_ZOMBIE_START = (2390, 1850)
_BUS_ZOMBIE_STARTS = ((2338, 1865), _BUS_EAST_ZOMBIE_START)
_BUS_SWITCH_POSITION = (2290, 1750)
_BUS_SPEAKER_POSITION = (2125, 1810)
_REAR_GATE_POSITION = (3165, 2196)
_FRONT_GATE_POSITION = (3067, 1925)
_PARKING_ZOMBIE_STARTS = (
    (2083, 1422), (2102, 1418), (2119, 1414), (2142, 1407),
    (2094, 1406), (2116, 1393), (2134, 1382), (2144, 1369),
)
_PARKING_HEAVY_ZOMBIE_START = (2056, 1430)
_PARKING_SHUTTER_POSITION = (2142, 1255)
_PARKING_LURE_POSITION = (2355, 1380)
_PARKING_BOTTLE_POSITION = (2110, 1230)
_BRIDGE_SOUTHEAST_ZOMBIE_START = (2898, 1274)
_SHOP_TRUCK_POSITION = (2290.0, 873.0)
_SHOP_TRUCK_DOOR = (2290.0, 907.0)
_DISTRICT_TRUCK_POSITION = (960.0, 110.0)
_DISTRICT_TRUCK_DOOR = (960.0, 144.0)
_DISTRICT_PLAYER_START = (985.0, 144.0)


@dataclass(frozen=True)
class DeliveryStop:
    name: str
    position: tuple[float, float]

SHOP_STOP = DeliveryStop("상점 앞", (1958.0, 1037.0))
FRONT_HOME_STOP = DeliveryStop("주택 앞문", (3090.0, 1969.0))
REAR_HOME_STOP = DeliveryStop("주택 뒷문", (3149.0, 2227.0))
BUS_STOP = DeliveryStop("정류장", (2290.0, 1860.0))
MANAGEMENT_STOP = DeliveryStop("관리실 뒤편", (2545.0, 1422.0))
REPAIR_DESK_STOP = DeliveryStop("정비 접수대", (1180.0, 751.0))
PARTS_DEPOT_STOP = DeliveryStop("부품 보관소", (1532.0, 1020.0))
SHIPPING_OFFICE_STOP = DeliveryStop("출고 사무실", (790.0, 860.0))
COLD_STORAGE_STOP = DeliveryStop("냉장 창고", (1220.0, 938.0))


@dataclass(frozen=True)
class DeliveryContract:
    name: str
    description: str
    difficulty: str
    destination: tuple[float, float]
    zombie_starts: tuple[tuple[float, float], ...]
    stops: tuple[DeliveryStop, ...] = ()
    player_start: tuple[float, float] = PLAYER_START
    pickup: tuple[float, float] = TOWN_PICKUP
    return_point: tuple[float, float] | None = None
    truck_position: tuple[float, float] | None = None
    number: int | None = None
    layout: DeliveryLayout | None = None
    preview_file: str | None = None

    def __post_init__(self):
        if not self.stops:
            object.__setattr__(self, "stops", (DeliveryStop(self.name, self.destination),))

    @property
    def truck_door_position(self):
        return self.return_point if self.truck_position is not None else None

    @property
    def truck_driver_exit(self):
        if self.truck_position is not None:
            x, y = self.truck_position
            return (x - 27, y + 32)
        return None

    @property
    def truck_driver_socket(self):
        if self.truck_position is not None:
            x, y = self.truck_position
            return (x - 27, y + 6)
        return None


_STARTER_CONTRACTS = (
    DeliveryContract(
        "상점·정류장", "상점 앞과 정류장에 배달", "보통",
        SHOP_STOP.position, (*_TOWN_APPROACH_ZOMBIES, *_SHOP_ZOMBIE_STARTS, *_BUS_ZOMBIE_STARTS),
        (SHOP_STOP, BUS_STOP),
    ),
    DeliveryContract(
        "주택가 배달", "주택 앞문과 뒷문에 배달", "어려움",
        FRONT_HOME_STOP.position,
        (*_TOWN_APPROACH_ZOMBIES, (3255, 525), _FRONT_HOME_ZOMBIE_START, *_REAR_ALLEY_ZOMBIES),
        (FRONT_HOME_STOP, REAR_HOME_STOP),
    ),
)
SHOP_ROUND_TRIP = DeliveryContract(
    "상점 왕복", "상점 앞과 관리실 뒤편, 정류장에 배달하고 트럭 복귀", "보통",
    SHOP_STOP.position,
    (*_ROUND_TRIP_SHOP_STARTS, (2020, 1335), (2370, 1465), _BRIDGE_SOUTHEAST_ZOMBIE_START, *_BUS_ZOMBIE_STARTS),
    (SHOP_STOP, MANAGEMENT_STOP, BUS_STOP),
    player_start=(2315.0, 907.0), pickup=_SHOP_TRUCK_DOOR, return_point=_SHOP_TRUCK_DOOR,
    truck_position=_SHOP_TRUCK_POSITION, number=4, preview_file="04-bridge.png",
)
DELIVERY_CONTRACTS = (
    *_STARTER_CONTRACTS,
    DeliveryContract(
        "세 곳 배달", "상점 앞과 주택 뒷문, 정류장에 배달", "어려움",
        SHOP_STOP.position,
        (*_TOWN_APPROACH_ZOMBIES, *_SHOP_ZOMBIE_STARTS, *_REAR_ALLEY_ZOMBIES, *_BUS_ZOMBIE_STARTS),
        (SHOP_STOP, REAR_HOME_STOP, BUS_STOP),
    ),
    SHOP_ROUND_TRIP,
)
REPAIR_ROUND_TRIP = DeliveryContract(
    "정비창 왕복", "철문 지름길이나 서쪽 우회로를 골라 두 곳 배달하고 트럭 복귀", "보통",
    REPAIR_DESK_STOP.position,
    ((820, 520), (865, 570), (1390, 1090), (1590, 1158), (80, 700), (1245, 310)),
    (REPAIR_DESK_STOP, PARTS_DEPOT_STOP),
    player_start=_DISTRICT_PLAYER_START, pickup=_DISTRICT_TRUCK_DOOR, return_point=_DISTRICT_TRUCK_DOOR,
    truck_position=_DISTRICT_TRUCK_POSITION, number=1, layout=REPAIR_YARD, preview_file="01-repair-yard.png",
)
WAREHOUSE_ROUND_TRIP = DeliveryContract(
    "물류창고 왕복", "방송으로 좀비를 유인하거나 조용히 우회해 두 곳 배달하고 트럭 복귀", "어려움",
    SHIPPING_OFFICE_STOP.position,
    ((870, 650), (907, 692), (1260, 620), (1085, 975), (1590, 823), (174, 725)),
    (SHIPPING_OFFICE_STOP, COLD_STORAGE_STOP),
    player_start=_DISTRICT_PLAYER_START, pickup=_DISTRICT_TRUCK_DOOR, return_point=_DISTRICT_TRUCK_DOOR,
    truck_position=_DISTRICT_TRUCK_POSITION, number=2, layout=WAREHOUSE, preview_file="02-warehouse.png",
)
PLAYABLE_CONTRACTS = {contract.number: contract
                      for contract in (REPAIR_ROUND_TRIP, WAREHOUSE_ROUND_TRIP, SHOP_ROUND_TRIP)}


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


TOWN_BASE_WALLS = (
    NeighborhoodWall(88, 305, 140, 190, "west-house", oblique=True),
    NeighborhoodWall(310, 225, 275, 200, "east-house", oblique=True),
    NeighborhoodWall(345, 164, 100, 12, "fence", height=38),
    # Leave a 72px alley between the rear house wall and the fence.
    *(NeighborhoodWall(x, 2272, 110, 12, "fence", height=38) for x in (2848, 2958, 3068)),
    NeighborhoodWall(3178, 2272, 72, 12, "fence", height=38),
    NeighborhoodWall(3125, 2190, 15, 12, "fence", height=38),
    NeighborhoodWall(3190, 2190, 20, 12, "fence", height=38),
    # The service alley bends around this shed and reconnects west of the fence.
    NeighborhoodWall(3306, 2273, 50, 57, "workshop", height=72),
    NeighborhoodWall(370, 99, 112, 44, "parked-car", height=36),
    NeighborhoodWall(2380, 101, 112, 44, "abandoned-car", height=36),
    NeighborhoodWall(2140, 1019, 112, 44, "abandoned-car", height=36),
    NeighborhoodWall(1692, 970, 88, 44, "abandoned-car", height=36),
    # The wrecks cut across the eastern road. The house side has a narrow bypass.
    NeighborhoodWall(3332, 730, 112, 44, "abandoned-car", height=36),
    NeighborhoodWall(3468, 752, 112, 44, "abandoned-car", height=36),
    NeighborhoodWall(578, 458, 60, 34, "dumpster", height=28),
    NeighborhoodWall(1768, 1008, 60, 34, "dumpster", height=28),
    NeighborhoodWall(2668, 1775, 60, 34, "dumpster", height=28),
    *(NeighborhoodWall(*building, "workshop") for building in _BUILDINGS),
    *(NeighborhoodWall(x, y, 140, 190, "west-house", oblique=True) for x, y in _WEST_HOUSES),
    *(NeighborhoodWall(x, y, 275, 200, "east-house", oblique=True) for x, y in _EAST_HOUSES),
    NeighborhoodWall(1820, 1060, 260, 160, "shop"),
    NeighborhoodWall(2210, 1780, 140, 52, "bus-stop", height=68),
)


class BridgePuzzle:
    key_position = (2608, 1190)
    panel_position = (2545, 1302)
    note_position = (2588, 1264)
    bridge_rect = (2510, 1342, 70, 38)
    channel_rect = (2480, 1342, 240, 38)
    bridge_position = (2545, 1361)
    # Power enters the bottom-left tile, then turns north and leaves to the east.
    _base_ports = (((-1, 0), (0, 1)), ((0, -1), (1, 0)), ((-1, 0), (1, 0)))

    def __init__(self):
        self.has_key = False
        self.panel_open = False
        self.bridge_down = False
        self.rotations = [2, 1, 3]
        self.bridge_wall = NeighborhoodWall(*self.bridge_rect, "bridge-raised", height=36)
        self.station_walls = (
            NeighborhoodWall(2630, 1170, 44, 40, "workshop", height=48),
            NeighborhoodWall(2492, 1273, 28, 48, "workshop", height=48),
        )

    @property
    def ports(self):
        result = []
        for ports, rotation in zip(self._base_ports, self.rotations):
            for _ in range(rotation):
                ports = tuple((y, -x) for x, y in ports)
            result.append(ports)
        return tuple(result)

    @property
    def powered(self):
        first, second, third = self.ports
        first_powered = (-1, 0) in first
        second_powered = first_powered and (0, 1) in first and (0, -1) in second
        third_powered = second_powered and (1, 0) in second and (-1, 0) in third
        return first_powered, second_powered, third_powered


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
    vehicle: NeighborhoodWall | None = None

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
    def pickup(self):
        return self.contract.pickup

    @property
    def roads(self):
        layout = self.contract.layout
        return layout.roads if layout is not None else TOWN_ROADS

    @property
    def mission_phase(self):
        if self.result == "defeated":
            return "failed"
        if self.result == "delivered":
            return "finished"
        if self._route_sequence is not None:
            return self._route_sequence
        return {"waiting": "unloading", "carrying": "delivering", "delivered": "returning"}[self.parcel]

    @property
    def route_sequence_active(self):
        return self._route_sequence is not None and self.result == "playing"

    @property
    def route_sequence_duration(self):
        return _TRUCK_SEQUENCE[self._route_sequence][0] if self.route_sequence_active else 0.0

    @property
    def truck_footprint(self):
        truck = self.truck_wall
        if truck is None:
            return None
        offset = 0.0
        if self.mission_phase == "arriving":
            progress = self.phase_elapsed / TRUCK_ARRIVAL_SECONDS
            offset = _TRUCK_TRAVEL * (1 - progress) ** 2
        elif self.mission_phase == "departing":
            progress = self.phase_elapsed / TRUCK_DEPARTURE_SECONDS
            offset = -_TRUCK_TRAVEL * progress ** 2
        elif truck not in self.walls:
            return None
        return (truck.x + offset, truck.y, truck.width, truck.depth)

    def advance_route_sequence(self, dt):
        if not self.route_sequence_active or not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
            return False
        self._resolve_result()
        transitioned = False
        while self.route_sequence_active:
            remaining = self.route_sequence_duration - self.phase_elapsed
            if dt < remaining - 1e-9:
                self.phase_elapsed += dt
                break
            dt = max(0.0, dt - remaining)
            self._advance_route_phase()
            transitioned = True
        return transitioned

    def skip_route_sequence(self):
        self._resolve_result()
        if not self.route_sequence_active:
            return False
        while self.route_sequence_active:
            self._advance_route_phase()
        return True

    def _advance_route_phase(self):
        phase = self._route_sequence
        _, self._route_sequence = _TRUCK_SEQUENCE[phase]
        self.phase_elapsed = 0.0
        if phase == "arriving":
            self.walls.append(self.truck_wall)
            self._clear_zombie_routes()
        elif phase == "disembarking":
            self.player.x, self.player.y = self.contract.player_start
        elif phase == "boarding":
            self.walls.remove(self.truck_wall)
            self._clear_zombie_routes()
        elif phase == "departing":
            self._finish_delivery()

    @property
    def returning(self):
        return self.contract.truck_door_position is not None and self.mission_phase == "returning"

    @property
    def return_blocked(self):
        if not self.returning:
            return False
        door = self.contract.truck_door_position
        return any(zombie.alive and zombie.state == "chase"
                   and math.dist((zombie.x, zombie.y), door) <= _TRUCK_EXIT_THREAT_RANGE
                   and self._player_line_clear(zombie) for zombie in self.zombies)

    @property
    def route_gimmicks_active(self):
        return self.bridge_puzzle is not None and self.district_gimmicks_active

    @property
    def district_gimmicks_active(self):
        return self.mission_phase in ("delivering", "returning")

    @property
    def available_contracts(self):
        return DELIVERY_CONTRACTS if self.two_stop_unlocked else (*_STARTER_CONTRACTS, DELIVERY_CONTRACTS[3])

    def select_contract(self, index):
        if not 0 <= index < len(DELIVERY_CONTRACTS):
            return False
        contract = DELIVERY_CONTRACTS[index]
        if contract not in self.available_contracts:
            return False
        self.contract = contract
        self.reset()
        return True

    def select_playable_contract(self, number):
        contract = PLAYABLE_CONTRACTS.get(number)
        if contract is None:
            return False
        self.contract = contract
        self.reset()
        return True

    def reset(self):
        super().reset()
        layout = self.contract.layout
        self.world_size = TOWN_SIZE if layout is None else layout.world_size
        self.props = type(self).props if layout is None else ()
        self._starting_player_hp = self.player_hp
        self.attack_count = 0
        self.elapsed_play_time = 0.0
        self.player = Player(*self.contract.player_start)
        self._route_sequence = "arriving" if self.contract.truck_position is not None else None
        self.phase_elapsed = 0.0
        self.truck_wall = None
        if self.contract.truck_position is not None:
            x, y = self.contract.truck_position
            width, depth = _TRUCK_SIZE
            self.truck_wall = NeighborhoodWall(x - width / 2, y - depth / 2, width, depth,
                                               "delivery-truck", height=48)
        self.zombies = []
        has_rear_door = REAR_HOME_STOP in self.contract.stops
        has_front_door = FRONT_HOME_STOP in self.contract.stops
        has_bus_stop = BUS_STOP in self.contract.stops
        has_parking = SHOP_STOP in self.contract.stops
        has_bridge = MANAGEMENT_STOP in self.contract.stops
        streetlights = type(self).streetlights if layout is None else layout.streetlights
        self.streetlights = (*streetlights, (2290, 1350)) if has_parking else streetlights
        parking_starts = _PARKING_ZOMBIE_STARTS if has_bridge else (
            tuple(_PARKING_ZOMBIE_STARTS[index] for index in (0, 2, 5)) if has_parking else ())
        shop_round_trip = self.contract is SHOP_ROUND_TRIP
        shop_patrols = _SHOP_SIDE_PATROLS if shop_round_trip else {}
        for index, position in enumerate((*self.contract.zombie_starts, *parking_starts, *shop_patrols)):
            patrol = shop_patrols.get(position)
            if has_rear_door and position == _REAR_ALLEY_PATROL[0]:
                patrol = _REAR_ALLEY_PATROL
            aim_angle = Player.aim_angle
            if patrol is not None:
                end_x, end_y = patrol[1]
                aim_angle = math.atan2(end_y - position[1], end_x - position[0])
            if position == _BUS_EAST_ZOMBIE_START:
                aim_angle = math.pi / 2
            elif position == _BRIDGE_SOUTHEAST_ZOMBIE_START:
                aim_angle = -math.pi / 2
            elif shop_round_trip:
                aim_angle = _ROUND_TRIP_SHOP_HEADINGS.get(position, aim_angle)
            self.zombies.append(Zombie(
                *position, aim_angle=aim_angle,
                state="patrol" if patrol else "idle", patrol_points=patrol,
                appearance=ZOMBIE_APPEARANCES[index % len(ZOMBIE_APPEARANCES)],
            ))
        if has_bridge:
            self.zombies.append(Zombie(*_PARKING_HEAVY_ZOMBIE_START, aim_angle=math.pi / 2,
                                       hp=HEAVY_ZOMBIE_HP, appearance=HEAVY_ZOMBIE_APPEARANCE))
        if layout is not None:
            self.gate_position = layout.gate_position
            self.gate = replace(layout.gate) if layout.gate is not None else None
        else:
            self.gate_position = _REAR_GATE_POSITION
            self.gate = NeighborhoodWall(3140, 2190, 50, 12, "iron-gate", height=38) if has_rear_door else None
        self.front_gate_position = _FRONT_GATE_POSITION if has_front_door else None
        self.front_gate = NeighborhoodWall(3040, 1919, 54, 12, "iron-gate", height=38) if has_front_door else None
        self.front_gate_fences = (
            NeighborhoodWall(2960, 1919, 80, 12, "fence", height=38),
            NeighborhoodWall(3094, 1919, 62, 12, "fence", height=38),
        ) if has_front_door else ()
        self.walls = [replace(wall) for wall in (TOWN_BASE_WALLS if layout is None else layout.walls)]
        if self.gate is not None:
            self.walls.append(self.gate)
        if self.front_gate is not None:
            self.walls.extend((*self.front_gate_fences, self.front_gate))
        self.shutter_position = _PARKING_SHUTTER_POSITION if has_parking else None
        self.shutter_lure = _PARKING_LURE_POSITION if has_parking else None
        self.shutter_wall = None
        self.shutter_closed = False
        self.parking_walls = ()
        self.bridge_puzzle = BridgePuzzle() if has_bridge else None
        if has_parking:
            # The west shutter is the lot's only opening. Its control is outside.
            self.shutter_wall = NeighborhoodWall(2160, 1262, 12, 162, "parking-shutter", height=66)
            self.parking_walls = (
                NeighborhoodWall(2160, 1250, 320, 12, "fence", height=38),
                NeighborhoodWall(2468, 1262, 12, 162, "fence", height=38),
                NeighborhoodWall(2160, 1424, 320, 12, "fence", height=38),
            )
            self.walls.extend(self.parking_walls)
        if has_bridge:
            puzzle = self.bridge_puzzle
            x, y, width, depth = puzzle.channel_rect
            bridge_x, _, bridge_width, _ = puzzle.bridge_rect
            bridge_end = bridge_x + bridge_width
            self.walls.extend((
                *puzzle.station_walls,
                NeighborhoodWall(x, y, bridge_x - x, depth, "bridge-channel", height=0),
                puzzle.bridge_wall,
                NeighborhoodWall(bridge_end, y, x + width - bridge_end, depth, "bridge-channel", height=0),
            ))
        self.parcel = "waiting"
        self._clear_interaction()
        self.waypoints: list[tuple[float, float]] = []
        self.first_waypoint_number = 1
        self.completed_stops: set[DeliveryStop] = set()
        self.just_unlocked_two_stop = False
        self.bottle_pickups = list(_BOTTLE_STARTS if layout is None else layout.bottle_pickups)
        if layout is None and self.contract.return_point is not None:
            self.bottle_pickups.append((2276, 902))
        if has_parking:
            self.bottle_pickups.append(_PARKING_BOTTLE_POSITION)
            if not has_bridge:
                self.bottle_pickups.append((1840, 875))
        self.has_bottle = False
        self.bottle_flight = None
        self.bottle_impact = None
        self.vehicle_alarm = None
        self.vehicle_alarm_source = None
        self.vehicle_hit = None
        self._triggered_vehicle_alarms = set()
        self.bus_switch_position = (_BUS_SWITCH_POSITION if has_bus_stop else None) if layout is None else layout.bus_switch
        self.bus_speaker_position = (_BUS_SPEAKER_POSITION if has_bus_stop else None) if layout is None else layout.bus_speaker
        self.bus_broadcast_cooldown = 0.0
        self.bus_broadcast_source = None

    @property
    def next_stop(self):
        if self.parcel == "waiting":
            return self.pickup
        if self.returning:
            return self.contract.return_point
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
        if not self.waypoints:
            self.first_waypoint_number = 1
        return True

    def skip_waypoint(self) -> bool:
        if not self.waypoints or self.result != "playing" or self.player_hp <= 0:
            return False
        self.waypoints.pop(0)
        self.first_waypoint_number = self.first_waypoint_number + 1 if self.waypoints else 1
        return True

    def advance_waypoint(self) -> bool:
        if not self.waypoints or self.result != "playing" or self.player_hp <= 0:
            return False
        origin = (self.player.x, self.player.y)
        target = self.waypoints[0]
        if math.dist(origin, target) > _WAYPOINT_REACH or any(
                wall_blocks(origin, target, wall) for wall in self.walls):
            return False
        return self.skip_waypoint()

    @property
    def combat_free(self):
        return self.attack_count == 0 and self.player_hp == self._starting_player_hp

    def start_attack(self, facing="front_right", *, stationary_front_right=False, stationary_swing=False):
        if self.route_sequence_active:
            return False
        started = super().start_attack(
            facing, stationary_front_right=stationary_front_right, stationary_swing=stationary_swing,
        )
        if started:
            self.attack_count += 1
        return started

    @property
    def nearby_bottle(self):
        if self.has_bottle or self.result != "playing" or self.player_hp <= 0 or self.route_sequence_active:
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
        preview = self.bottle_throw_preview(target)
        if preview is None:
            return False
        destination, vehicle = preview
        self.bottle_flight = BottleFlight((self.player.x, self.player.y), destination, vehicle=vehicle)
        self.has_bottle = False
        return True

    def can_throw_bottle(self, target):
        return self._bottle_destination(target) is not None

    def _bottle_destination(self, target):
        preview = self.bottle_throw_preview(target)
        return preview[0] if preview is not None else None

    def bottle_throw_hint(self, target, *, light=None):
        preview = self.bottle_throw_preview(target)
        if preview is None:
            return None
        landing, vehicle = preview
        if light is None or light.contains(landing):
            if vehicle is not None:
                return "차량 경보 유인"
            if (self.district_gimmicks_active and self.shutter_lure is not None and not self.shutter_closed
                    and math.dist(landing, self.shutter_lure) <= 18):
                return "주차장 안쪽으로 유인"
        return "병 던지기"

    def bottle_throw_preview(self, target):
        """Return a reachable landing point and the armed vehicle struck, if any."""
        if (not self.has_bottle or self.bottle_flight is not None or self.attack is not None
                or self.result != "playing" or self.player_hp <= 0 or self.route_sequence_active):
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
        vehicle = None
        # Use zombie clearance so a bottle stopped by a wall can still be reached.
        if not can_walk_direct(origin, destination, self.walls):
            first_wall, _ = self._first_wall_hit(origin, destination)
            clear, blocked = 0.0, travel
            for _ in range(20):
                middle = (clear + blocked) / 2
                if can_walk_direct(origin, landing(middle), self.walls):
                    clear = middle
                else:
                    blocked = middle
            # A nearer corner can stop the throw even if the center ray misses it.
            if (self._can_trigger_vehicle_alarm(first_wall)
                    and not can_walk_direct(origin, landing(blocked), (first_wall,))):
                vehicle = first_wall
            travel = clear
            destination = landing(travel)
        return (destination, vehicle) if travel > 1e-9 else None

    def update(self, dt, axis_x=0.0, axis_y=0.0, *, facing_hint=None, sprint=False, sneak=False):
        self.bottle_impact = None
        self.vehicle_alarm = None
        self.vehicle_alarm_source = None
        self.vehicle_hit = None
        self.bus_broadcast_source = None
        super().update(0 if self.route_sequence_active else dt, axis_x, axis_y,
                       facing_hint=facing_hint, sprint=sprint, sneak=sneak)
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

    def _first_wall_hit(self, origin, end):
        closest, entry = None, math.inf
        for wall in self.walls:
            fraction = wall_entry(origin, end, wall)
            if fraction is not None and fraction < entry:
                closest, entry = wall, fraction
        return closest, entry

    def _on_attack_impact(self, angle):
        origin = self.player.x, self.player.y
        dx, dy = ATTACK_RANGE * math.cos(angle), ATTACK_RANGE * math.sin(angle)
        end = origin[0] + dx, origin[1] + dy
        closest, entry = self._first_wall_hit(origin, end)
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
        if self.bus_broadcast_cooldown > 0:
            remaining = self.bus_broadcast_cooldown - dt
            self.bus_broadcast_cooldown = remaining if remaining > 1e-9 else 0.0
        flight = self.bottle_flight
        if flight is None:
            return
        flight.elapsed += dt
        if flight.elapsed >= BOTTLE_FLIGHT_TIME - 1e-9:
            self.bottle_flight = None
            self.bottle_impact = flight.destination
            if self._can_trigger_vehicle_alarm(flight.vehicle):
                self._trigger_vehicle_alarm(flight.vehicle, flight.destination)
            else:
                self._emit_noise(BOTTLE_NOISE_RANGE, flight.destination)

    @property
    def interaction_target(self):
        if self.result != "playing" or self.player_hp <= 0 or self.route_sequence_active:
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
        return ((self.contract.layout is None or self.district_gimmicks_active)
                and self._gate_in_reach(self.gate, self.gate_position))

    def can_open_front_gate(self):
        return self.district_gimmicks_active and self._gate_in_reach(self.front_gate, self.front_gate_position)

    def _gate_in_reach(self, gate, position):
        if gate is None or self.result != "playing" or self.player_hp <= 0 or self.route_sequence_active:
            return False
        origin = (self.player.x, self.player.y)
        return (math.dist(origin, position) <= INTERACTION_RANGE
                and not any(wall_blocks(origin, position, wall) for wall in self.walls if wall is not gate))

    def can_start_bus_broadcast(self):
        if (self.bus_switch_position is None or self.bus_broadcast_cooldown > 0
                or not self.district_gimmicks_active or self.player_hp <= 0):
            return False
        origin = (self.player.x, self.player.y)
        return (math.dist(origin, self.bus_switch_position) <= INTERACTION_RANGE
                and not any(wall_blocks(origin, self.bus_switch_position, wall) for wall in self.walls))

    def can_close_shutter(self):
        if self.shutter_wall is None or self.shutter_closed or not self.district_gimmicks_active or self.player_hp <= 0:
            return False
        origin = (self.player.x, self.player.y)
        if (math.dist(origin, self.shutter_position) > INTERACTION_RANGE
                or any(wall_blocks(origin, self.shutter_position, wall) for wall in self.walls)):
            return False
        blockers = (self.shutter_wall,)
        if not can_walk_direct(origin, origin, blockers):
            return False
        for zombie in self.zombies:
            point = (zombie.x, zombie.y)
            if zombie.alive and not can_walk_direct(point, point, blockers):
                return False
        return True

    def _bridge_interaction_in_reach(self, target):
        origin = (self.player.x, self.player.y)
        return (self.route_gimmicks_active and self.player_hp > 0 and math.dist(origin, target) <= INTERACTION_RANGE
                and not any(wall_blocks(origin, target, wall) for wall in self.walls))

    def can_collect_bridge_key(self):
        puzzle = self.bridge_puzzle
        return (puzzle is not None and not puzzle.has_key
                and self._bridge_interaction_in_reach(puzzle.key_position))

    def can_reach_bridge_panel(self):
        puzzle = self.bridge_puzzle
        return puzzle is not None and self._bridge_interaction_in_reach(puzzle.panel_position)

    def can_read_bridge_note(self):
        puzzle = self.bridge_puzzle
        return (puzzle is not None and self._bridge_interaction_in_reach(puzzle.note_position)
                and self._available_interaction() is None)

    def can_open_bridge_panel(self):
        puzzle = self.bridge_puzzle
        return (puzzle is not None and puzzle.has_key and not puzzle.bridge_down and not puzzle.panel_open
                and self.can_reach_bridge_panel())

    def close_bridge_panel(self):
        if self.bridge_puzzle is not None:
            self.bridge_puzzle.panel_open = False

    def rotate_bridge_tile(self, index):
        puzzle = self.bridge_puzzle
        if puzzle is None or not puzzle.panel_open or not 0 <= index < len(puzzle.rotations):
            return False
        puzzle.rotations[index] = (puzzle.rotations[index] + 1) % 4
        if not puzzle.powered[-1] or (1, 0) not in puzzle.ports[-1]:
            return False
        puzzle.bridge_down = True
        self.close_bridge_panel()
        self.walls.remove(puzzle.bridge_wall)
        self._clear_zombie_routes()
        self._emit_noise(BRIDGE_MOTOR_NOISE_RANGE, puzzle.bridge_position)
        return True

    def _clear_zombie_routes(self):
        for zombie in self.zombies:
            zombie.investigation_route = None
            zombie.patrol_route = None

    def can_board_truck(self):
        if not self.returning or self.player_hp <= 0 or self.truck_wall not in self.walls:
            return False
        origin = (self.player.x, self.player.y)
        door = self.contract.truck_door_position
        return (math.dist(origin, door) <= INTERACTION_RANGE and not self.return_blocked
                and not any(wall_blocks(origin, door, wall) for wall in self.walls))

    def _available_interaction(self):
        target = self.interaction_target
        if target is not None:
            return ("pickup" if self.parcel == "waiting" else "deliver", target)
        if self.can_open_gate():
            return "gate", self.gate_position
        if self.can_open_front_gate():
            return "front_gate", self.front_gate_position
        if self.can_start_bus_broadcast():
            return "bus_broadcast", self.bus_switch_position
        if self.can_close_shutter():
            return "shutter", self.shutter_position
        if self.can_collect_bridge_key():
            return "bridge_key", self.bridge_puzzle.key_position
        if self.can_open_bridge_panel():
            return "bridge_panel", self.bridge_puzzle.panel_position
        if self.can_board_truck():
            return "board_truck", self.contract.truck_door_position
        return None

    def _clear_interaction(self):
        self._held_interaction = None
        self._interaction_elapsed = 0.0

    @property
    def interaction_candidate(self):
        candidate = self._available_interaction()
        return candidate[0] if candidate is not None else None

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
            self._clear_zombie_routes()
            self._emit_noise(GATE_NOISE_RANGE, target)
            return True
        if action == "front_gate":
            self.walls.remove(self.front_gate)
            self.front_gate = None
            self._clear_zombie_routes()
            self._emit_noise(FRONT_GATE_NOISE_RANGE, target)
            return True
        if action == "bus_broadcast":
            self.bus_broadcast_cooldown = BUS_BROADCAST_COOLDOWN
            self.bus_broadcast_source = self.bus_speaker_position
            self._emit_noise(BUS_BROADCAST_NOISE_RANGE, self.bus_broadcast_source)
            return True
        if action == "shutter":
            self.walls.append(self.shutter_wall)
            self.shutter_closed = True
            self._clear_zombie_routes()
            self._emit_noise(_SHUTTER_NOISE_RANGE, target)
            return True
        if action == "bridge_key":
            self.bridge_puzzle.has_key = True
            return True
        if action == "bridge_panel":
            self.bridge_puzzle.panel_open = True
            return True
        if action == "board_truck":
            self._route_sequence = "boarding"
            self.phase_elapsed = 0.0
            self.attack = None
            self.bottle_flight = None
            return True
        if action == "pickup":
            self.parcel = "carrying"
            return True
        self.completed_stops.add(next(stop for stop in self.remaining_stops if stop.position == target))
        if not self.remaining_stops:
            self.parcel = "delivered"
            if self.contract.return_point is None:
                self._finish_delivery()
        return True

    def _finish_delivery(self):
        self.result = "delivered"
        self.attack = None
        self._resolve_result()
        if self.contract in _STARTER_CONTRACTS and not self.two_stop_unlocked:
            self.two_stop_unlocked = True
            self.just_unlocked_two_stop = True
