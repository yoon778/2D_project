"""Dead Route R1-A: one fixed pose, ground aiming and depth ordering."""
from __future__ import annotations

import argparse
import ctypes
from pathlib import Path
import time

import pico2d.pico2d as p

from core import Player, Wall, WORLD_WIDTH, WORLD_HEIGHT, move_player, aim_player
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


def sorted_drawables(player, walls):
    # Stable ties: wall before player, so the player is drawn last at equal y.
    objects = [("wall", wall) for wall in walls] + [("player", player)]
    return sorted(objects, key=lambda item: -item[1].y)


def rectangle(x, y, width, height, color, filled=True):
    p.draw_rectangle(x, y, x + width, y + height, *color, filled=filled)


def cross(x, y, color, size=5):
    p.draw_line(x - size, y, x + size, y, *color)
    p.draw_line(x, y - size, x, y + size, *color)


class Renderer:
    def __init__(self):
        self.font = None
        self.player_visual = None
        try:
            font_path = Path(p.__file__).parent / "data/ConsolaMalgun.ttf"
            self.font = p.load_font(str(font_path), 18)
            self.player_visual = PlayerVisual()
        except Exception:
            self.close()
            raise

    def close(self):
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
        for kind, actor in sorted_drawables(player, walls):
            if kind == "wall":
                self.wall(actor)
            else:
                self.player_visual.draw(*foot)
                cross(*foot, TEAL, size=4)
        # Development markers are separate from the fixed-pose sprite.
        target_screen = world_to_screen(*target)
        p.draw_line(*foot, *target_screen, 112, 93, 56)
        cross(*target_screen, ORANGE, size=7)
        self.font.draw(24, 683, "Dead Route - R1-A  |  한 방향 샘플 고정 · 조준 표식만 변화", WHITE)
        self.font.draw(24, 651, "WASD 이동 · 마우스 지면 조준 · 발점 청록 / 조준 주황 · Esc 종료", WHITE)
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
        p.SDL_SetWindowTitle(p.window, b"Dead Route - R1-A")
        p.SDL_SetWindowPosition(p.window, p.SDL_WINDOWPOS_CENTERED, p.SDL_WINDOWPOS_CENTERED)
        p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
        renderer = Renderer()
        player = Player()
        walls = [Wall(400, 330, 220, 60)]
        pressed = set()
        target = (660.0, 360.0)
        previous = time.perf_counter()
        frame = 0
        running = True
        smoke_poses = (("initial", 480, 180), ("wall-behind", 480, 420),
                       ("wall-front", 480, 300))
        while running:
            now = time.perf_counter()
            dt = min(now - previous, 0.05)
            previous = now
            for event in poll_events():
                if event.type == p.SDL_QUIT:
                    running = False
                elif event.type == p.SDL_KEYDOWN and not event.key.repeat:
                    key = event.key.keysym.sym
                    pressed.add(key)
                    if key == p.SDLK_ESCAPE:
                        running = False
                elif event.type == p.SDL_KEYUP and not event.key.repeat:
                    pressed.discard(event.key.keysym.sym)
                elif event.type == p.SDL_MOUSEMOTION:
                    target = sdl_to_world(event.motion.x, event.motion.y)
                elif (event.type == p.SDL_WINDOWEVENT
                      and event.window.event == p.SDL_WINDOWEVENT_FOCUS_LOST):
                    pressed.clear()
            if not running:
                break
            focused = bool(p.SDL_GetWindowFlags(p.window) & p.SDL_WINDOW_INPUT_FOCUS)
            if not focused:
                pressed.clear()
            axis_x = int(p.SDLK_d in pressed) - int(p.SDLK_a in pressed)
            axis_y = int(p.SDLK_w in pressed) - int(p.SDLK_s in pressed)
            move_player(player, axis_x, axis_y, dt if focused else 0.0, walls)
            if smoke_test:
                name, player.x, player.y = smoke_poses[frame]
            aim_player(player, *target)
            renderer.draw(player, walls, target, focused)
            if smoke_test:
                output = BASE_DIR.parent / "output/review/R1-A" / f"ui-{name}.png"
                capture(output)
                print(f"R1-A SDL capture: {output}", flush=True)
            p.update_canvas()
            frame += 1
            if smoke_test and frame >= len(smoke_poses):
                running = False
    finally:
        if renderer is not None:
            renderer.close()
        p.close_canvas()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dead Route R1-A fixed-pose ground sample")
    parser.add_argument("--smoke-test", action="store_true",
                        help="render three native SDL fixtures, save PNGs and exit")
    run(parser.parse_args().smoke_test)
