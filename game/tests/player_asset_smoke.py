r"""Native SDL player fixtures; PNG poses require human review.

Run from the repository root: .venv\Scripts\python.exe game/tests/player_asset_smoke.py
Uses dummy SDL video/audio, not physical input or listening tests.
"""
from contextlib import ExitStack
from copy import deepcopy
import ctypes
from dataclasses import asdict
import gc
import json
import math
import os
from pathlib import Path
import sys
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "tmp" / "player-asset-qa"
sys.path.insert(0, str(ROOT / "game"))
import main as game_main
import pico2d.pico2d as p
from core import Game, Rect


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def fixture(carrying=False):
    game = Game()
    game.start()
    game.player.x, game.player.y = 400.0, 360.0
    game.zombie.x, game.zombie.y = 1150.0, 580.0
    game.walls = []
    if carrying:
        game.pickup = (game.player.x, game.player.y)
        require(game.interact() == "pickup", "Fixture pickup failed")
    game.pop_events()
    return game


def aim(game):
    return (game.player.x + math.cos(game.player.angle) * 300,
            game.player.y + math.sin(game.player.angle) * 300)


def capture(name, player):
    """Save the actual back buffer before Present; return a player-area sample."""
    surface = p.SDL_CreateRGBSurfaceWithFormat(
        0, game_main.WIDTH, game_main.HEIGHT, 32, p.SDL_PIXELFORMAT_ARGB8888,
    )
    require(bool(surface), "SDL capture surface allocation failed")
    try:
        require(p.SDL_RenderReadPixels(
            p.renderer, None, p.SDL_PIXELFORMAT_ARGB8888,
            surface.contents.pixels, surface.contents.pitch,
        ) == 0, f"SDL read failed: {p.SDL_GetError()!r}")
        path = OUTPUT / f"{name}.png"
        require(p.IMG_SavePNG(surface, str(path).encode("utf-8")) == 0,
                f"PNG save failed: {path.name}")
        pitch = surface.contents.pitch
        pixels = ctypes.string_at(surface.contents.pixels, pitch * game_main.HEIGHT)
        x, y = round(player.x), round(player.y)
        # This comparison checks reset consistency, not body/hand identification.
        sample = b"".join(
            pixels[(game_main.HEIGHT - 1 - row) * pitch + (x - 80) * 4:
                   (game_main.HEIGHT - 1 - row) * pitch + (x + 81) * 4]
            for row in range(y - 80, y + 81)
        )
        return path.relative_to(ROOT).as_posix(), sample
    finally:
        p.SDL_FreeSurface(surface)


def track_resources(stack, live, loaded_images, release_issues):
    """Pass through real SDL calls while recording Renderer-owned resources."""
    def address(handle):
        return ctypes.cast(handle, ctypes.c_void_p).value

    def create(original, kind):
        def call(*args, **kwargs):
            handle = original(*args, **kwargs)
            if handle:
                live[kind][address(handle)] = handle
            return handle
        return call

    def destroy(original, kind):
        def call(handle, *args, **kwargs):
            key = address(handle)
            if not key:
                return None
            if key not in live[kind]:
                # Fail the report without handing a duplicate free to native SDL.
                release_issues.append(f"Repeated/untracked {kind} release: {key}")
                return None
            value = original(handle, *args, **kwargs)
            live[kind].pop(key)
            return value
        return call

    for kind, creators, releaser in (
        ("textures", ("SDL_CreateTexture", "SDL_CreateTextureFromSurface", "IMG_LoadTexture"), "SDL_DestroyTexture"),
        ("fonts", ("TTF_OpenFont",), "TTF_CloseFont"),
        ("audio_chunks", ("Mix_LoadWAV",), "Mix_FreeChunk"),
    ):
        for name in creators:
            stack.enter_context(patch.object(p, name, create(getattr(p, name), kind)))
        stack.enter_context(patch.object(p, releaser, destroy(getattr(p, releaser), kind)))

    original_load = p.load_image

    def load_image(path, *args, **kwargs):
        image = original_load(path, *args, **kwargs)
        loaded_images.append(Path(path).resolve().relative_to(ROOT).as_posix())
        return image

    stack.enter_context(patch.object(p, "load_image", load_image))


def scenarios(renderer, result):
    def render(name, game, moving=False):
        before = deepcopy(vars(game))
        for _ in range(2):
            renderer.draw(game, aim(game), moving=moving, focused=True)
            require(vars(game) == before,
                    f"{name}: draw mutated gameplay state or pending events/noises")
        path, pixels = capture(name, game.player)
        result["captures"].append({
            "name": name, "path": path, "player": asdict(game.player),
            "carrying": game.carrying, "attack_elapsed": game.attack_elapsed,
            "time": game.time, "moving_from_displacement": moving,
        })
        return pixels

    for carrying in (False, True):
        label = "parcel" if carrying else "empty"
        game = fixture(carrying)
        for degrees in range(0, 360, 45):
            game.player.angle = math.radians(degrees)
            render(f"direction-{label}-{degrees:03}", game)
    result["checks"].append("Eight headings before and after pickup; PNG pose review pending")

    for carrying in (False, True):
        label = "parcel" if carrying else "empty"
        game = fixture(carrying)
        game.zombie.x, game.zombie.y = game.player.x + 60, game.player.y
        require(game.swing() and not game.swing(), "Attack acceptance/reentry changed")
        events = []
        for phase, dt in (("preparation", 0.09), ("impact", 0.10), ("recovery", 0.23)):
            game.step(dt, 0, 0, False, *aim(game))
            if phase == "preparation":
                require(game.attack_elapsed < game.attack_hit_time, "Preparation time skipped")
            elif phase == "impact":
                require(game.attack_elapsed >= game.attack_hit_time and game.zombie.hp == 4,
                        "Impact did not resolve once")
            else:
                require(game.attack_hit_time + 0.12 < game.attack_elapsed < game.attack_duration,
                        "Recovery time skipped")
            render(f"attack-{label}-{phase}", game)
            events.extend(game.pop_events())
        game.step(0.20, 0, 0, False, *aim(game))
        events.extend(game.pop_events())
        kinds = [event.kind for event in events]
        require(game.attack_elapsed is None and game.zombie.hp == 4,
                "Attack completion or single damage changed")
        require(kinds.count("attack") == 1 and kinds.count("hit") == 1,
                f"Duplicate attack/hit events: {kinds}")
    result["checks"].append("Attack preparation/impact/recovery; exactly one attack event and one hit")

    game = fixture()
    render("movement-idle", game)
    for state, running, speed in (("walk", False, game.walk_speed), ("run", True, game.run_speed)):
        before = (game.player.x, game.player.y)
        # Aim backwards while moving right: facing must remain independent.
        game.step(0.2, 1, 0, running, game.player.x - 300, game.player.y)
        distance = math.dist(before, (game.player.x, game.player.y))
        require(math.isclose(distance, speed * 0.2, abs_tol=1e-7), f"{state}: actual speed changed")
        require(game.player.state == state and math.isclose(abs(game.player.angle), math.pi),
                f"{state}: movement/facing state changed")
        render(f"movement-{state}-backwards", game, moving=distance > 1e-8)

    game = fixture()
    game.walls = [Rect(500.0, 300.0, 100.0, 120.0)]
    game.player.x = 500.0 - game.player.radius
    before = (game.player.x, game.player.y)
    stamina = game.stamina
    game.step(0.2, 1, 0, True, *aim(game))
    distance = math.dist(before, (game.player.x, game.player.y))
    require(distance == 0 and game.player.state == "idle" and game.stamina == stamina,
            "Blocked movement changed position/state/stamina")
    require(not any(event.kind in ("walk", "run") for event in game.pop_events()),
            "Blocked movement emitted player footsteps")
    render("movement-blocked-idle", game, moving=distance > 1e-8)
    result["checks"].append("Actual idle/walk/run and wall-blocked displacement; backwards aiming preserved")

    game = Game()
    game.start()
    baseline = render("restart-baseline", game)
    old_player = game.player
    require(game.interact() == "pickup", "Restart fixture pickup failed")
    game.step(0.2, 1, 0, True, 160, 500)
    require(game.swing(), "Restart fixture attack failed")
    render("restart-old-actor", game, moving=True)
    game.restart()
    require(game.player is not old_player and not game.carrying
            and game.attack_elapsed is None and game.player.state == "idle",
            "Restart did not replace/reset the Actor")
    require(render("restart-new-actor", game) == baseline,
            "Restart player-area pixels differ from baseline; inspect stale pose/cache")
    result["checks"].append("Replaced Actor resets parcel/attack/pose to baseline player-area pixels")


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "failed", "verification": "Actual Renderer and native SDL with dummy video/audio",
        "visual_review": "pending; PNGs do not certify asset quality or left/right hands",
        "limits": "Direct Game/Renderer fixtures; main.run input wiring, physical controls and listening not tested",
        "checks": [], "captures": [], "loaded_images": [], "errors": [],
    }
    live = {kind: {} for kind in ("textures", "fonts", "audio_chunks")}
    release_issues = []
    renderer = None
    canvas_open = False
    with ExitStack() as stack:
        try:
            # Mark before initialization so partial open_canvas failures still close SDL.
            canvas_open = True
            p.open_canvas(game_main.WIDTH, game_main.HEIGHT, sync=False)
            if not p.renderer:
                p.renderer = p.SDL_CreateRenderer(p.window, -1, p.SDL_RENDERER_SOFTWARE)
            require(bool(p.renderer), f"SDL renderer unavailable: {p.SDL_GetError()!r}")
            p.hide_lattice()
            p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
            track_resources(stack, live, result["loaded_images"], release_issues)
            renderer = game_main.Renderer()
            scenarios(renderer, result)
        except Exception as error:
            result["errors"].append(f"{type(error).__name__}: {error}")
        finally:
            cleanup = {"renderer_close_before_canvas": False}
            if renderer is not None:
                try:
                    renderer.close()
                    gc.collect()
                    cleanup["renderer_close_before_canvas"] = True
                    cleanup["live_after_renderer_close"] = {kind: len(handles) for kind, handles in live.items()}
                    require(not any(live.values()), f"Native resources remain after Renderer.close: {cleanup['live_after_renderer_close']}")
                    result["checks"].append("Tracked textures/fonts/audio chunks released before SDL shutdown")
                except Exception as error:
                    result["errors"].append(f"Cleanup {type(error).__name__}: {error}")
            # Dispose the renderer while SDL is alive, even when its close failed.
            renderer = None
            gc.collect()
            # pico2d 1.5.1 Font has no finalizer: test-only fallback, still a failure above.
            cleanup["harness_font_fallback_count"] = len(live["fonts"])
            for font in tuple(live["fonts"].values()):
                try:
                    p.TTF_CloseFont(font)
                except Exception as error:
                    result["errors"].append(f"Font fallback {type(error).__name__}: {error}")
            cleanup["release_issues"] = release_issues
            result["errors"].extend(release_issues)
            if canvas_open:
                try:
                    p.close_canvas()
                except Exception as error:
                    result["errors"].append(f"Canvas close {type(error).__name__}: {error}")
            result["cleanup"] = cleanup
    result["loaded_images"] = sorted(set(result["loaded_images"]))
    result["status"] = "passed" if not result["errors"] else "failed"
    (OUTPUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "captures": len(result["captures"]),
                      "errors": result["errors"], "report": "tmp/player-asset-qa/result.json"}, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(run())
