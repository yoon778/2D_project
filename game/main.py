"""Dead Route R2-Z: courier combat and eight-direction zombie walk/hit sprites."""
from __future__ import annotations

import argparse
import ctypes
from pathlib import Path
import time

import pico2d.pico2d as p

from core import WORLD_WIDTH, WORLD_HEIGHT, aim_player
from combat import CombatWorld
from combat_visual import CombatVisual
from locomotion import Locomotion, select_facing
from player_visual import PlayerVisual

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
GROUND_X = 160.0
GROUND_Y = 90.0
GROUND_SCALE_Y = 0.60
WALL_HEIGHT = 110
BASE_DIR = Path(__file__).resolve().parent
WHITE = (231, 236, 231)
TEAL = (86, 225, 194)
ORANGE = (255, 182, 78)


def world_to_screen(x, y):
    return GROUND_X + x, GROUND_Y + GROUND_SCALE_Y * y


def screen_to_world(x, y):
    return x - GROUND_X, (y - GROUND_Y) / GROUND_SCALE_Y


def sdl_to_world(x, y):
    return screen_to_world(x, WINDOW_HEIGHT - 1 - y)


def sorted_drawables(player, walls, zombie=None):
    # Stable ties: wall before player, so the player is drawn last at equal y.
    objects = [("wall", wall) for wall in walls]
    if zombie is not None:
        objects.append(("zombie", zombie))
    objects.append(("player", player))
    return sorted(objects, key=lambda item: -item[1].y)


def mouse_target(world, visual, mouse_x, mouse_y):
    foot = world_to_screen(world.zombie.x, world.zombie.y)
    if visual.zombie_contains(world.zombie, *foot, mouse_x, WINDOW_HEIGHT - 1 - mouse_y):
        return world.zombie.x, world.zombie.y
    return sdl_to_world(mouse_x, mouse_y)


def rectangle(x, y, width, height, color, filled=True):
    p.draw_rectangle(x, y, x + width, y + height, *color, filled=filled)


def cross(x, y, color, size=5):
    p.draw_line(x - size, y, x + size, y, *color)
    p.draw_line(x, y - size, x, y + size, *color)


class Renderer:
    def __init__(self):
        self.font = None
        self.player_visual = None
        self.combat_visual = None
        self.combat = None
        try:
            font_path = Path(p.__file__).parent / "data/ConsolaMalgun.ttf"
            self.font = p.load_font(str(font_path), 18)
            self.player_visual = PlayerVisual()
            self.combat_visual = CombatVisual()
        except Exception:
            self.close()
            raise

    def close(self):
        if self.combat_visual is not None:
            self.combat_visual.close()
            self.combat_visual = None
        if self.player_visual is not None:
            self.player_visual.close()
            self.player_visual = None
        if self.font is not None:
            if self.font.font:
                p.TTF_CloseFont(self.font.font)
                self.font.font = None
            self.font = None

    def floor(self):
        rectangle(GROUND_X, GROUND_Y, WORLD_WIDTH,
                  WORLD_HEIGHT * GROUND_SCALE_Y, (42, 53, 57))
        for x in range(0, int(WORLD_WIDTH) + 1, 80):
            start, end = world_to_screen(x, 0), world_to_screen(x, WORLD_HEIGHT)
            p.draw_line(*start, *end, 55, 68, 73)
        for y in range(0, int(WORLD_HEIGHT) + 1, 80):
            start, end = world_to_screen(0, y), world_to_screen(WORLD_WIDTH, y)
            p.draw_line(*start, *end, 55, 68, 73)
        rectangle(GROUND_X, GROUND_Y, WORLD_WIDTH,
                  WORLD_HEIGHT * GROUND_SCALE_Y, (106, 126, 133), filled=False)

    def wall(self, wall):
        x, y = world_to_screen(wall.x, wall.y)
        rectangle(x, y, wall.width, WALL_HEIGHT, (69, 84, 94))
        rectangle(x, y + WALL_HEIGHT, wall.width,
                  wall.depth * GROUND_SCALE_Y, (102, 122, 132))
        rectangle(x, y, wall.width, WALL_HEIGHT, (142, 159, 165), filled=False)
        rectangle(x, y + WALL_HEIGHT, wall.width,
                  wall.depth * GROUND_SCALE_Y, (142, 159, 165), filled=False)
        self.font.draw(x + 46, y + 55, "벽 높이 110px", WHITE)

    def draw(self, player, walls, target, focused=True):
        p.SDL_SetRenderDrawColor(p.renderer, 12, 19, 26, 255)
        p.SDL_RenderClear(p.renderer)
        self.floor()
        foot = world_to_screen(player.x, player.y)
        combat = getattr(self, "combat", None)
        for kind, actor in sorted_drawables(player, walls, combat.zombie if combat else None):
            if kind == "wall":
                self.wall(actor)
            elif kind == "zombie":
                self.combat_visual.draw_zombie(actor, *world_to_screen(actor.x, actor.y))
            else:
                if combat is None or not self.combat_visual.draw_attack(
                        combat.attack, *foot, walk_frame_index=self.player_visual.frame_index):
                    self.player_visual.draw(*foot)
                cross(*foot, TEAL, size=4)
        # Development markers are separate from facing/frame selection.
        target_screen = world_to_screen(*target)
        p.draw_line(*foot, *target_screen, 112, 93, 56)
        cross(*target_screen, ORANGE, size=7)
        self.font.draw(24, 683, "Dead Route - R2-Z  |  좀비 1마리 · 도트 8방향 걷기/피격", WHITE)
        self.font.draw(24, 651, "WASD 이동 · 마우스 조준 · 좌클릭 8방향 공격 · R 재시작 · Esc 종료", WHITE)
        if combat is not None:
            self.font.draw(24, 620, f"HP {combat.player_hp}/3   좀비 {combat.zombie.hp}/5", WHITE)
            if combat.result != "playing":
                message = "연습 좀비 처치" if combat.result == "cleared" else "쓰러짐"
                self.font.draw(470, 365, f"{message} · R 재시작", TEAL)
        self.font.draw(24, 54, "입력 활성" if focused else "포커스 없음 · 이동 입력 초기화", WHITE)
        self.font.draw(24, 24,
                       f"발점 ({player.x:.1f}, {player.y:.1f})   "
                       f"조준 지면 ({target[0]:.1f}, {target[1]:.1f})   "
                       f"각도 {player.aim_angle:.3f} rad", WHITE)


def capture(path):
    """Save actual SDL back-buffer pixels before Present."""
    path.parent.mkdir(parents=True, exist_ok=True)
    surface = p.SDL_CreateRGBSurfaceWithFormat(
        0, WINDOW_WIDTH, WINDOW_HEIGHT, 32, p.SDL_PIXELFORMAT_ARGB8888)
    if not surface:
        raise RuntimeError(f"SDL capture allocation failed: {p.SDL_GetError()!r}")
    try:
        if p.SDL_RenderReadPixels(p.renderer, None, p.SDL_PIXELFORMAT_ARGB8888,
                                 surface.contents.pixels, surface.contents.pitch) != 0:
            raise RuntimeError(f"SDL capture failed: {p.SDL_GetError()!r}")
        if p.IMG_SavePNG(surface, str(path).encode("utf-8")) != 0:
            raise RuntimeError(f"PNG save failed: {path}")
    finally:
        p.SDL_FreeSurface(surface)


def poll_events():
    """Read raw events, retaining focus changes without FPS title updates."""
    while True:
        event = p.SDL_Event()
        if not p.SDL_PollEvent(ctypes.byref(event)):
            return
        yield event


def run(smoke_test=False):
    renderer = None
    try:
        p.open_canvas(WINDOW_WIDTH, WINDOW_HEIGHT, sync=True)
        if not p.renderer:
            p.renderer = p.SDL_CreateRenderer(p.window, -1, p.SDL_RENDERER_SOFTWARE)
        if not p.renderer:
            raise RuntimeError(f"SDL renderer initialization failed: {p.SDL_GetError()!r}")
        p.hide_lattice()
        p.SDL_SetWindowTitle(p.window, b"Dead Route - R2-Z")
        p.SDL_SetWindowPosition(p.window, p.SDL_WINDOWPOS_CENTERED, p.SDL_WINDOWPOS_CENTERED)
        p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
        renderer = Renderer()
        world = CombatWorld()
        renderer.combat = world
        player, walls = world.player, world.walls
        pressed = set()
        target = (world.zombie.x, world.zombie.y)
        cursor = None
        mouse_held = False
        previous = time.perf_counter()
        frame = 0
        running = True
        smoke_poses = (("initial", 480, 180), ("wall-behind", 480, 420),
                       ("wall-front", 480, 300))
        while running:
            now = time.perf_counter()
            dt = min(now - previous, 0.05)
            previous = now
            pending_click = None
            reset_requested = False
            lost_focus = False
            for event in poll_events():
                if event.type == p.SDL_QUIT:
                    running = False
                elif event.type == p.SDL_KEYDOWN and not event.key.repeat:
                    key = event.key.keysym.sym
                    pressed.add(key)
                    if key == p.SDLK_ESCAPE:
                        running = False
                    elif key == p.SDLK_r:
                        reset_requested = True
                elif event.type == p.SDL_KEYUP and not event.key.repeat:
                    pressed.discard(event.key.keysym.sym)
                elif event.type == p.SDL_MOUSEMOTION:
                    cursor = (event.motion.x, event.motion.y)
                elif event.type == p.SDL_MOUSEBUTTONDOWN and event.button.button == p.SDL_BUTTON_LEFT:
                    cursor = (event.button.x, event.button.y)
                    if not mouse_held:
                        pending_click = cursor
                    mouse_held = True
                elif event.type == p.SDL_MOUSEBUTTONUP and event.button.button == p.SDL_BUTTON_LEFT:
                    mouse_held = False
                elif (event.type == p.SDL_WINDOWEVENT
                      and event.window.event == p.SDL_WINDOWEVENT_FOCUS_LOST):
                    pressed.clear()
                    pending_click = None
                    mouse_held = False
                    lost_focus = True
            if not running:
                break
            focused = bool(p.SDL_GetWindowFlags(p.window) & p.SDL_WINDOW_INPUT_FOCUS)
            if not focused:
                pressed.clear()
                pending_click = None
                mouse_held = False
            if reset_requested:
                world.reset()
                player, walls = world.player, world.walls
                renderer.player_visual.locomotion = Locomotion()
                renderer.combat_visual.reset_zombie_animation()
                pressed.clear()
                pending_click = None
                mouse_held = False
                cursor = None
                target = (world.zombie.x, world.zombie.y)
            if cursor is not None:
                target = mouse_target(world, renderer.combat_visual, *cursor)
            aim_player(player, *target)
            active = focused and not lost_focus
            if pending_click is not None and active:
                attack_target = mouse_target(world, renderer.combat_visual, *pending_click)
                aim_player(player, *attack_target)
                motion = renderer.player_visual.locomotion
                facing = select_facing(player.aim_angle, motion.facing if motion._initialized else None)
                world.start_attack(facing=facing)
                aim_player(player, *target)
            axis_x = int(p.SDLK_d in pressed) - int(p.SDLK_a in pressed)
            axis_y = int(p.SDLK_w in pressed) - int(p.SDLK_s in pressed)
            before = (player.x, player.y)
            zombie_before = (world.zombie.x, world.zombie.y)
            world.update(dt if active else 0.0, axis_x, axis_y)
            dx, dy = player.x - before[0], player.y - before[1]
            renderer.combat_visual.update_zombie(
                world.zombie, world.zombie.x - zombie_before[0], world.zombie.y - zombie_before[1])
            if smoke_test:
                name, player.x, player.y = smoke_poses[frame]
            aim_player(player, *target)
            display_angle = world.attack.angle if world.attack is not None else player.aim_angle
            renderer.player_visual.update(display_angle, dx, dy)
            renderer.draw(player, walls, target, focused)
            if smoke_test:
                output = BASE_DIR.parent / "output/review/R2-C8" / f"ui-{name}.png"
                capture(output)
                print(f"R2-C8 SDL capture: {output}", flush=True)
            p.update_canvas()
            frame += 1
            if smoke_test and frame >= len(smoke_poses):
                running = False
    finally:
        if renderer is not None:
            renderer.close()
        p.close_canvas()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dead Route R2-C8 eight-direction combat sample")
    parser.add_argument("--smoke-test", action="store_true",
                        help="render three native SDL fixtures, save PNGs and exit")
    run(parser.parse_args().smoke_test)
