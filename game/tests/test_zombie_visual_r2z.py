"""R2-Z distance-driven zombie poses, current-frame picking and SDL queue wiring."""
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
from combat_visual import CombatVisual
import test_visual_input_r1a as input_fixture


FACINGS = (("front", -math.pi / 2), ("front_right", -math.pi / 4),
           ("right", 0), ("back_right", math.pi / 4), ("back", math.pi / 2),
           ("back_left", 3 * math.pi / 4), ("left", math.pi), ("front_left", -3 * math.pi / 4))
HIT_BOUNDS = (0, .06, .14, .26, .4)
ATTACK_BOUNDS = (0, .04, .08, .12, .16, .23, .3, .4, .46, .52, .64, .72, .8)


def zombie_metadata():
    """Test-only atlas with a different opaque row/column for each cell."""
    def frame(col, row):
        x, y = col * 80, row * 80
        return {"clip_topleft": [x, y, 80, 80], "foot_pivot_topleft": [x + 40, y + 72],
                "opaque_rows": {str(10 + row): [[10 + col * 5, 12 + col * 5]]}}
    facings = {}
    for col, (facing, _) in enumerate(FACINGS):
        hits = []
        for index in range(4):
            cell = frame(col, 9 + index)
            cell.update(start=HIT_BOUNDS[index], end=HIT_BOUNDS[index + 1])
            hits.append(cell)
        facings[facing] = {"idle": frame(col, 0), "walk": [frame(col, row) for row in range(1, 9)], "hit": hits}
    return {"image": "fixture-zombie.png", "canvas_size": [640, 1120], "cell_size": [80, 80],
            "scale": 2, "reference_height": 64, "stride_distance": 64,
            "facings": facings, "frames": {"dead": frame(0, 13)}}


def zombie_attack_metadata():
    facings = {}
    for col, (facing, _) in enumerate(FACINGS):
        facings[facing] = [
            {"clip_topleft": [col * 80, row * 80, 80, 80],
             "foot_pivot_topleft": [col * 80 + 40, row * 80 + 72],
             "opaque_rows": {str(50 + row): [[20 + col * 5, 22 + col * 5]]},
             "start": ATTACK_BOUNDS[row], "end": ATTACK_BOUNDS[row + 1]} for row in range(12)]
    return {"image": "fixture-zombie-attack.png", "canvas_size": [640, 960], "cell_size": [80, 80],
            "scale": 2, "reference_height": 64, "facings": facings}


class ZombiePoseTests(unittest.TestCase):
    def setUp(self):
        self.visual = CombatVisual.__new__(CombatVisual)
        self.visual.metadata = {"zombie": zombie_metadata(), "zombie_attack": zombie_attack_metadata()}
        self.visual.images = {"zombie": SimpleNamespace(h=1120, clip_draw=Mock())}
        self.visual.reset_zombie_animation()

    def advance(self, world, dt):
        before = (world.zombie.x, world.zombie.y)
        world.update(dt)
        dx, dy = world.zombie.x - before[0], world.zombie.y - before[1]
        self.visual.update_zombie(world.zombie, dx, dy)
        return math.hypot(dx, dy)

    def test_eight_facings_and_walk_phases_follow_actual_world_distance_then_stop_resume(self):
        for facing, angle in FACINGS:
            with self.subTest(facing=facing):
                self.visual.reset_zombie_animation()
                world = CombatWorld()
                world.walls = []
                world.player.y = 360
                world.zombie.x = world.player.x - 150 * math.cos(angle)
                world.zombie.y = world.player.y - 150 * math.sin(angle)
                travelled = 0.0
                for index in range(8):
                    travelled += self.advance(world, (1 if index == 0 else 8) / 90)
                    motion = self.visual.zombie_locomotion
                    self.assertEqual(motion.facing, facing)
                    self.assertAlmostEqual(motion.phase, travelled / 64)
                    self.assertEqual(self.visual._zombie_frame(world.zombie),
                                     self.visual.metadata["zombie"]["facings"][facing]["walk"][index])
                phase = self.visual.zombie_locomotion.phase
                self.advance(world, 0)
                self.assertEqual(self.visual.zombie_locomotion.phase, phase)
                self.assertEqual(self.visual._zombie_frame(world.zombie),
                                 self.visual.metadata["zombie"]["facings"][facing]["idle"])
                travelled += self.advance(world, 1 / 90)
                self.assertAlmostEqual(self.visual.zombie_locomotion.phase, travelled / 64)

    def test_hit_uses_stun_clock_preserves_phase_restarts_on_rehit_and_ends_in_one_corpse(self):
        world = CombatWorld()
        world.walls = []
        world.player.aim_angle = 0
        world.zombie.x, world.zombie.y = 540, 180
        self.assertTrue(world.start_attack())
        distance = self.advance(world, .18)
        phase = self.visual.zombie_locomotion.phase
        self.assertAlmostEqual(phase, distance / 64)
        self.assertEqual(world.zombie.hp, 4)
        position = (world.zombie.x, world.zombie.y)
        previous = 0.0
        for index, elapsed in enumerate(HIT_BOUNDS[:-1]):
            self.advance(world, elapsed - previous)
            self.assertAlmostEqual(world.zombie.x, position[0] + min(elapsed / .10, 1) * 8)
            self.assertEqual(world.zombie.y, position[1])
            self.assertEqual(self.visual.zombie_locomotion.phase, phase)
            self.assertEqual(self.visual._zombie_frame(world.zombie),
                             self.visual.metadata["zombie"]["facings"]["left"]["hit"][index])
            previous = elapsed
        self.advance(world, .4 - previous)
        self.assertEqual(self.visual._zombie_frame(world.zombie),
                         self.visual.metadata["zombie"]["facings"]["left"]["hit"][-1])
        self.advance(world, STUN_DURATION - .4)
        self.assertEqual(world.zombie.stun_remaining, 0)
        moved = self.advance(world, .02)
        self.assertAlmostEqual(self.visual.zombie_locomotion.phase, phase + moved / 64)
        for hp in (3, 2, 1, 0):
            self.assertTrue(world.start_attack())
            self.advance(world, .18)
            self.assertEqual(world.zombie.hp, hp)
            expected = (self.visual.metadata["zombie"]["facings"]["left"]["hit"][0]
                        if hp else self.visual.metadata["zombie"]["frames"]["dead"])
            self.assertEqual(self.visual._zombie_frame(world.zombie), expected)
            self.advance(world, .42)
        self.assertEqual(world.result, "cleared")
        self.assertFalse(self.visual.zombie_contains(world.zombie, 100, 200, 100, 200))

    def test_every_current_pose_uses_its_own_mask_and_the_same_ground_anchor(self):
        zombie = CombatWorld().zombie
        for col, (facing, angle) in enumerate(FACINGS):
            self.visual.reset_zombie_animation()
            zombie.aim_angle = angle
            self.visual.update_zombie(zombie, 0, 0)
            poses = self.visual.metadata["zombie"]["facings"][facing]
            cases = [(0, 0, poses["idle"])]
            cases += [(index + 1, 0, frame) for index, frame in enumerate(poses["walk"])]
            cases += [(0, STUN_DURATION - frame["start"], frame) for frame in poses["hit"]]
            for walk, stun, frame in cases:
                zombie.stun_remaining = stun
                motion = self.visual.zombie_locomotion
                motion.phase, motion.moving = ((walk - 1 + .1) / 8 if walk else .3), bool(walk)
                self.assertIs(self.visual._zombie_frame(zombie), frame)
                self.visual.draw_zombie(zombie, 100, 200)
                x, y, _, _ = frame["clip_topleft"]
                self.visual.images["zombie"].clip_draw.assert_called_with(
                    x, 1120 - y - 80, 80, 80, 100.0, 264.0, 160.0, 160.0)
                row = int(next(iter(frame["opaque_rows"])))
                start, end = frame["opaque_rows"][str(row)][0]
                screen = (20 + (start + .5) * 2, 184 + (80 - row - .5) * 2)
                self.assertTrue(self.visual.zombie_contains(zombie, 100, 200, *screen))
                self.assertFalse(self.visual.zombie_contains(zombie, 100, 200, screen[0] + (end - start + 2) * 2, screen[1]))
                self.assertFalse(self.visual.zombie_contains(zombie, 100, 200, 20, 184))
            zombie.stun_remaining = 0
        zombie.hp = 0
        self.visual.draw_zombie(zombie, 100, 200)
        self.visual.images["zombie"].clip_draw.assert_called_with(0, 0, 80, 80, 100.0, 264.0, 160.0, 160.0)
        self.assertFalse(self.visual.zombie_contains(zombie, 100, 200, 41, 297))

    def test_overlay_replaces_only_legacy_texture_path_and_reset_never_reloads(self):
        metadata = json.loads(combat_visual.METADATA_PATH.read_text(encoding="utf-8"))
        legacy = metadata["zombie"]["image"]
        source = zombie_metadata()
        attack_source = zombie_attack_metadata()
        overlay = SimpleNamespace(parent=Path("new-zombie"), read_text=Mock(return_value=json.dumps(source)))
        attack_overlay = SimpleNamespace(parent=Path("new-zombie-attack"), read_text=Mock(return_value=json.dumps(attack_source)))
        expected = dict(metadata, zombie=source, zombie_attack=attack_source)
        images = [SimpleNamespace(w=s["canvas_size"][0], h=s["canvas_size"][1], texture=object(), clip_draw=Mock())
                  for s in expected.values()]
        with (patch.object(combat_visual, "ZOMBIE_METADATA_PATH", overlay, create=True),
              patch.object(combat_visual, "ZOMBIE_ATTACK_METADATA_PATH", attack_overlay),
              patch.object(combat_visual.p, "load_image", side_effect=images) as load,
              patch.object(combat_visual.p, "SDL_SetTextureScaleMode", return_value=0)):
            visual = CombatVisual()
            self.assertEqual(visual.metadata, expected)
            self.assertEqual(load.call_count, len(expected))
            paths = [call.args[0] for call in load.call_args_list]
            self.assertIn(str(overlay.parent / source["image"]), paths)
            self.assertIn(str(attack_overlay.parent / attack_source["image"]), paths)
            self.assertFalse(any(Path(path).name == legacy for path in paths))
            for key in metadata.keys() - {"zombie"}:
                self.assertEqual(visual.metadata[key], metadata[key])
            visual.zombie_locomotion.phase = .7
            visual.reset_zombie_animation()
            self.assertEqual((visual.zombie_locomotion.phase, visual.zombie_locomotion.moving), (0, False))
            self.assertEqual(load.call_count, len(expected))
            visual.close()
            self.assertEqual(visual.images, {})


class ZombieQueueTests(unittest.TestCase):
    def observe(self, initial, after_draw, maximum_draws=6, setup=None):
        states = []
        original_draw, original_world = main.Renderer.draw, main.CombatWorld

        def make_world():
            world = original_world()
            if setup:
                setup(world)
            return world

        def draw(renderer, player, walls, target, focused=True):
            original_draw(renderer, player, walls, target, focused)
            zombie, visual = renderer.combat.zombie, renderer.combat_visual
            states.append({"position": (zombie.x, zombie.y), "phase": visual.zombie_locomotion.phase,
                           "moving": visual.zombie_locomotion.moving, "stun": zombie.stun_remaining,
                           "source": visual._zombie_pose(zombie)[0], "hp": renderer.combat.player_hp,
                           "zombie_hp": zombie.hp,
                           "attack_elapsed": zombie.attack.elapsed if zombie.attack else None,
                           "attack_facing": zombie.attack.facing if zombie.attack else None,
                           "attack_done": zombie.attack._hit_done if zombie.attack else None,
                           "row": visual._zombie_frame(zombie)["clip_topleft"][1] // 80})

        with (patch.object(main, "CombatWorld", side_effect=make_world), patch.object(main.Renderer, "draw", draw)):
            input_fixture.DummyInputTests._run_events(self, initial, after_draw, maximum_draws)
        return states

    def test_real_chase_focus_pause_and_r_reset_use_distance_without_texture_reload(self):
        original_load = main.p.load_image
        with patch.object(main.p, "load_image", wraps=original_load) as load:
            states = self.observe([], {1: [("lost",), ("gained",)], 3: [("down", main.p.SDLK_r)], 4: [("quit",)]})
        self.assertEqual(load.call_count, 49)
        self.assertEqual(sum(call.args == (str(main.TRASH_CAN_PATH),) for call in load.call_args_list), 1)
        self.assertAlmostEqual(states[0]["phase"], 1.5 / 64)
        self.assertEqual(states[0]["phase"], states[1]["phase"])
        self.assertEqual(states[0]["position"], states[1]["position"])
        self.assertFalse(states[1]["moving"])
        self.assertAlmostEqual(states[2]["phase"], 3 / 64)
        self.assertAlmostEqual(states[3]["phase"], 1.5 / 64)
        self.assertEqual(states[3]["position"], states[0]["position"])

    def test_real_wall_stop_preserves_phase_and_selects_idle(self):
        def setup(world):
            world.player.x, world.player.y = 300, 360
            world.zombie.x, world.zombie.y = 650, 360
        states = self.observe([], {20: [("quit",)]}, 21, setup)
        self.assertEqual(states[-1]["position"], (634, 360))
        self.assertAlmostEqual(states[-1]["phase"], 16 / 64)
        self.assertFalse(states[-1]["moving"])
        self.assertEqual(states[-1]["row"], 0)

    def test_real_attack_selects_all_four_hit_steps_then_resumes_chase(self):
        def setup(world):
            world.zombie.x, world.zombie.y = 520, 140
        states = self.observe([("click", 680, 545)], {60: [("quit",)]}, 61, setup)
        hit = [state for state in states if state["stun"] > 0]
        self.assertEqual({state["row"] for state in hit}, {9, 10, 11, 12})
        recoil_seen = 8 * (hit[0]["stun"] - (STUN_DURATION - 0.10)) / 0.10
        self.assertAlmostEqual(math.dist(hit[-1]["position"], hit[0]["position"]), recoil_seen)
        self.assertTrue(all(state["phase"] == hit[0]["phase"] for state in hit))
        self.assertTrue(states[-1]["moving"])
        self.assertGreater(states[-1]["phase"], hit[0]["phase"])


if __name__ == "__main__":
    unittest.main()
