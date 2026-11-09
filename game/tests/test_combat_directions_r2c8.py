"""R2-C8 direction dispatch and real SDL-queue attack/walk integration."""
from copy import deepcopy
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
from combat import CombatWorld, STUN_DURATION
from combat_visual import CombatVisual, METADATA_PATH
import test_attack_walk_visual as walk_fixture
from test_combat_visual_r2a import combat_metadata


DIRECTIONS = (("front_right", (1, -1)), ("right", (1, 0)),
              ("back_right", (1, 1)), ("back", (0, 1)),
              ("back_left", (-1, 1)), ("left", (-1, 0)),
              ("front_left", (-1, -1)), ("front", (0, -1)))
BOUNDARIES = (0, .045, .09, .135, .18, .225, .27, .32, .37, .425, .48, .54, .6)


def source_names(facing):
    return ("attack", "attack_walk") if facing == "front_right" else (
        f"attack_{facing}", f"attack_walk_{facing}")


def click(facing, origin=(480, 180)):
    dx, dy = dict(DIRECTIONS)[facing]
    # Keep clicks away from the initial zombie's opaque body.
    distance = 240 if facing == "right" else 160
    x, y = main.world_to_screen(origin[0] + dx * distance, origin[1] + dy * distance)
    return ("click", round(x), round(main.WINDOW_HEIGHT - 1 - y))


class DirectionSpriteTests(unittest.TestCase):
    def setUp(self):
        self.metadata = combat_metadata()
        # Missing art sources use in-memory fixtures only until the handoff.
        for facing, _ in DIRECTIONS[1:]:
            for key, base in zip(source_names(facing), ("attack", "attack_walk")):
                if key not in self.metadata:
                    self.metadata[key] = deepcopy(self.metadata[base])
                    self.metadata[key]["facing"] = facing
                    self.metadata[key]["image"] = f"fixture-{key}.png"
        self.visual = CombatVisual.__new__(CombatVisual)
        self.visual.metadata = self.metadata
        self.visual.images = {key: SimpleNamespace(h=source["canvas_size"][1], clip_draw=Mock())
                              for key, source in self.metadata.items()}

    def test_every_direction_stage_and_walk_cell_uses_its_own_source_and_anchor(self):
        for facing, _ in DIRECTIONS:
            stationary, walking = source_names(facing)
            frames = self.metadata[stationary]["frames"]
            self.assertEqual([frame["start"] for frame in frames], list(BOUNDARIES[:-1]))
            self.assertEqual([frame["end"] for frame in frames], list(BOUNDARIES[1:]))
            for index, elapsed in enumerate(BOUNDARIES[:-1]):
                attack = SimpleNamespace(facing=facing, elapsed=elapsed)
                self.assertEqual(self.visual.attack_frame_index(attack), index)
                before_end = SimpleNamespace(facing=facing, elapsed=math.nextafter(BOUNDARIES[index + 1], -math.inf))
                self.assertEqual(self.visual.attack_frame_index(before_end), index)
                for walk in (None, 0, *range(1, 9)):
                    with self.subTest(facing=facing, stage=index, walk=walk):
                        self.assertTrue(self.visual.draw_attack(attack, 100, 200, walk))
                        key = walking if walk else stationary
                        x, y = ((walk - 1) * 96, 1152 - (index + 1) * 96) if walk else (
                            index % 4 * 96, 288 - (index // 4 + 1) * 96)
                        image = self.visual.images[key]
                        image.clip_draw.assert_called_once_with(x, y, 96, 96, 100.0, 264.0, 192.0, 192.0)
                        image.clip_draw.reset_mock()
        self.assertTrue(all(image.clip_draw.call_count == 0 for image in self.visual.images.values()))

    def test_eight_directions_keep_one_hit_at_018_and_recovery_at_060(self):
        for facing, (dx, dy) in DIRECTIONS:
            with self.subTest(facing=facing):
                world = CombatWorld()
                world.walls = []
                world.player.aim_angle = math.atan2(dy, dx)
                distance = math.hypot(dx, dy)
                world.zombie.x = world.player.x + dx / distance * 60
                world.zombie.y = world.player.y + dy / distance * 60
                world.zombie.stun_remaining = .4
                self.assertTrue(world.start_attack(facing))
                previous = 0.0
                for index, boundary in enumerate(BOUNDARIES[:-1]):
                    world.update(boundary - previous)
                    self.assertEqual(world.attack.facing, facing)
                    self.assertEqual(world.attack.angle, world.player.aim_angle)
                    self.assertAlmostEqual(world.attack.elapsed, boundary)
                    self.assertEqual(self.visual.attack_frame_index(world.attack), index)
                    self.assertEqual((world.player_hp, world.zombie.hp), (3, 5 if boundary < .18 else 4))
                    if boundary >= .18:
                        self.assertAlmostEqual(world.zombie.stun_remaining, STUN_DURATION - (boundary - .18))
                    self.assertFalse(world.start_attack(facing))
                    previous = boundary
                world.update(.6 - previous)
                self.assertIsNone(world.attack)
                self.assertEqual((world.player_hp, world.zombie.hp, world.result), (3, 4, "playing"))
                self.assertAlmostEqual(world.zombie.stun_remaining, STUN_DURATION - .42)
                self.assertTrue(world.start_attack(facing))

    def test_unknown_facing_and_unsupported_elapsed_do_not_draw(self):
        for facing, elapsed in (("unknown", .18), ("front", -.001), ("left", .6),
                                ("back", math.nan), ("back_left", math.inf),
                                ("right", None), ("front_left", ".18")):
            with self.subTest(facing=facing, elapsed=elapsed):
                self.assertFalse(self.visual.draw_attack(SimpleNamespace(facing=facing, elapsed=elapsed),
                                                         100, 200, 8))
        self.assertTrue(all(image.clip_draw.call_count == 0 for image in self.visual.images.values()))

    def test_all_nineteen_sources_load_once_and_rendering_never_reloads(self):
        images = [SimpleNamespace(w=s["canvas_size"][0], h=s["canvas_size"][1],
                                  texture=object(), clip_draw=Mock()) for s in self.metadata.values()]
        path = SimpleNamespace(read_text=Mock(return_value=json.dumps(self.metadata)), parent=Path("fixture"))
        with (patch.object(combat_visual, "METADATA_PATH", path),
              patch.object(combat_visual.p, "load_image", side_effect=images) as load,
              patch.object(combat_visual.p, "SDL_SetTextureScaleMode", return_value=0) as nearest):
            visual = CombatVisual()
            self.assertEqual(set(visual.images), set(self.metadata))
            for facing, _ in DIRECTIONS:
                for walk in (0, 7):
                    self.assertTrue(visual.draw_attack(SimpleNamespace(facing=facing, elapsed=.18), 100, 200, walk))
            self.assertEqual(load.call_count, 19)
            self.assertEqual(nearest.call_count, 19)
            self.assertEqual([args.args[0] for args in load.call_args_list],
                             [str({"zombie": combat_visual.ZOMBIE_METADATA_PATH.parent,
                                   "zombie_attack": combat_visual.ZOMBIE_ATTACK_METADATA_PATH.parent}.get(key, path.parent)
                                  / source["image"]) for key, source in self.metadata.items()])
            visual.close()
            self.assertEqual(visual.images, {})

    def test_bad_middle_canvas_clears_loaded_image_references(self):
        images = [SimpleNamespace(w=s["canvas_size"][0], h=s["canvas_size"][1], texture=object())
                  for s in self.metadata.values()]
        images[7].w = 1
        path = SimpleNamespace(read_text=Mock(return_value=json.dumps(self.metadata)), parent=Path("fixture"))
        original_close = CombatVisual.close
        with (patch.object(combat_visual, "METADATA_PATH", path),
              patch.object(combat_visual.p, "load_image", side_effect=images) as load,
              patch.object(combat_visual.p, "SDL_SetTextureScaleMode", return_value=0),
              patch.object(CombatVisual, "close", autospec=True, side_effect=original_close) as close):
            with self.assertRaisesRegex(ValueError, "canvas differs"):
                CombatVisual()
            self.assertEqual(load.call_count, 8)
            self.assertEqual(close.call_count, 1)
            self.assertEqual(close.call_args.args[0].images, {})


class AuthoredDirectionMetadataTests(unittest.TestCase):
    def test_runtime_metadata_exposes_all_eight_pairs_with_existing_fr_names(self):
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(metadata), 18)
        for facing, _ in DIRECTIONS:
            for key, count, canvas in zip(source_names(facing), (12, 96), ([384, 288], [768, 1152])):
                with self.subTest(source=key):
                    self.assertEqual(metadata[key]["facing"], facing)
                    self.assertEqual(len(metadata[key]["frames"]), count)
                    self.assertEqual(metadata[key]["canvas_size"], canvas)
                    self.assertTrue((METADATA_PATH.parent / metadata[key]["image"]).is_file())


class DirectionInputTests(unittest.TestCase):
    observe = walk_fixture.AttackWalkInputTests.observe

    def test_eight_facings_start_render_and_lock_aim_and_position(self):
        for index, (facing, (dx, dy)) in enumerate(DIRECTIONS):
            with self.subTest(facing=facing):
                axis = ((dx, dy), (-dx, -dy), (-dy, dx))[index % 3]
                keys = [key for component, key in ((axis[0] > 0, main.p.SDLK_d),
                                                   (axis[0] < 0, main.p.SDLK_a),
                                                   (axis[1] > 0, main.p.SDLK_w),
                                                   (axis[1] < 0, main.p.SDLK_s)) if component]
                opposite = DIRECTIONS[(index + 4) % 8][0]
                cursor = ("motion", *click(opposite)[1:])
                point = click(facing)
                frames, states, choices = self.observe(
                    [point] + [("down", key) for key in keys],
                    {1: [cursor], 3: [("quit",)]}, phase=.37, initial_aim=point[1:])
                self.assertIsNotNone(states[0]["attack"])
                for state, choice in zip(states, choices):
                    self.assertEqual((state["facing"], state["display_facing"]), (facing, facing))
                    self.assertEqual(state["angle"], states[0]["angle"])
                    self.assertTrue(choice["drawn"])
                self.assertEqual(frames[-1]["aim_angle"], states[0]["angle"])
                self.assertNotEqual(states[-1]["target"], states[0]["target"])
                self.assertEqual(states[-1]["phase"], .37)
                self.assertEqual((frames[-1]["x"], frames[-1]["y"]), (480, 180))

    def test_eight_facings_near_wall_stay_still_then_resume_walking(self):
        vectors = dict(DIRECTIONS)
        for facing, _ in DIRECTIONS:
            with self.subTest(facing=facing):
                point = click(facing, (480, 316))
                frames, states, choices = self.observe(
                    [point, ("down", main.p.SDLK_w)],
                    {1: [("up", main.p.SDLK_w), ("down", main.p.SDLK_s)],
                     2: [("up", main.p.SDLK_s)], 3: [("down", main.p.SDLK_d)],
                     43: [("quit",)]}, 44, phase=.23, wall=True, initial_aim=point[1:])
                self.assertTrue(all(choice["walk"] == 0 for choice in choices[:4]))
                self.assertTrue(all(choice["drawn"] for choice in choices[:4]))
                self.assertTrue(all(state["phase"] == .23 for state in states[:4]))
                signed_distance, previous = 0.0, (480, 316)
                for frame, state in zip(frames, states):
                    current = (frame["x"], frame["y"])
                    dx, dy = current[0] - previous[0], current[1] - previous[1]
                    fx, fy = vectors[state["display_facing"]]
                    direction = -1 if dx * fx + dy * fy < 0 else 1
                    signed_distance += direction * math.dist(previous, current)
                    self.assertAlmostEqual(state["phase"], (.23 + signed_distance / 64) % 1)
                    previous = current
                self.assertIsNone(states[-1]["attack"])
                pose_count = 8 if facing == "front_right" else 12
                self.assertEqual({choice["attack_index"] for choice in choices
                                  if choice["attack_index"] is not None}, set(range(pose_count)))
                self.assertFalse(choices[-1]["drawn"])
                self.assertGreater(choices[-1]["walk"], 0)

    def test_eight_facings_focus_pause_and_r_clear_input_attack_and_phase(self):
        for facing, _ in DIRECTIONS:
            with self.subTest(facing=facing):
                point = click(facing)
                frames, states, choices = self.observe(
                    [point, ("down", main.p.SDLK_d)],
                    {1: [("lost",), ("gained",)], 2: [("down", main.p.SDLK_d)],
                     3: [("down", main.p.SDLK_r)], 4: [("quit",)]}, phase=.3, initial_aim=point[1:])
                self.assertEqual(states[0]["facing"], facing)
                self.assertTrue(choices[0]["drawn"])
                self.assertEqual(choices[1]["walk"], 0)
                self.assertEqual(states[0]["elapsed"], states[1]["elapsed"])
                self.assertEqual(states[0]["phase"], states[1]["phase"])
                self.assertEqual(states[2]["phase"], .3)
                self.assertEqual((frames[3]["x"], frames[3]["y"], states[3]["phase"]), (480, 180, 0))
                self.assertIsNone(states[3]["attack"])
                self.assertFalse(choices[3]["drawn"])

    def test_new_direction_hold_duplicate_click_and_fresh_press_after_recovery(self):
        point = click("back_left")
        _, states, choices = self.observe(
            [point], {37: [point], 39: [("release", *point[1:]), point], 41: [("quit",)]}, 42,
            initial_aim=point[1:])
        first = states[0]["attack"]
        self.assertIsNotNone(first)
        self.assertTrue(all(state["attack"] is None for state in states[36:39]))
        self.assertIsNotNone(states[39]["attack"])
        self.assertIsNot(states[39]["attack"], first)
        self.assertEqual(states[39]["facing"], "back_left")
        self.assertTrue(choices[39]["drawn"])


if __name__ == "__main__":
    unittest.main()
