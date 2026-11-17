"""Opening and music wiring through the real SDL event and render loop."""
from contextlib import ExitStack
import ctypes
from itertools import count
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from combat import ZombieAttack
import pico2d.pico2d as p


class OpeningTests(unittest.TestCase):
    def play(self, batches, *, clock=None, dead=False, smoke=False):
        opening_times, game, worlds, cleanup = [], [], [], []
        music = Mock()
        music.close.side_effect = lambda: cleanup.append("music")
        factory = Mock(return_value=music)
        original_opening, original_draw = main.opening.draw, main.Renderer.draw
        original_world, original_poll, original_close = main.CombatWorld, main.poll_events, p.close_canvas
        original_init = main.Renderer.__init__
        batches = iter(batches)
        ticks = clock if clock is not None else (i / 60 for i in count())
        settings = None

        def initialize(renderer):
            nonlocal settings
            original_init(renderer)
            settings = renderer.audio_settings
            p.SDL_FlushEvents(p.SDL_FIRSTEVENT, p.SDL_LASTEVENT)

        def poll():
            for kind, *args in next(batches, (("quit",),)):
                event = p.SDL_Event()
                if kind == "key":
                    event.type = p.SDL_KEYDOWN
                    event.key.keysym.sym = args[0]
                elif kind == "click":
                    event.type = p.SDL_MOUSEBUTTONDOWN
                    event.button.button = p.SDL_BUTTON_LEFT
                    event.button.x, event.button.y = (760, 569)
                elif kind == "lost":
                    event.type = p.SDL_WINDOWEVENT
                    event.window.event = p.SDL_WINDOWEVENT_FOCUS_LOST
                elif kind == "quit":
                    event.type = p.SDL_QUIT
                else:
                    raise AssertionError(kind)
                self.assertEqual(p.SDL_PushEvent(ctypes.byref(event)), 1)
            return original_poll()

        def draw_opening(elapsed, *args):
            self.assertFalse(worlds, "The world must wait until opening ends")
            opening_times.append(elapsed)
            original_opening(elapsed, *args)

        def make_world():
            world = original_world()
            if dead:
                world.zombie.hp = 0
            worlds.append(world)
            return world

        def draw(renderer, player, walls, target, focused=True):
            original_draw(renderer, player, walls, target, focused)
            world = renderer.combat
            game.append((player.x, player.y, world.attack is not None, world.zombie.x, world.zombie.y))

        def close():
            cleanup.append("canvas")
            original_close()

        with ExitStack() as patches:
            patches.enter_context(patch.dict("os.environ", {
                "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "SDL_RENDER_DRIVER": "software",
            }))
            patches.enter_context(patch.dict(sys.modules, {"spatial_audio": SimpleNamespace(BackgroundMusic=factory)}))
            patches.enter_context(patch.object(p, "SDL_GetWindowFlags", return_value=p.SDL_WINDOW_INPUT_FOCUS))
            patches.enter_context(patch.object(p, "close_canvas", close))
            patches.enter_context(patch.object(main.time, "perf_counter", side_effect=iter(ticks)))
            patches.enter_context(patch.object(main, "poll_events", poll))
            patches.enter_context(patch.object(main, "CombatWorld", side_effect=make_world))
            patches.enter_context(patch.object(main, "capture"))
            patches.enter_context(patch.object(main.Renderer, "__init__", initialize))
            patches.enter_context(patch.object(main.Renderer, "draw", draw))
            patches.enter_context(patch.object(main.opening, "draw", draw_opening))
            main.run(smoke_test=smoke, show_opening=True, practice=True)
        self.assertEqual(cleanup, ["canvas"] if smoke else ["music", "canvas"])
        if smoke:
            factory.assert_not_called()
        else:
            factory.assert_called_once_with(main.BASE_DIR / "assets/audio/last-delivery.mp3", settings=settings)
            self.assertIs(factory.call_args.kwargs["settings"], settings)
            music.start.assert_called_once_with()
            music.close.assert_called_once_with()
        return opening_times, game, worlds, music.update.call_args_list

    def test_three_cuts_end_at_eight_seconds_and_drain_the_transition_batch(self):
        opening, game, worlds, music = self.play(
            [[("key", p.SDLK_w), ("click",)], [("lost",)], [], [], [],
             [("key", p.SDLK_d), ("click",)], [], [("quit",)]],
            clock=[0, 0, 2.6, 3.5, 5.2, 7.99, 8.0, 8.0, 8.02, 8.04],
        )
        self.assertEqual(opening, [0, 2.6, 3.5, 5.2, 7.99])
        self.assertEqual(len(worlds), 1)
        self.assertEqual(len(game), 1)
        self.assertEqual(game[0][:3], (480, 180, False))
        self.assertEqual([call.kwargs for call in music[:5]], [
            {"opening": True, "focused": focused} for focused in (True, False, True, True, True)
        ])
        x, y, _, zx, zy = game[0]
        self.assertEqual(music[-1].kwargs, {"distance": math.hypot(zx - x, zy - y), "focused": True})

    def test_both_enter_keys_skip_and_r_restarts_only_the_game(self):
        for key in (p.SDLK_RETURN, p.SDLK_KP_ENTER):
            with self.subTest(key=key):
                opening, game, worlds, music = self.play([
                    [("key", p.SDLK_w), ("click",), ("key", key), ("key", p.SDLK_a), ("click",)],
                    [], [("key", p.SDLK_d), ("click",)], [("key", p.SDLK_r)], [("quit",)],
                ])
                self.assertFalse(opening)
                self.assertEqual(len(worlds), 1)
                self.assertEqual(game[0][:3], (480, 180, False))
                self.assertEqual(game[1][0], 480)
                self.assertTrue(game[1][2])
                self.assertEqual(game[2][:3], (480, 180, False))
                self.assertTrue(all(not call.kwargs.get("opening") for call in music))

    def test_escape_or_quit_exits_even_when_enter_was_queued_first(self):
        for stop in (("key", p.SDLK_ESCAPE), ("quit",)):
            with self.subTest(stop=stop):
                opening, game, worlds, _ = self.play([[("key", p.SDLK_RETURN), stop]])
                self.assertEqual((opening, game, worlds), ([], [], []))

    def test_dead_zombie_omits_distance_and_lost_focus_pauses_music(self):
        _, game, _, music = self.play([
            [("key", p.SDLK_RETURN)], [("lost",)], [("quit",)],
        ], dead=True)
        self.assertEqual(len(game), 1)
        self.assertEqual(music[0].kwargs, {"distance": None, "focused": False})

    def test_smoke_stays_on_the_three_game_fixtures(self):
        opening, game, worlds, music = self.play([[], [], []], smoke=True)
        self.assertFalse(opening)
        self.assertEqual([frame[1] for frame in game], [180, 420, 300])
        self.assertEqual(len(worlds), 1)
        self.assertFalse(music)


class EndingTests(unittest.TestCase):
    def test_world_sound_position_keeps_distance_and_softens_pan_near_listener(self):
        origin = (140, 180)
        self.assertEqual(main.sound_position(origin, (240, 180)), (100.0, 1.0))
        self.assertEqual(main.sound_position(origin, (80, 260)), (100.0, -0.6))
        self.assertEqual(main.sound_position(origin, (140, 80)), (100.0, 0.0))
        self.assertEqual(main.sound_position(origin, (176, 180)), (36.0, 0.5))
        self.assertEqual(main.sound_position(origin, origin), (0.0, 0.0))

    def test_failure_animates_the_hit_scene_without_updating_combat(self):
        duration = main.opening.FAILURE_DURATION
        renderer, world, audio, art = Mock(), main.CombatWorld(), Mock(), object()
        world.player_hp = 1
        zombie = world.zombie
        zombie.x, zombie.y = world.player.x - 20, world.player.y
        zombie.attack = ZombieAttack(0.0, "right", .29)
        world.update(.02)
        self.assertEqual(world.result, "defeated")
        self.assertIsNone(zombie.attack)
        source, attack = world.fatal_zombie_strike
        self.assertIs(source, zombie)
        hit_elapsed = attack.elapsed
        pose_times = []
        renderer.combat_visual._motion_for.return_value = SimpleNamespace(attack_facing="front_right")

        def observe(player, walls, target, elapsed, attacker):
            self.assertIs(player, world.player)
            self.assertIs(walls, world.walls)
            self.assertEqual(target, (123, 456))
            self.assertIs(attacker[0], zombie)
            self.assertIsNot(attacker[1], zombie)
            self.assertEqual(attacker[1].attack.facing, "front_right")
            self.assertEqual((world.player_hp, zombie.attack, attack.elapsed), (0, None, hit_elapsed))
            pose_times.append((elapsed, attacker[1].attack.elapsed))

        renderer.draw_defeat.side_effect = observe
        with (
            patch.object(main.time, "perf_counter", side_effect=[0.0, 0.0, duration / 2, duration]),
            patch.object(main, "cutscene_controls", side_effect=[(False, False), (True, True), (False, False)]),
            patch.object(p, "window", object(), create=True),
            patch.object(p, "SDL_GetWindowFlags", return_value=p.SDL_WINDOW_INPUT_FOCUS),
            patch.object(main.opening, "draw_ending") as draw,
            patch.object(main.opening, "draw_defeat_overlay") as overlay,
            patch.object(p, "update_canvas"),
        ):
            self.assertTrue(main.play_ending(renderer, art, world, audio, player_hit=True, target=(123, 456)))
        draw.assert_not_called()
        self.assertEqual(overlay.call_args_list, [call(0, renderer.font, art), call(duration / 2, renderer.font, art)])
        self.assertEqual(pose_times, [(0, hit_elapsed), (duration / 2, hit_elapsed + duration / 2 * .30)])
        self.assertEqual(audio.mock_calls, [call.stop(), call.play_player_hit(), call.stop(), call.stop()])
        world.reset()
        self.assertIsNone(world.fatal_zombie_strike)

    def test_three_stop_delivery_only_plays_one_ending_and_skip_does_not_retry(self):
        world = main.DeliveryWorld(two_stop_unlocked=True)
        first, second, third = main.DELIVERY_CONTRACTS[2].stops

        def tap(*keys):
            return tuple((kind, key) for key in keys for kind in (p.SDL_KEYDOWN, p.SDL_KEYUP))

        def hold(position, frames):
            return [(position, ((p.SDL_KEYDOWN, p.SDLK_e),)), *[(None, ())] * (frames - 1)]

        release_e = (p.SDL_KEYUP, p.SDLK_e)
        batches = iter([
            (None, tap(p.SDLK_3, p.SDLK_RETURN)),
            (None, tap(p.SDLK_e, p.SDLK_f)),
            (None, tap(p.SDLK_f)),
            *hold(None, 10),
            (None, (release_e,)),
            *hold(first.position, 20),
            (None, (release_e,)),
            (None, tap(p.SDLK_m, p.SDLK_ESCAPE)),
            (None, tap(p.SDLK_m)),
            (None, ()),
            (None, ((p.SDL_WINDOWEVENT, p.SDL_WINDOWEVENT_FOCUS_LOST),)),
            (None, tap(p.SDLK_ESCAPE)),
            *hold(second.position, 20),
            (None, (release_e,)),
            *hold(third.position, 20),
            (None, (release_e, *tap(p.SDLK_d))),
            (None, tap(p.SDLK_RETURN, p.SDLK_r, p.SDLK_e)),
            (None, ()),
            (None, tap(p.SDLK_KP_ENTER)),
        ])
        audio, music, art = Mock(), Mock(), Mock()
        frames, endings, combat_frames = [], [], []
        original_poll = main.poll_events

        def poll():
            batch = next(batches, None)
            if batch is None:
                event = p.SDL_Event()
                event.type = p.SDL_QUIT
                self.assertEqual(p.SDL_PushEvent(ctypes.byref(event)), 1)
            else:
                position, events = batch
                if position is not None:
                    world.player.x, world.player.y = position
                    world.zombies.clear()
                for kind, key in events:
                    event = p.SDL_Event()
                    event.type = kind
                    if kind == p.SDL_WINDOWEVENT:
                        event.window.event = key
                    else:
                        event.key.keysym.sym = key
                    self.assertEqual(p.SDL_PushEvent(ctypes.byref(event)), 1)
            return original_poll()

        def draw_game(renderer, player, walls, target, focused=True):
            state = (world.result, world.parcel, len(world.completed_stops), renderer.choosing_delivery)
            if not frames or state != frames[-1]:
                frames.append(state)
            if world.zombies:
                combat_frames.append(music.update.call_args.kwargs["combat"])
                if len(combat_frames) == 1:
                    world.zombie.hp = 0
                    world.zombie.state = "chase"
                elif len(combat_frames) == 2:
                    zombie = world.zombies[1]
                    zombie.x, zombie.y = player.x + 65, player.y
                    zombie.state = "chase"
                elif len(combat_frames) == 3:
                    self.assertAlmostEqual(audio.update.call_args.kwargs["pan"], (world.zombies[1].x - player.x) / 72)
                    self.assertGreater(audio.update.call_args.kwargs["pan"], 0)
                    step, = audio.update.call_args.kwargs["footstep_sources"]
                    self.assertEqual(step.source_id, id(world.zombies[1]))
                    self.assertGreater(step.stride, 0)
                    world.zombies[1].hp = 0

        def draw_ending(elapsed, font, cutscene_art, delivery):
            self.assertIs(cutscene_art, art)
            self.assertEqual(delivery.completed_stops, {first, second, third})
            self.assertFalse(music.update.call_args.kwargs["focused"])
            endings.append(delivery.result)

        clock = (i / 20 for i in count())
        with ExitStack() as patches:
            patches.enter_context(patch.dict("os.environ", {
                "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "SDL_RENDER_DRIVER": "software",
            }))
            patches.enter_context(patch.dict(sys.modules, {"spatial_audio": SimpleNamespace(BackgroundMusic=Mock(return_value=music))}))
            patches.enter_context(patch.object(main, "PLAYABLE_CONTRACTS", {3: main.DELIVERY_CONTRACTS[2]}))
            patches.enter_context(patch.object(main, "CONTRACT_NUMBERS", (3,)))
            patches.enter_context(patch.object(main, "load_contract_previews", return_value=[None]))
            patches.enter_context(patch.object(world, "select_playable_contract", lambda number: world.select_contract(2)))
            patches.enter_context(patch.object(main, "DeliveryWorld", return_value=world))
            patches.enter_context(patch.object(main, "ZombieAudio", return_value=audio))
            patches.enter_context(patch.object(main, "poll_events", poll))
            patches.enter_context(patch.object(main.time, "perf_counter", side_effect=clock))
            patches.enter_context(patch.object(main.Renderer, "draw", draw_game))
            patches.enter_context(patch.object(main.opening, "CutsceneArt", return_value=art))
            patches.enter_context(patch.object(main.opening, "draw_ending", draw_ending))
            patches.enter_context(patch.object(p, "SDL_GetWindowFlags", return_value=p.SDL_WINDOW_INPUT_FOCUS))
            main.run()

        self.assertEqual(endings, ["delivered"])
        self.assertEqual([combat > 0 for combat in combat_frames[:4]], [False, False, True, False])
        self.assertEqual(frames, [("playing", "waiting", 0, False), ("playing", "carrying", 0, False),
                                  ("playing", "carrying", 1, False), ("playing", "carrying", 2, False),
                                  ("delivered", "delivered", 3, False),
                                  ("playing", "waiting", 0, False)])
        audio.play_delivery_cue.assert_called_once_with()
        audio.play_parcel_pickup.assert_called_once_with()
        self.assertEqual(audio.play_parcel_drop.call_args_list, [call(), call()])
        audio.play_bottle_pickup.assert_called_once_with()
        audio.play_player_hit.assert_not_called()
        map_calls = [i for i, entry in enumerate(audio.mock_calls) if entry == call.play_map_toggle()]
        self.assertEqual(len(map_calls), 2)
        opening_map, closing_map = map_calls
        self.assertEqual(audio.mock_calls[opening_map - 1].kwargs["active"], False)
        self.assertEqual(audio.mock_calls[opening_map - 1].kwargs["preserve_map_cue"], True)
        self.assertEqual(audio.mock_calls[opening_map + 1].kwargs["preserve_map_cue"], True)
        self.assertEqual(audio.mock_calls[opening_map + 2].kwargs["preserve_map_cue"], False)
        self.assertEqual(audio.mock_calls[closing_map - 1].kwargs["active"], True)
        audio.close.assert_called_once_with()
        art.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
