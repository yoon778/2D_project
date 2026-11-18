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
from combat import CombatWorld, STUN_DURATION, Zombie
from combat_visual import CombatVisual, METADATA_PATH
from core import Player, Wall, wall_blocks
from delivery import DeliveryWorld, NeighborhoodWall
from flashlight import Flashlight, LightField
import test_visual_input_r1a as input_fixture


FR_BOUNDARIES = (0, .045, .09, .135, .18, .225, .27, .32, .37, .425, .48, .54, .6)


def combat_metadata():
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    metadata["zombie"] = json.loads(combat_visual.ZOMBIE_METADATA_PATH.read_text(encoding="utf-8"))
    metadata["zombie_attack"] = json.loads(combat_visual.ZOMBIE_ATTACK_METADATA_PATH.read_text(encoding="utf-8"))
    return metadata


def zombie_body_point(visual, zombie, foot, target_row=35):
    frame = visual._zombie_frame(zombie)
    scale = visual.metadata["zombie"]["scale"] * visual.display_scale
    row = min(map(int, frame["opaque_rows"]), key=lambda value: abs(value - target_row))
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
                self.assertAlmostEqual(world.zombie.stun_remaining, STUN_DURATION - (boundary - .18))
            self.assertFalse(world.start_attack())
            previous = boundary
        world.update(.6 - previous)
        self.assertIsNone(world.attack)
        self.assertEqual((world.zombie.hp, world.player_hp), (4, 3))
        self.assertAlmostEqual(world.zombie.stun_remaining, STUN_DURATION - .42)
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

    def test_diagonal_light_clips_different_rows_at_the_same_x_for_drawing_and_picking(self):
        world = CombatWorld()
        world.walls = []
        world.zombie.x, world.zombie.y = 489, 260
        beam = Flashlight((200, 100), math.pi / 4, [])
        light = LightField((beam,))
        visual = SimpleNamespace(zombie_contains=Mock(return_value=True))
        camera, shake = (120, 40), (3, -2)

        def project(x, y):
            sx, sy = main.world_to_screen(x, y, camera)
            return sx + shake[0], sy + shake[1]

        rows = main.light_source_rows(beam, project)
        x, y = map(round, project(489, 260))
        near_row = main.WINDOW_HEIGHT - 1 - y
        far_row = near_row - 42
        renderer = main.Renderer.__new__(main.Renderer)
        renderer.project = project
        renderer.delivery = None
        renderer.light_sources = ((beam, rows),)
        renderer._open_light_rows = {}
        spans = renderer.actor_light_spans((489, 260), x, y, wall_shadow_at_feet=True)
        self.assertTrue(any(left <= x < right for left, right in spans(near_row)))
        self.assertFalse(any(left <= x < right for left, right in spans(far_row)))
        self.assertEqual(main.mouse_target(world, visual, x, near_row, light, camera, shake), (489, 260))
        self.assertEqual(main.mouse_target(world, visual, x, far_row, light, camera, shake),
                         main.sdl_to_world(x, far_row, camera))

    def test_shop_wall_keeps_lit_head_drawable_and_pickable_before_the_wall(self):
        world = DeliveryWorld()
        self.assertTrue(world.select_playable_contract(4))
        world.skip_route_sequence()
        world.parcel = "carrying"
        self.visual.display_scale = main.DELIVERY_CHARACTER_SCALE
        renderer = main.Renderer.__new__(main.Renderer)
        renderer.delivery = world
        renderer.shake_offset = (0, 0)
        renderer.combat_visual = self.visual
        renderer.glow_source = None
        renderer._open_light_rows = {}
        renderer.draw_lit_region = Mock()
        renderer.draw_zombie_markers = Mock()

        for origin, position, visible in (
            ((1980, 910), (1980, 1042), True),
            ((1980, 980), (1980, 1240), False),
        ):
            with self.subTest(position=position):
                world.player.x, world.player.y = origin
                renderer.follow(world.player)
                beam = Flashlight(origin, math.pi / 2, world.walls, world.world_size)
                renderer.light_sources = ((beam, main.light_source_rows(beam, renderer.project)),)
                self.assertTrue(Flashlight(origin, math.pi / 2, (), world.world_size).contains(position))
                self.assertEqual(beam.contains(position), visible)

                zombie = Zombie(*position, aim_angle=-math.pi / 2)
                world.zombies[:] = [zombie]
                self.visual.update_zombie(zombie, 0, 0)
                foot = renderer.project(*position)
                mx, sy = map(math.floor, zombie_body_point(self.visual, zombie, foot, target_row=16))
                self.assertTrue(self.visual.zombie_contains(zombie, *foot, mx, sy))
                my = main.WINDOW_HEIGHT - 1 - sy

                renderer.draw_lit_region.reset_mock()
                renderer.draw_lit_zombie(zombie, world, None)
                rendered = any(
                    left <= mx < right for call in renderer.draw_lit_region.call_args_list
                    for left, right in call.kwargs["row_spans"](my))
                self.assertEqual(rendered, visible)
                fallback = main.sdl_to_world(mx, my, renderer.camera)
                self.assertEqual(main.mouse_target(world, self.visual, mx, my, LightField((beam,)), renderer.camera),
                                 position if visible else fallback)

    def test_head_can_be_picked_in_a_horizontal_beam_and_stays_hidden_by_wall(self):
        world = CombatWorld()
        world.zombie.x, world.zombie.y = 300, 300
        visual = SimpleNamespace(zombie_contains=Mock(return_value=True))
        x, foot_y = map(round, main.world_to_screen(300, 300))
        head_row = main.WINDOW_HEIGHT - 1 - (foot_y + 70)
        world.walls = []
        light = LightField((Flashlight((200, 300), 0, world.walls),))
        self.assertEqual(main.mouse_target(world, visual, x, head_row, light), (300, 300))
        world.walls = [Wall(245, 286, 12, 28)]
        light = LightField((Flashlight((200, 300), 0, world.walls),))
        self.assertEqual(main.mouse_target(world, visual, x, head_row, light), main.sdl_to_world(x, head_row))

    def test_only_buildings_over_the_courier_are_hidden(self):
        camera = (150, 100)
        for texture in ("west-house", "east-house", "shop", "workshop", "fence", "parked-car", "bus-stop"):
            with self.subTest(texture=texture):
                wall = NeighborhoodWall(100, 300, 140, 190, texture, oblique=texture.endswith("house"))
                hidden = main.building_covers_player(wall, Player(170, 520), camera)
                self.assertEqual(hidden, texture in {"west-house", "east-house", "shop", "workshop"})
                for position in ((170, 280), (255, 520), (170, 700)):
                    self.assertFalse(main.building_covers_player(wall, Player(*position), camera))
        house = NeighborhoodWall(100, 300, 140, 190, "west-house", oblique=True)
        self.assertFalse(main.building_covers_player(house, Player(104, 520), camera))

    def test_hidden_building_stops_screen_pick_occlusion_but_still_blocks_light(self):
        world = CombatWorld()
        world.zombie.x, world.zombie.y = 300, 320
        wall = NeighborhoodWall(245, 200, 110, 60, "workshop")
        world.walls = [wall]
        visual = SimpleNamespace(zombie_contains=Mock(return_value=True))
        x, foot_y = map(round, main.world_to_screen(300, 320))
        head_row = main.WINDOW_HEIGHT - 1 - (foot_y + 50)
        fallback = main.sdl_to_world(x, head_row)
        world.player = Player(230, 285)
        self.assertEqual(main.mouse_target(world, visual, x, head_row), fallback)
        world.player.x = 300
        self.assertEqual(main.mouse_target(world, visual, x, head_row), (300, 320))
        renderer = main.Renderer.__new__(main.Renderer)
        renderer.camera = (0.0, 0.0)
        renderer.delivery = None
        renderer._building_fades = {}
        renderer.update_building_fades(world.player, world.walls, main.BUILDING_FADE_OUT / 2)
        self.assertEqual(main.mouse_target(world, visual, x, head_row, building_opacity=renderer.building_opacity),
                         fallback)
        renderer.update_building_fades(world.player, world.walls, main.BUILDING_FADE_OUT / 2)
        self.assertEqual(main.mouse_target(world, visual, x, head_row, building_opacity=renderer.building_opacity),
                         (300, 320))
        light = LightField((Flashlight((300, 150), math.pi / 2, world.walls),))
        self.assertEqual(main.mouse_target(world, visual, x, head_row, light,
                                           building_opacity=renderer.building_opacity), fallback)
        self.assertEqual(world.walls, [wall])

    def test_light_caches_refresh_for_wall_changes_at_the_same_pose(self):
        renderer = main.Renderer.__new__(main.Renderer)
        renderer.camera = (0.0, 0.0)
        renderer.shake_offset = (0, 0)
        renderer.light = renderer._light_pose = None
        walls = []
        player, target = Player(200, 200), (280, 200)
        world = SimpleNamespace(world_size=(1000, 1000), walls=walls, streetlights=((200, 200),))
        renderer.delivery = renderer.combat = world
        renderer.reset_streetlights()

        def visibility(sources):
            return tuple(any(left <= target[0] < right for left, right in source.spans_at(target[1]))
                         for source in (*sources.lights, renderer.nearby_light))

        clear = renderer.prepare_light(player, walls, target)
        self.assertEqual(visibility(clear), (True, True, True))
        self.assertIs(renderer.prepare_light(player, walls, target), clear)
        barrier = Wall(235, 188, 8, 24)
        walls.append(barrier)
        blocked = renderer.prepare_light(player, walls, target)
        self.assertIsNot(blocked, clear)
        self.assertEqual(visibility(blocked), (False, False, False))

        barrier.y = 245
        moved = renderer.prepare_light(player, walls, target)
        self.assertIsNot(moved, blocked)
        self.assertEqual(visibility(moved), (True, True, True))
        barrier.y = 188
        self.assertEqual(visibility(renderer.prepare_light(player, walls, target)), (False, False, False))
        walls.remove(barrier)
        self.assertEqual(visibility(renderer.prepare_light(player, walls, target)), (True, True, True))

    def test_wall_planes_keep_hit_width_and_apply_the_lifted_beam_mask_only_to_the_roof(self):
        renderer = main.Renderer.__new__(main.Renderer)
        renderer.project = lambda x, y: (x, y)
        renderer.ground_scale = lambda: main.GROUND_SCALE_Y
        renderer.neighborhood_walls = {
            "east-house": SimpleNamespace(h=96),
            "east-house-side": SimpleNamespace(h=96),
        }
        renderer.draw_wall_plane = Mock()
        wall = NeighborhoodWall(330, 350, 100, 60, "east-house", oblique=True)
        front, side, roof = main.house_planes(wall, wall.x, wall.y)
        outline = tuple((point, wall) for point in ((345, 350), (385, 350), (430, 362), (430, 392)))
        mask = ((300, 300), (435, 315), (450, 395))
        renderer.wall(wall, (outline,), mask)

        lit = [draw for draw in renderer.draw_wall_plane.call_args_list if draw.args[4] != (0, 0, 0)]
        for plane, expected in ((front, (.15, 0, .55, 1)), (side, (.2, 0, .7, 1))):
            face, = [draw for draw in lit if draw.args[1] == plane]
            self.assertEqual(face.args[5], expected)
            self.assertIsNone(face.kwargs.get("mask"))
        roof_draws = [draw for draw in lit if draw.args[1] == roof]
        self.assertEqual(len(roof_draws), 2)
        for draw in roof_draws:
            self.assertEqual(tuple(draw.kwargs["mask"]), tuple((x, y + wall.height) for x, y in mask))

    def test_building_fade_reverses_from_current_opacity_and_resets(self):
        renderer = main.Renderer.__new__(main.Renderer)
        renderer.camera = (150, 100)
        renderer.delivery = None
        renderer._building_fades = {}
        wall = NeighborhoodWall(100, 300, 140, 190, "east-house", oblique=True)
        fence = NeighborhoodWall(100, 300, 140, 190, "fence")
        walls = [wall, fence]
        behind, side = Player(170, 520), Player(255, 520)
        self.assertEqual(renderer.building_opacity(wall), 1)
        for _ in range(8):
            renderer.update_building_fades(behind, walls, .01)
        self.assertAlmostEqual(renderer.building_opacity(wall), .5)
        self.assertEqual(renderer.building_opacity(fence), 1)
        renderer.update_building_fades(side, walls, .02)
        self.assertAlmostEqual(renderer.building_opacity(wall), .6)
        for _ in range(16):
            renderer.update_building_fades(behind, walls, .01)
        self.assertEqual(renderer.building_opacity(wall), 0)
        for _ in range(20):
            renderer.update_building_fades(side, walls, .01)
        self.assertEqual(renderer.building_opacity(wall), 1)
        renderer.update_building_fades(behind, walls, .08)
        renderer.reset_building_fades()
        self.assertEqual(renderer.building_opacity(wall), 1)

    def test_shelter_cutaway_reveals_indoor_zombie_without_removing_light_blocker(self):
        world = DeliveryWorld()
        self.assertTrue(world.select_playable_contract(3))
        room = world.contract.layout.interior
        zombie = Zombie(1080, 690)
        world.zombies = [zombie]
        visual = SimpleNamespace(zombie_contains=Mock(return_value=True))
        renderer = main.Renderer.__new__(main.Renderer)
        renderer.camera = (0, 0)
        renderer.delivery = world
        renderer._building_fades = {}
        renderer.reset_building_fades()
        front = next(wall for wall in world.walls if getattr(wall, "texture", None) == "interior-wall"
                     and wall.y == room.y and wall.x == room.door_bounds[1])

        cursor_x, foot_y = main.world_to_screen(zombie.x, zombie.y)
        cursor_y = main.WINDOW_HEIGHT - 1 - (foot_y + 30)
        world.player = Player(1000, 525)
        target = main.mouse_target(world, visual, cursor_x, cursor_y, building_opacity=renderer.building_opacity)
        self.assertEqual(target, main.sdl_to_world(cursor_x, cursor_y))

        world.player.y = 590
        renderer.update_building_fades(world.player, world.walls, main.BUILDING_FADE_OUT)
        self.assertEqual(renderer._roof_opacity, 0)
        self.assertEqual(renderer.building_opacity(front), 0)
        self.assertEqual(main.mouse_target(world, visual, cursor_x, cursor_y, building_opacity=renderer.building_opacity),
                         (zombie.x, zombie.y))
        self.assertIn(front, renderer.light_walls(world.walls))
        self.assertTrue(wall_blocks((1080, 520), (1080, 630), front))

        world.player.y = 525
        renderer.update_building_fades(world.player, world.walls, main.BUILDING_FADE_IN)
        self.assertEqual(renderer._roof_opacity, 1)
        self.assertEqual(renderer.building_opacity(front), 1)

    def test_building_fade_multiplies_existing_vertex_alpha(self):
        renderer = main.Renderer.__new__(main.Renderer)
        with (patch.object(main.p, "renderer", object(), create=True),
              patch.object(main.p, "SDL_RenderGeometry", return_value=0) as geometry):
            renderer.draw_wall_plane(None, main.quad(100, 100, 30, 20), 0, 1, (70, 85, 95),
                                     alpha=(255, 191, 63, 0), opacity=.5)
        vertices = geometry.call_args.args[2]
        self.assertEqual([vertex.color.a for vertex in vertices], [128, 96, 32, 0])

    def test_zombie_stun_and_dead_states_use_separate_authored_cells(self):
        zombie = CombatWorld().zombie
        zombie.aim_angle = -math.pi / 4
        atlas_height = self.visual.metadata["zombie"]["canvas_size"][1]
        for hp, stun, x, row in ((5, 0, 80, 0), (4, STUN_DURATION, 80, 9), (0, .4, 0, 13)):
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
    def observe(self, initial, after_draw, maximum_draws=6, setup=None):
        states = []
        original = main.Renderer.draw
        create_world = main.CombatWorld

        def make_world():
            world = create_world()
            if setup:
                setup(world)
            return world

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
                           "target": target, "hp": world.player_hp, "zombie_hp": world.zombie.hp,
                           "shake": renderer.shake_offset, "cursor": renderer.cursor})

        with (patch.object(main.Renderer, "draw", draw),
              patch.object(main, "CombatWorld", side_effect=make_world)):
            frames = input_fixture.DummyInputTests._run_events(
                self, initial, after_draw, maximum_draws=maximum_draws)
        return frames, states

    def test_body_click_without_motion_picks_zombie_and_starts_fr_attack(self):
        visual = CombatVisual.__new__(CombatVisual)
        visual.metadata = combat_metadata()
        visual.reset_zombie_animation()
        world = CombatWorld()
        foot = main.world_to_screen(world.zombie.x, world.zombie.y)
        x, y = zombie_body_point(visual, world.zombie, foot, target_row=63)
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
        _, states = self.observe([("motion", 640, 269)],
                                 {25: [("click", 640, 269)], 26: [("quit",)]}, 27)
        self.assertIsNotNone(states[25]["attack"])
        self.assertEqual(states[25]["facing"], "back")

    def test_flick_and_click_hits_in_the_previously_visible_body_direction(self):
        def setup(world):
            world.zombie.x, world.zombie.y = 540, 180

        _, states = self.observe([], {
            1: [("motion", 160, 521), ("click", 160, 521)],
            16: [("quit",)],
        }, 17, setup)
        self.assertEqual(states[1]["target"], (0, 180))
        self.assertEqual(states[1]["cursor"], (160, 521))
        self.assertEqual(states[1]["facing"], states[0]["display_facing"])
        self.assertTrue(all(state["angle"] == 0 for state in states[1:]))
        self.assertEqual(states[10]["zombie_hp"], 5)
        self.assertEqual(states[11]["zombie_hp"], 4)
        self.assertEqual(states[11]["shake"], (3, 0))

    def test_miss_stays_steady_and_player_damage_shakes(self):
        _, miss = self.observe([("click", 760, 569)], {24: [("quit",)]}, 25)
        self.assertTrue(all(state["shake"] == (0, 0) for state in miss))
        self.assertEqual(miss[-1]["zombie_hp"], 5)

        def setup(world):
            world.zombie.x, world.zombie.y = 508, 180

        _, damage = self.observe([], {26: [("quit",)]}, 27, setup)
        first_hit = next(i for i, state in enumerate(damage) if state["hp"] == 2)
        self.assertEqual(damage[first_hit - 1]["shake"], (0, 0))
        self.assertEqual(damage[first_hit]["shake"], (4, 0))
        self.assertEqual(damage[-1]["shake"], (0, 0))

    def test_attack_keeps_angle_position_and_walk_phase_under_input(self):
        frames, states = self.observe([("click", 760, 569), ("down", main.p.SDLK_d)],
                                     {1: [("motion", 160, 521)], 3: [("quit",)]})
        self.assertEqual(len(states), 3)
        for i, state in enumerate(states):
            self.assertEqual((frames[i]["x"], frames[i]["y"]), (480, 180))
            self.assertEqual(state["phase"], 0)
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
