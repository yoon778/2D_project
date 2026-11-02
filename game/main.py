"""임시 도형으로 이동과 근접 전투를 확인하는 첫 프로토타입."""
from __future__ import annotations

import math
from pathlib import Path
import time

import pico2d.pico2d as p
from core import Game, WIDTH, HEIGHT
from spatial_audio import SpatialAudio
from visibility import flashlight_polygon

BASE_DIR = Path(__file__).resolve().parent
INK = (9, 18, 25)
FLOOR = (14, 28, 37)
GRID = (22, 38, 47)
WHITE = (232, 238, 233)
MUTED = (139, 164, 171)
TEAL = (82, 193, 173)
GOLD = (233, 184, 93)
RED = (230, 116, 99)


def rect(x, y, w, h, color, alpha=255, filled=True):
    p.draw_rectangle(x, y, x + w, y + h, *color, alpha, filled=filled)


def circle(x, y, radius, color, alpha=255, filled=True):
    p.draw_circle(x, y, int(radius), *color, alpha, filled=filled)


def line(a, b, color, width=1, alpha=255):
    for offset in range(-(width // 2), width // 2 + 1):
        p.draw_line(a[0], a[1] + offset, b[0], b[1] + offset, *color, alpha)


def local_point(x, y, angle, forward, left):
    return (
        x + math.cos(angle) * forward - math.sin(angle) * left,
        y + math.sin(angle) * forward + math.cos(angle) * left,
    )


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


class Renderer:
    def __init__(self):
        font_path = Path(p.__file__).parent / "data" / "ConsolaMalgun.ttf"
        self.small = p.load_font(str(font_path), 18)
        self.body = p.load_font(str(font_path), 23)
        self.title = p.load_font(str(font_path), 36)
        self.effects = []
        self.sounds = {}
        self.world_texture = p.SDL_CreateTexture(
            p.renderer, p.SDL_PIXELFORMAT_RGBA8888, p.SDL_TEXTUREACCESS_TARGET,
            WIDTH, HEIGHT,
        )
        if not self.world_texture:
            raise RuntimeError("Flashlight texture initialization failed")
        p.SDL_SetTextureBlendMode(self.world_texture, p.SDL_BLENDMODE_NONE)
        if p.audio_on:
            for kind in ("attack", "hit", "hurt"):
                self.sounds[kind] = p.load_wav(str(BASE_DIR / "assets" / "audio" / (kind + ".wav")))
                self.sounds[kind].set_volume(35)
        self.spatial_audio = SpatialAudio(p, BASE_DIR)

    def consume(self, game, focused=True):
        self.spatial_audio.update(game, focused=focused)
        for event in game.pop_events():
            if event.kind in ("zombie_step", "zombie_groan"):
                if game.zombie.hp > 0:
                    self.spatial_audio.play(event.kind, event.x, event.y,
                                            game.player.x, game.player.y)
                continue
            self.effects.append((event.kind, event.x, event.y, game.time))
            if event.kind in self.sounds:
                self.sounds[event.kind].play()

    def close(self):
        self.spatial_audio.close()
        self.sounds.clear()
        if self.world_texture:
            p.SDL_DestroyTexture(self.world_texture)
            self.world_texture = None
        self.small = self.body = self.title = None

    def actor(self, game, actor, player=False, moving=False):
        x, y, angle = actor.x, actor.y, actor.angle
        if actor.hp <= 0:
            circle(x, y, 19, (45, 51, 49), filled=False)
            return
        bob = math.sin(game.time * (15 if moving else 0)) * 2
        color = TEAL if player else (144, 158, 103)
        recoil = 0.0
        if not player and actor.stun > 0:
            progress = 1 - min(1.0, actor.stun / game.zombie_hit_stun)
            recoil = 1 - smooth(progress)
            if progress < 0.2:
                color = WHITE
        if actor.invulnerable > 0 and int(game.time * 14) % 2 == 0:
            color = WHITE
        circle(x + 2, y - 5, 20, (4, 11, 15))
        for side in (-1, 1):
            foot = local_point(x, y, angle, -10 + side * bob, side * 9)
            circle(*foot, 5, (36, 47, 53))
        # Feet/world position stay fixed; only the upper-body pose flinches.
        angle += recoil * 0.18
        circle(x, y, 16, color)
        head = local_point(x, y, angle, 8 - recoil * 9, recoil * 2)
        circle(*head, 9, (219, 191, 153) if player else (171, 167, 123))
        nose = local_point(x, y, angle, 18 - recoil * 9, recoil * 2)
        circle(*nose, 3, WHITE if player else (94, 102, 76))
        if player:
            # 왼손 택배와 오른손 방망이는 같은 몸 좌표를 기준으로 배치
            left_hand = local_point(x, y, angle, 8, 19)
            line((x, y), left_hand, color, 6)
            if game.carrying:
                rect(left_hand[0] - 10, left_hand[1] - 9, 20, 18, GOLD)
                line((left_hand[0], left_hand[1] - 8), (left_hand[0], left_hand[1] + 8), (173, 127, 62), 2)
            else:
                circle(*left_hand, 5, (219, 191, 153))
            shoulder = local_point(x, y, angle, 2, -15)
            swing_angle = -0.24
            if game.attack_elapsed is not None:
                t = game.attack_elapsed
                if t < game.attack_hit_time:
                    swing_angle = -1.35 + smooth(t / game.attack_hit_time) * 1.35
                elif t < game.attack_hit_time + 0.12:
                    swing_angle = smooth((t - game.attack_hit_time) / 0.12) * 0.85
                else:
                    swing_angle = 0.85 - smooth((t - game.attack_hit_time - 0.12) / (game.attack_duration - game.attack_hit_time - 0.12)) * 1.09
            bat_angle = angle + swing_angle
            hand = (shoulder[0] + math.cos(bat_angle) * 14, shoulder[1] + math.sin(bat_angle) * 14)
            tip = (hand[0] + math.cos(bat_angle) * 45, hand[1] + math.sin(bat_angle) * 45)
            line(shoulder, hand, color, 7)
            circle(*hand, 5, (219, 191, 153))
            line(hand, tip, (164, 117, 63), 6)
            circle(*tip, 4, (205, 156, 92))
            lamp = local_point(x, y, angle, 14, 0)
            circle(*lamp, 3, GOLD)
        else:
            for side in (-1, 1):
                hand = local_point(x, y, angle, 23 - recoil * 12, side * (14 + recoil * 4))
                arm = local_point(x, y, angle, 0, side * 12)
                line(arm, hand, color, 5)
                circle(*hand, 4, (171, 167, 123))
            health_width = actor.max_hp * 10 - 2
            for i in range(actor.max_hp):
                rect(x - health_width / 2 + i * 10, y + 30, 8, 4, RED if i < actor.hp else (55, 63, 55))
            marker = "!" if actor.state == "chase" else "?" if actor.state in ("investigate", "search") else ""
            if marker:
                self.body.draw(x - 6, y + 57, marker, RED if marker == "!" else GOLD)

    def world(self, game):
        rect(0, 0, WIDTH, HEIGHT, FLOOR)
        for x in range(40, WIDTH, 40):
            line((x, 95), (x, 635), GRID)
        for y in range(115, 636, 40):
            line((24, y), (1256, y), GRID)
        for wall in game.walls:
            rect(wall.x + 7, wall.y - 7, wall.w, wall.h, (4, 11, 15))
            rect(wall.x, wall.y, wall.w, wall.h, (33, 50, 61))
            rect(wall.x + 6, wall.y + 6, wall.w - 12, wall.h - 12, (25, 41, 51))
            line((wall.x, wall.y + wall.h), (wall.x + wall.w, wall.y + wall.h), (75, 94, 101), 2)
            self.small.draw(wall.x + 25, wall.y + wall.h - 32, "고정 건물", MUTED)

        for (x, y), label, color in (
            (game.pickup, "수령 거점", TEAL),
            (game.destination, "배달 목적지", GOLD),
        ):
            if not game.is_visible(x, y):
                continue
            circle(x, y, 37, color, filled=False)
            circle(x, y, 32, color, alpha=40)
            rect(x - 11, y - 9, 22, 18, color)
            self.small.draw(x - 40, y + 53, label, color)
        if game.is_visible(game.zombie.x, game.zombie.y):
            self.actor(game, game.zombie, moving=game.zombie.state in ("chase", "investigate"))
        self.effects = [effect for effect in self.effects if game.time - effect[3] < 0.4]
        for kind, x, y, began in self.effects:
            if not game.is_visible(x, y):
                continue
            age = game.time - began
            if kind == "attack":
                circle(x, y, 24 + age * 145, GOLD, alpha=int(150 * (1 - age / 0.4)), filled=False)
            elif kind in ("walk", "run"):
                circle(x, y, 12 + age * (90 if kind == "run" else 40), MUTED,
                       alpha=int(110 * (1 - age / 0.4)), filled=False)
            elif kind in ("hit", "hurt"):
                self.body.draw(x - 10, y + 45 + age * 35, "-1", GOLD if kind == "hit" else RED)

        if game.state == "playing":
            target = game.destination if game.carrying else game.pickup
            if (math.dist((game.player.x, game.player.y), target) <= game.interaction_radius
                    and game.is_visible(*target)):
                self.body.draw(game.player.x - 54, game.player.y + 81,
                               "E  배달" if game.carrying else "E  수령", WHITE)

    def draw(self, game, mouse, moving=False, focused=True):
        # Everything in world space shares one mask, including labels/effects.
        previous_target = p.SDL_GetRenderTarget(p.renderer)
        if p.SDL_SetRenderTarget(p.renderer, self.world_texture) != 0:
            raise RuntimeError("Flashlight render target failed")
        try:
            self.world(game)
        finally:
            p.SDL_SetRenderTarget(p.renderer, previous_target)
        p.SDL_SetRenderDrawColor(p.renderer, 0, 0, 0, 255)
        p.SDL_RenderClear(p.renderer)
        for wall in game.walls:
            rect(wall.x, wall.y, wall.w, wall.h, (18, 25, 29), filled=False)

        boundary = flashlight_polygon(game)
        points = []
        for first, last in zip(boundary, boundary[1:]):
            points.extend(((game.player.x, game.player.y), first, last))
        vertices = (p.SDL_Vertex * len(points))(*(
            p.SDL_Vertex((x, HEIGHT - 1 - y), (255, 255, 255, 255),
                         (x / WIDTH, (HEIGHT - 1 - y) / HEIGHT))
            for x, y in points
        ))
        if p.SDL_RenderGeometry(p.renderer, self.world_texture, vertices, len(vertices), None, 0) != 0:
            raise RuntimeError("Flashlight geometry rendering failed")
        # The player and HUD stay readable; they reveal no hidden world objects.
        self.actor(game, game.player, player=True, moving=moving and game.state == "playing")
        rect(0, 636, WIDTH, 84, INK)
        self.title.draw(28, 684, "그림자 배달", WHITE)
        self.small.draw(30, 651, "소음 유도 · 걷기와 달리기 · 방망이 5타", MUTED)
        self.body.draw(590, 680, "택배 운반 중" if game.carrying else "거점에서 택배 수령", GOLD if game.carrying else TEAL)
        stamina_color = RED if game.exhausted else TEAL
        self.small.draw(788, 651, "스태미나", MUTED)
        rect(880, 644, 140, 12, (49, 56, 61))
        rect(880, 644, 140 * game.stamina / game.stamina_max, 12, stamina_color)
        self.small.draw(1037, 651, "회복 중" if game.exhausted else f"{game.stamina:.0f} / {game.stamina_max:.0f}", stamina_color)
        for i in range(game.player.max_hp):
            circle(1065 + i * 38, 681, 11, RED if i < game.player.hp else (49, 56, 61))
        rect(0, 0, WIDTH, 91, INK)
        self.small.draw(28, 62, "WASD 이동    Shift 달리기    마우스 조준    왼쪽 클릭 공격    E 수령·배달", WHITE)
        self.small.draw(28, 31, "벽 뒤에서도 소음 감지   /   달리기 스태미나 소모   /   Esc 종료", MUTED)
        self.small.draw(1030, 31, "손전등 시야", GOLD)
        # 소형 조준점
        mx, my = mouse
        line((mx - 7, my), (mx + 7, my), WHITE)
        line((mx, my - 7), (mx, my + 7), WHITE)

        if game.state != "playing":
            rect(270, 227, 740, 260, INK, alpha=245)
            title, color = {
                "ready": ("배달을 시작할 준비", WHITE),
                "won": ("택배 배달 완료", GOLD),
                "lost": ("체력이 모두 소진됨", RED),
            }[game.state]
            self.title.draw(330, 431, title, color)
            message = "걷기는 좀비와 같은 속도 · 달리기와 소음에 주의" if game.state == "ready" else "한 판을 다시 시작해 조작과 공격 간격을 확인"
            self.body.draw(332, 370, message, MUTED)
            self.body.draw(332, 307, "Enter  시작" if game.state == "ready" else "R  다시 시작", TEAL)
        elif not focused:
            rect(406, 301, 468, 120, INK, alpha=245)
            self.body.draw(445, 365, "잠시 멈춤", GOLD)
            self.small.draw(445, 332, "게임 창을 선택하면 계속 진행", WHITE)


def run():
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    if not p.renderer:
        p.renderer = p.SDL_CreateRenderer(p.window, -1, p.SDL_RENDERER_SOFTWARE)
    if not p.renderer:
        raise RuntimeError("SDL renderer initialization failed")
    p.hide_lattice()
    p.SDL_SetWindowTitle(p.window, "그림자 배달 - 전투 프로토타입".encode("utf-8"))
    p.SDL_SetWindowPosition(p.window, p.SDL_WINDOWPOS_CENTERED, p.SDL_WINDOWPOS_CENTERED)
    p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
    game = Game()
    renderer = Renderer()
    pressed = set()
    mouse = (game.player.x + 100, game.player.y)
    running = True
    previous = time.perf_counter()
    print("Prototype started; audio initialized:", p.audio_on, flush=True)
    try:
        while running:
            now = time.perf_counter()
            dt = min(now - previous, 0.05)
            previous = now
            interact_requested = False
            for event in p.get_events():
                if event.type == p.SDL_QUIT:
                    running = False
                elif event.type == p.SDL_KEYDOWN:
                    pressed.add(event.key)
                    if event.key == p.SDLK_ESCAPE:
                        running = False
                    elif event.key == p.SDLK_RETURN and game.state == "ready":
                        game.start()
                    elif event.key == p.SDLK_r and game.state in ("won", "lost"):
                        game.restart()
                        renderer.effects.clear()
                    elif event.key == p.SDLK_e:
                        interact_requested = True
                elif event.type == p.SDL_KEYUP:
                    pressed.discard(event.key)
                elif event.type in (p.SDL_MOUSEMOTION, p.SDL_MOUSEBUTTONDOWN):
                    mouse = (event.x, HEIGHT - 1 - event.y)
                    game.player.angle = math.atan2(mouse[1] - game.player.y, mouse[0] - game.player.x)
                    if event.type == p.SDL_MOUSEBUTTONDOWN and event.button == p.SDL_BUTTON_LEFT:
                        game.swing()
            p.SDL_SetWindowTitle(p.window, "그림자 배달 - 전투 프로토타입".encode("utf-8"))
            focused = bool(p.SDL_GetWindowFlags(p.window) & p.SDL_WINDOW_INPUT_FOCUS)
            if not focused:
                pressed.clear()
            move_x = int(p.SDLK_d in pressed) - int(p.SDLK_a in pressed)
            move_y = int(p.SDLK_w in pressed) - int(p.SDLK_s in pressed)
            sprint = p.SDLK_LSHIFT in pressed or p.SDLK_RSHIFT in pressed
            game.step(dt if focused else 0.0, move_x, move_y, sprint, *mouse)
            if interact_requested:
                game.interact()
            renderer.consume(game, focused=focused)
            renderer.draw(game, mouse, moving=bool(move_x or move_y), focused=focused)
            p.update_canvas()
    finally:
        # SDL 텍스처·글꼴은 SDL 종료보다 먼저 해제
        renderer.close()
        p.close_canvas()


if __name__ == "__main__":
    run()
