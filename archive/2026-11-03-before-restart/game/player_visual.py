"""One top-down courier atlas; all animation remains renderer-owned."""
from __future__ import annotations

import math
from pathlib import Path

import pico2d.pico2d as p


# PNG top-left clip, clip-local top-left pivot, displayed width in world px.
PARTS = {
    "body": ((102, 91, 330, 351), (154, 165), 36.0),
    "arm": ((605, 201, 326, 132), (32, 59), 22.0),
    "foot": ((1136, 193, 294, 153), (147, 76), 12.0),
    "parcel": ((126, 653, 264, 225), (132, 112), 20.0),
    "bat": ((557, 720, 423, 84), (80, 42), 56.0),
}


def point(x, y, angle, forward, left):
    return (x + math.cos(angle) * forward - math.sin(angle) * left,
            y + math.sin(angle) * forward + math.cos(angle) * left)


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


class PlayerVisual:
    def __init__(self, base_dir: Path):
        path = base_dir / "assets" / "player" / "courier-atlas-20261103-v1.png"
        if not path.is_file():
            raise FileNotFoundError(f"Player atlas not found: {path}")
        self.atlas = p.load_image(str(path))
        if (self.atlas.w, self.atlas.h) != (1536, 1024):
            raise ValueError(f"Player atlas must be 1536x1024: {path}")
        self._actor = None
        self._time = 0.0
        self._position = (0.0, 0.0)
        self._phase = 0.0
        self._walking = False

    def close(self):
        # pico2d.Image.__del__ owns its SDL texture.
        self.atlas = None
        self._actor = None

    def _motion(self, game):
        actor = game.player
        position = (actor.x, actor.y)
        if actor is not self._actor or game.time < self._time:
            self._actor = actor
            self._phase = 0.0
            self._walking = False
        elif game.time > self._time:
            distance = math.dist(position, self._position)
            self._walking = game.state == "playing" and distance > 1e-8
            if self._walking:
                stride = 44.0 if actor.state == "run" else 40.0
                self._phase = (self._phase + distance * math.tau / stride) % math.tau
            else:
                self._phase = 0.0
        self._time = game.time
        self._position = position
        return math.sin(self._phase) * 3.0 if self._walking else 0.0

    def _part(self, name, anchor, angle):
        (left, top, width, height), (pivot_x, pivot_y), shown_width = PARTS[name]
        scale = shown_width / width
        center = point(*anchor, angle,
                       (width / 2 - pivot_x) * scale,
                       (pivot_y - height / 2) * scale)
        self.atlas.clip_composite_draw(
            left, self.atlas.h - top - height, width, height,
            angle, "", *center, shown_width, height * scale,
        )

    @staticmethod
    def _swing(game):
        t = game.attack_elapsed
        if t is None:
            return -0.24
        if t < game.attack_hit_time:
            return -1.35 + smooth(t / game.attack_hit_time) * 1.35
        if t < game.attack_hit_time + 0.12:
            return smooth((t - game.attack_hit_time) / 0.12) * 0.85
        recovery = game.attack_duration - game.attack_hit_time - 0.12
        return 0.85 - smooth((t - game.attack_hit_time - 0.12) / recovery) * 1.09

    def draw(self, game):
        actor = game.player
        x, y, angle = actor.x, actor.y, actor.angle
        bob = self._motion(game)
        if actor.hp <= 0:
            p.draw_circle(x, y, 19, 45, 51, 49, filled=False)
            return
        blink = actor.invulnerable > 0 and int(game.time * 14) % 2 == 0
        self.atlas.opacify(0.35 if blink else 1.0)
        try:
            for side in (-1, 1):
                self._part("foot", point(x, y, angle, -16 + side * bob, side * 12), angle)
            # Flinch only the upper body. Never change actor/world coordinates.
            recoil = min(1.0, actor.stun / 0.12)
            origin = point(x, y, angle, -2 * recoil, 0)
            body_angle = angle + recoil * 0.12
            left_shoulder = point(*origin, body_angle, 0, 13)
            left_angle = body_angle - math.atan2(3, 18)
            right_shoulder = point(*origin, body_angle, 2, -14)
            right_angle = body_angle + self._swing(game)
            # Sleeves start inside the torso, so the body covers their root.
            self._part("arm", left_shoulder, left_angle)
            self._part("arm", right_shoulder, right_angle)
            self._part("body", origin, body_angle)
            arm_scale = PARTS["arm"][2] / PARTS["arm"][0][2]
            left_hand = point(*left_shoulder, left_angle, 248 * arm_scale, -4 * arm_scale)
            right_hand = point(*right_shoulder, right_angle, 248 * arm_scale, -4 * arm_scale)
            if game.carrying:
                parcel = point(*left_hand, body_angle, 10, -2)
                self._part("parcel", parcel, body_angle)
            self._part("bat", right_hand, right_angle)
        finally:
            self.atlas.opacify(1.0)
