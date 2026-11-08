"""Focused R2-A frame/anchor, picking and real SDL event-queue regressions."""
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(TEST_DIR.parent))

import main
import combat_visual
from combat import CombatWorld
from combat_visual import CombatVisual, METADATA_PATH
import test_visual_input_r1a as input_fixture


FR_BOUNDARIES = (0, .045, .09, .135, .18, .225, .27, .32, .37, .425, .48, .54, .6)


def combat_metadata():
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    metadata["zombie"] = json.loads(combat_visual.ZOMBIE_METADATA_PATH.read_text(encoding="utf-8"))
    metadata["zombie_attack"] = json.loads(combat_visual.ZOMBIE_ATTACK_METADATA_PATH.read_text(encoding="utf-8"))
    return metadata


def zombie_body_point(visual, zombie, foot):
    frame = visual._zombie_frame(zombie)
    scale = visual.metadata["zombie"]["scale"]
    row = min(map(int, frame["opaque_rows"]), key=lambda value: abs(value - 35))
    start, end = max(frame["opaque_rows"][str(row)], key=lambda span: span[1] - span[0])
    left, bottom, _, _ = combat_visual.sprite_rect(
        *foot, frame["clip_topleft"], frame["foot_pivot_topleft"], frame["clip_topleft"][3] * scale)
    return left + ((start + end) // 2 + .5) * scale, bottom + (frame["clip_topleft"][3] - row - .5) * scale


class CombatSpriteTests(unittest.TestCase):
    def setUp(self):
        self.visual = CombatVisual.__new__(CombatVisual)
        self.visual.metadata = combat_metadata()
        self.visual.images = {
            "attack": SimpleNamespace(h=self.visual.metadata["attack"]["canvas_size"][1], clip_draw=Mock()),
            "zombie": SimpleNamespace(h=self.visual.metadata["zombie"]["canvas_size"][1], clip_draw=Mock()),
        }
        self.visual.reset_zombie_animation()

    def attack(self, elapsed, facing="front_right"):
        return SimpleNamespace(elapsed=elapsed, facing=facing)

    def test_hit_and_recovery_boundaries_choose_the_authored_pose(self):
        frames = self.visual.metadata["attack"]["frames"]
        self.assertEqual([frame["start"] for frame in frames], list(FR_BOUNDARIES[:-1]))
        self.assertEqual([frame["end"] for frame in frames], list(FR_BOUNDARIES[1:]))
        for index, (start, end) in enumerate(zip(FR_BOUNDARIES, FR_BOUNDARIES[1:])):
            for t in (start, math.nextafter(end, -math.inf)):
                with self.subTest(t=t):
                    self.assertEqual(self.visual.attack_frame_index(self.attack(t)), index)
        for t in (-.1, .6, float("nan")):
            self.assertIsNone(self.visual.attack_frame_index(self.attack(t)))
        self.assertIsNone(self.visual.attack_frame_index(None))
        self.assertFalse(self.visual.draw_attack(self.attack(.18, "unknown"), 100, 200))
        self.visual.images["attack"].clip_draw.assert_not_called()

    def test_attack_full_cell_keeps_two_times_scale_and_ground_anchor(self):
        self.assertEqual(self.visual.metadata["attack"]["canvas_size"], [384, 288])
        for t, source in ((0, (0, 192)), (.135, (288, 192)), (.18, (0, 96)),
                          (.48, (192, 0)), (.54, (288, 0))):
            self.assertTrue(self.visual.draw_attack(self.attack(t), 100, 200))
            self.visual.images["attack"].clip_draw.assert_called_with(
                *source, 96, 96, 100.0, 264.0, 192.0, 192.0)

    def test_killing_hit_keeps_displaying_the_same_attack_through_recovery(self):
        world = CombatWorld()
        world.zombie.x, world.zombie.y, world.zombie.hp = 520, 140, 1
        world.player.aim_angle = -math.pi / 4
        world.start_attack()
        world.update(.18)
        self.assertEqual(world.result, "cleared")
        self.assertEqual(self.visual.attack_frame_index(world.attack), 4)
        self.assertTrue(self.visual.draw_attack(world.attack, 100, 200))
        world.update(.29)
        self.assertEqual(self.visual.attack_frame_index(world.attack), 9)
        world.update(.13)
        self.assertIsNone(world.attack)
        self.assertFalse(self.visual.draw_attack(world.attack, 100, 200))

    def test_twelve_visual_steps_keep_single_hit_at_018_and_recovery_at_060(self):
        world = CombatWorld()
        world.player.aim_angle = -math.pi / 4
        world.zombie.x, world.zombie.y = 520, 140
        world.zombie.stun_remaining = .4
        self.assertTrue(world.start_attack())
        previous = 0.0
        for index, boundary in enumerate(FR_BOUNDARIES[:-1]):
            world.update(boundary - previous)
            self.assertAlmostEqual(world.attack.elapsed, boundary)
            self.assertEqual(self.visual.attack_frame_index(world.attack), index)
            self.assertEqual(world.zombie.hp, 5 if boundary < .18 else 4)
            self.assertEqual(world.player_hp, 3)
            if boundary >= .18:
                self.assertAlmostEqual(world.zombie.stun_remaining, .4 - (boundary - .18))
            self.assertFalse(world.start_attack())
            previous = boundary
        world.update(.6 - previous)
        self.assertIsNone(world.attack)
        self.assertEqual((world.zombie.hp, world.player_hp, world.zombie.stun_remaining), (4, 3, 0.0))
        self.assertTrue(world.start_attack())

    def test_zombie_pick_uses_opaque_pixels_not_the_transparent_cell(self):
        world = CombatWorld()
        foot = main.world_to_screen(world.zombie.x, world.zombie.y)
        # Pick a real opaque body pixel; raw ground conversion changes its aim.
        screen = zombie_body_point(self.visual, world.zombie, foot)
        sdl = (screen[0], main.WINDOW_HEIGHT - 1 - screen[1])
        self.assertTrue(self.visual.zombie_contains(world.zombie, *foot, *screen))
        self.assertEqual(main.mouse_target(world, self.visual, *sdl), (600, 100))
        self.assertNotEqual(main.sdl_to_world(*sdl), (600, 100))
        padding = (foot[0] - 79, main.WINDOW_HEIGHT - 1 - (foot[1] - 15))
        self.assertEqual(main.mouse_target(world, self.visual, *padding), main.sdl_to_world(*padding))
        world.zombie.hp = 0
        self.assertEqual(main.mouse_target(world, self.visual, *sdl), main.sdl_to_world(*sdl))

    def test_zombie_stun_and_dead_states_use_separate_authored_cells(self):
        zombie = CombatWorld().zombie
        zombie.aim_angle = -math.pi / 4
        atlas_height = self.visual.metadata["zombie"]["canvas_size"][1]
        for hp, stun, x, row in ((5, 0, 80, 0), (4, .4, 80, 9), (0, .4, 0, 13)):
            zombie.hp, zombie.stun_remaining = hp, stun
            self.visual.update_zombie(zombie, 0, 0)
            self.visual.draw_zombie(zombie, 100, 200)
            cell = (x, atlas_height - (row + 1) * 80, 80, 80)
            self.assertEqual(self.visual.images["zombie"].clip_draw.call_args.args[:4], cell)

    def test_images_load_once_at_initialization_and_release_references(self):
        sources = combat_metadata()
        images = [SimpleNamespace(w=source["canvas_size"][0], h=source["canvas_size"][1],
                                  texture=object(), clip_draw=Mock()) for source in sources.values()]
        with (patch.object(combat_visual.p, "load_image", side_effect=images) as load,
              patch.object(combat_visual.p, "SDL_SetTextureScaleMode", return_value=0)):
            visual = CombatVisual()
            for t in (0, .18, .48):
                visual.draw_attack(self.attack(t), 100, 200)
            visual.draw_attack(self.attack(.18), 100, 200, walk_frame_index=7)
            self.assertEqual(load.call_count, len(sources))
            visual.close()
            self.assertEqual(visual.images, {})

    def test_zombie_depth_keeps_wall_and_player_tie_order(self):
        world = CombatWorld()
        world.zombie.y = world.player.y
        self.assertEqual([k for k, _ in main.sorted_drawables(world.player, world.walls, world.zombie)],
                         ["wall", "zombie", "player"])


class CombatInputTests(unittest.TestCase):
    def observe(self, initial, after_draw, maximum_draws=6):
        states = []
        original = main.Renderer.draw

        def draw(renderer, player, walls, target, focused=True):
            original(renderer, player, walls, target, focused)
            world = renderer.combat
            attack = world.attack
            states.append({"attack": attack, "elapsed": attack.elapsed if attack else None,
                           "angle": attack.angle if attack else None,
                           "facing": attack.facing if attack else None,
                           "display_facing": renderer.player_visual.locomotion.facing,
                           "phase": renderer.player_visual.locomotion.phase,
                           "zombie": (world.zombie.x, world.zombie.y),
                           "target": target, "hp": world.player_hp})

        with patch.object(main.Renderer, "draw", draw):
            frames = input_fixture.DummyInputTests._run_events(
                self, initial, after_draw, maximum_draws=maximum_draws)
        return frames, states

    def test_body_click_without_motion_picks_zombie_and_starts_fr_attack(self):
        visual = CombatVisual.__new__(CombatVisual)
        visual.metadata = combat_metadata()
        visual.reset_zombie_animation()
        world = CombatWorld()
        x, y = zombie_body_point(visual, world.zombie, main.world_to_screen(world.zombie.x, world.zombie.y))
        _, states = self.observe([("click", round(x), round(main.WINDOW_HEIGHT - 1 - y))], {1: [("quit",)]})
        self.assertIsNotNone(states[0]["attack"])
        self.assertEqual(states[0]["target"], (600, 100))
        self.assertAlmostEqual(states[0]["angle"], math.atan2(-80, 120))

    def test_hold_and_duplicate_down_after_recovery_do_not_auto_repeat(self):
        _, states = self.observe([("click", 760, 569)],
                                 {41: [("click", 760, 569)], 44: [("quit",)]}, 45)
        first = states[0]["attack"]
        self.assertTrue(first.stationary_front_right)
        self.assertIs(states[36]["attack"], first)
        self.assertTrue(all(s["attack"] is None or s["attack"] is first for s in states))
        self.assertTrue(all(s["attack"] is None for s in states[40:]))

    def test_release_then_fresh_down_can_start_after_recovery(self):
        _, states = self.observe([("click", 760, 569)],
                                 {41: [("release", 760, 569), ("click", 760, 569)],
                                  44: [("quit",)]}, 45)
        self.assertIsNotNone(states[41]["attack"])
        self.assertIsNot(states[41]["attack"], states[0]["attack"])

    def test_focus_loss_discards_queued_click_and_pauses_combat_time(self):
        _, states = self.observe([("click", 760, 569), ("lost",), ("gained",)],
                                 {1: [("quit",)]})
        self.assertIsNone(states[0]["attack"])
        self.assertEqual(states[0]["zombie"], (600, 100))
        _, states = self.observe([("click", 760, 569)],
                                 {1: [("lost",), ("gained",)], 2: [("quit",)]})
        self.assertEqual(states[0]["elapsed"], states[1]["elapsed"])
        self.assertEqual(states[0]["zombie"], states[1]["zombie"])

    def test_back_facing_can_start_the_authored_attack(self):
        _, states = self.observe([("click", 640, 269)], {1: [("quit",)]})
        self.assertIsNotNone(states[0]["attack"])
        self.assertEqual(states[0]["facing"], "back")

    def test_attack_keeps_angle_while_actual_movement_advances_walk_phase(self):
        frames, states = self.observe([("click", 760, 569), ("down", main.p.SDLK_d)],
                                     {1: [("motion", 160, 521)], 3: [("quit",)]})
        self.assertEqual(len(states), 3)
        for i, state in enumerate(states):
            self.assertAlmostEqual(frames[i]["x"], 481 + i)
            self.assertAlmostEqual(state["phase"], (i + 1) / 64)
            self.assertAlmostEqual(state["angle"], math.atan2(-80, 120))

    def test_r_resets_world_and_visual_phase_without_reloading_assets(self):
        frames, states = self.observe([("click", 760, 569), ("down", main.p.SDLK_d)],
                                     {1: [("down", main.p.SDLK_r)], 2: [("quit",)]})
        self.assertEqual((frames[1]["x"], frames[1]["y"]), (480, 180))
        self.assertIsNone(states[1]["attack"])
        self.assertEqual(states[1]["phase"], 0)
        self.assertEqual(states[1]["hp"], 3)


if __name__ == "__main__":
    unittest.main()
