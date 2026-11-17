"""World-anchored art for the delivery truck and its handoff."""
from dataclasses import dataclass
import math

from locomotion import STRIDE_DISTANCE, select_facing
from player_visual import load_atlas


TRUCK_WIDTH, TRUCK_HEIGHT = 96, 64
_VEHICLE_CELLS = ("closed", "cab", "cargo", "cargo_empty")
_PICKUP_FACINGS = ("left", "right", "front")


@dataclass(frozen=True)
class CourierStep:
    position: tuple[float, float]
    facing: str
    frame: int
    opacity: float


def _mix(start, end, progress):
    return tuple(a + (b - a) * progress for a, b in zip(start, end))


def courier_step(world):
    phase = world.mission_phase
    if phase not in ("disembarking", "boarding"):
        return None
    contract = world.contract
    curb, socket = contract.truck_driver_exit, contract.truck_driver_socket
    to_truck = phase == "boarding"
    pavement = (world.player.x, world.player.y) if to_truck else contract.player_start
    progress = min(1.0, max(0.0, world.phase_elapsed / world.route_sequence_duration))
    # The faster segment is the road walk. The step up/down gets its own pause and concealment.
    split = .61 if to_truck else .39
    points = (pavement, curb, socket) if to_truck else (socket, curb, pavement)
    start, finish = points[:2] if progress < split else points[1:]
    travel = progress / split if progress < split else (progress - split) / (1 - split)
    traveled = math.dist(start, finish) * travel
    if progress >= split:
        traveled += math.dist(*points[:2])
    before = math.atan2(points[1][1] - points[0][1], points[1][0] - points[0][0])
    after = math.atan2(points[2][1] - points[1][1], points[2][0] - points[1][0])
    turn = min(1.0, max(0.0, (progress - split + .1) / .2))
    facing = select_facing(before + math.remainder(after - before, math.tau) * turn)
    frame = int((traveled % STRIDE_DISTANCE) / STRIDE_DISTANCE * 8) + 1
    opacity = min(1.0, (1 - progress) * 4.2 if to_truck else progress * 5.2)
    return CourierStep(_mix(start, finish, travel), facing, frame, opacity)


def pickup_frame(progress):
    return min(3, max(0, int(progress * 4)))


def pickup_facing(origin, door):
    dx, dy = door[0] - origin[0], door[1] - origin[1]
    if abs(dx) < abs(dy) * .55:
        return "front"
    return "left" if dx <= 0 else "right"


def truck_bounds(project, footprint):
    x, y, width, _ = footprint
    left, bottom = project(x, y)
    right, _ = project(x + width, y)
    width = right - left
    return left, bottom - 1, width, TRUCK_HEIGHT * width / TRUCK_WIDTH


class TruckVisual:
    def __init__(self, asset_path):
        self.image = load_atlas(asset_path / "delivery-truck.png", [TRUCK_WIDTH * len(_VEHICLE_CELLS), TRUCK_HEIGHT])
        self.pickup = load_atlas(asset_path / "courier-pickup.png", [320, 240])

    def draw(self, bounds, door):
        cell = _VEHICLE_CELLS.index(door)
        self.image.clip_draw_to_origin(cell * TRUCK_WIDTH, 0, TRUCK_WIDTH, TRUCK_HEIGHT, *bounds)

    def draw_pickup(self, foot, facing, index, scale, *, upper_body=False):
        row = _PICKUP_FACINGS.index(facing)
        x, y = foot
        height = 53 if upper_body else 80
        crop_bottom = 80 - height
        self.pickup.clip_draw_to_origin(index * 80, 160 - row * 80 + crop_bottom, 80, height,
                                        x - 40 * scale, y + (crop_bottom - 8) * scale,
                                        80 * scale, height * scale)
