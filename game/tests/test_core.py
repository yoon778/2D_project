import unittest
from math import cos, hypot, pi, radians, sin

from game.core import Game, Rect, circle_overlaps_rect, find_path


class GameTests(unittest.TestCase):
    def make_game(self):
        game = Game()
        game.start()
        return game

    def combat_scene(self):
        game = self.make_game()
        game.player.x, game.player.y = 200.0, 200.0
        game.zombie.x, game.zombie.y = 260.0, 200.0
        game.walls = []
        return game

    def test_diagonal_movement_has_same_speed_as_straight_movement(self):
        game = self.make_game()
        game.zombie.hp = 0
        game.step(0.2, 1, 1, False, 600, 160)
        self.assertAlmostEqual(hypot(game.player.x - 160, game.player.y - 160), 18.0)
        game.restart()
        game.zombie.hp = 0
        game.step(0.2, 1, 0, False, 600, 160)
        self.assertAlmostEqual(game.player.x - 160, 18.0)

    def test_player_does_not_cross_wall_or_map_boundary(self):
        game = self.make_game()
        game.zombie.hp = 0
        game.player.x, game.player.y = 450.0, 350.0
        game.step(1.0, 1, 0, True, 900, 350)
        self.assertLessEqual(game.player.x + game.player.radius, 500.0)
        self.assertGreater(game.player.x, 450.0)
        game.player.x, game.player.y = 30.0, 100.0
        game.step(1.0, -1, 0, True, 0, 100)
        self.assertEqual(game.player.x, game.player.radius)

    def test_attack_hits_once_and_ignores_clicks_during_recovery(self):
        game = self.combat_scene()
        self.assertTrue(game.swing())
        self.assertFalse(game.swing())
        self.assertEqual([event.kind for event in game.pop_events()], ["attack"])
        game.step(0.4, 0, 0, False, 600, 200)
        self.assertEqual(game.zombie.hp, 4)
        self.assertEqual([event.kind for event in game.pop_events()].count("hit"), 1)
        self.assertFalse(game.swing())
        game.step(0.21, 0, 0, False, 600, 200)
        self.assertIsNone(game.attack_elapsed)
        self.assertTrue(game.swing())

    def test_long_vertical_movement_stays_clear_of_hud_bands(self):
        game = self.make_game()
        game.zombie.hp = 0
        game.step(8.0, 0, -1, True, 160, 0)
        self.assertAlmostEqual(game.player.y - game.player.radius, 100.0)
        game.step(8.0, 0, 1, True, 160, 720)
        self.assertAlmostEqual(game.player.y + game.player.radius, 636.0)
        self.assertEqual(game.player.x, 160.0)

    def test_wall_blocks_attack_and_direct_zombie_approach(self):
        game = self.combat_scene()
        game.walls = [Rect(226.0, 160.0, 12.0, 80.0)]
        game.step(0.1, 0, 0, False, 600, 200)
        self.assertEqual((game.zombie.x, game.zombie.y), (260.0, 200.0))
        self.assertEqual(game.zombie.state, "idle")
        game.swing()
        game.step(0.7, 0, 0, False, 600, 200)
        self.assertEqual(game.zombie.hp, 5)
        self.assertFalse(circle_overlaps_rect(game.zombie.x, game.zombie.y,
                                             game.zombie.radius, game.walls[0]))
        self.assertEqual(game.zombie.state, "investigate")
        self.assertNotIn("hit", [event.kind for event in game.pop_events()])

    def test_slow_frame_still_resolves_exactly_one_impact(self):
        game = self.combat_scene()
        game.swing()
        game.step(0.7, 0, 0, False, 600, 200)
        self.assertEqual(game.zombie.hp, 4)
        self.assertIsNone(game.attack_elapsed)
        self.assertEqual([event.kind for event in game.pop_events()].count("hit"), 1)

    def test_killing_hit_precedes_contact_damage_in_same_tick(self):
        game = self.combat_scene()
        game.zombie.x, game.zombie.y = game.player.x, game.player.y
        game.zombie.hp = 1
        game.swing()
        game.attack_elapsed = 0.17
        game.step(0.02, 0, 0, False, 600, 200)
        self.assertEqual(game.zombie.hp, 0)
        self.assertEqual(game.zombie.state, "dead")
        self.assertEqual(game.player.hp, 3)
        self.assertNotIn("hurt", [event.kind for event in game.pop_events()])

    def test_hit_stuns_in_place_then_zombie_resumes_moving(self):
        game = self.combat_scene()
        game.swing()
        game.attack_elapsed = 0.17
        before = (game.zombie.x, game.zombie.y)
        game.step(0.01, 0, 0, False, 600, 200)
        self.assertEqual(game.zombie.hp, 4)
        self.assertEqual((game.zombie.x, game.zombie.y), before)
        self.assertAlmostEqual(game.zombie.stun, 0.4)
        self.assertEqual(game.zombie.state, "stunned")
        game.step(0.2, 0, 0, False, 600, 200)
        self.assertEqual((game.zombie.x, game.zombie.y), before)
        self.assertEqual(game.zombie.state, "stunned")
        game.step(0.21, 0, 0, False, 600, 200)
        self.assertLess(game.zombie.x, before[0])
        self.assertEqual(game.zombie.state, "chase")

    def test_surviving_hit_blocks_contact_damage_until_stun_ends(self):
        game = self.combat_scene()
        game.zombie.x, game.zombie.y = game.player.x, game.player.y
        game.zombie.angle = 1.2
        game.swing()
        game.attack_elapsed = 0.17
        game.step(0.01, 0, 0, False, 600, 200)
        self.assertEqual(game.zombie.hp, 4)
        self.assertEqual(game.player.hp, 3)
        self.assertEqual(game.zombie_hit_stun, 0.4)
        self.assertAlmostEqual(game.zombie.stun, game.zombie_hit_stun)
        self.assertEqual(game.zombie.angle, 1.2)
        game.step(0.39, 0, 0, False, 200, 600)
        self.assertEqual(game.player.hp, 3)
        self.assertEqual(game.zombie.angle, 1.2)
        self.assertEqual(game.zombie.state, "stunned")
        self.assertNotIn("hurt", [event.kind for event in game.pop_events()])
        game.step(0.03, 0, 0, False, 600, 200)
        self.assertEqual(game.player.hp, 2)
        self.assertIn("hurt", [event.kind for event in game.pop_events()])

    def test_hidden_zombie_walk_and_groan_events_ignore_player_flashlight(self):
        game = self.make_game()
        game.player.x, game.player.y = 450.0, 360.0
        game.zombie.x, game.zombie.y = 850.0, 360.0
        game.swing()
        game.pop_events()
        events = []
        for _ in range(70):
            game.step(1 / 60, 0, 0, False, 100, 360)
            self.assertFalse(game.is_visible(game.zombie.x, game.zombie.y))
            events.extend(game.pop_events())
        kinds = [event.kind for event in events]
        self.assertGreaterEqual(kinds.count("zombie_step"), 2)
        self.assertEqual(kinds.count("zombie_groan"), 1)
        self.assertEqual(game.zombie_target, (450.0, 360.0))
        for event in events:
            if event.kind in ("zombie_step", "zombie_groan"):
                self.assertNotEqual((event.x, event.y), (game.player.x, game.player.y))

    def test_idle_and_blocked_zombies_groan_without_footsteps_or_self_attraction(self):
        game = self.make_game()
        game.step(1.1, 0, 0, False, 100, 160)
        self.assertEqual([event.kind for event in game.pop_events()], ["zombie_groan"])
        self.assertIsNone(game.zombie_target)
        self.assertEqual(game.zombie.state, "idle")
        game.player.x, game.player.y = 600.0, 360.0
        game.zombie.x, game.zombie.y = 400.0, 360.0
        game.walls = [Rect(500.0, 100.0, 20.0, 536.0)]
        game.swing()
        game.pop_events()
        game.step(3.3, 0, 0, False, 900, 360)
        self.assertEqual([event.kind for event in game.pop_events()], ["zombie_groan"])
        self.assertEqual((game.zombie.x, game.zombie.y), (400.0, 360.0))
        self.assertIsNone(game.zombie_target)

    def test_stunned_zombie_has_no_steps_and_death_clears_pending_zombie_sounds(self):
        game = self.combat_scene()
        game.zombie.stun = 1.0
        before = (game.zombie.x, game.zombie.y)
        game.step(0.5, 0, 0, False, 600, 200)
        self.assertEqual((game.zombie.x, game.zombie.y), before)
        self.assertNotIn("zombie_step", [event.kind for event in game.pop_events()])
        game.restart()
        game.step(1.1, 0, 0, False, 600, 160)
        # Leave the emitted groan pending until the killing hit in the next frame.
        game.player.x, game.player.y = 200.0, 200.0
        game.zombie.x, game.zombie.y = 260.0, 200.0
        game.zombie.hp = 1
        game.swing()
        game.attack_elapsed = 0.17
        game.step(0.01, 0, 0, False, 600, 200)
        kinds = [event.kind for event in game.pop_events()]
        self.assertIn("dead", kinds)
        self.assertNotIn("zombie_groan", kinds)
        self.assertNotIn("zombie_step", kinds)
        game.step(8.0, 1, 0, True, 600, 200)
        self.assertFalse(any(event.kind.startswith("zombie_") for event in game.pop_events()))

    def test_zombie_sound_interval_restart_and_long_frame_do_not_queue_bursts(self):
        game = Game()
        game.step(5.0, 0, 0, False, 600, 160)
        self.assertEqual(game.pop_events(), [])
        game.start()
        game.step(0.9, 0, 0, False, 600, 160)
        self.assertEqual(game.pop_events(), [])
        game.step(0.2, 0, 0, False, 600, 160)
        self.assertEqual([event.kind for event in game.pop_events()], ["zombie_groan"])
        game.step(3.0, 0, 0, False, 600, 160)
        self.assertEqual(game.pop_events(), [])
        game.step(0.2, 0, 0, False, 600, 160)
        self.assertEqual([event.kind for event in game.pop_events()], ["zombie_groan"])
        game.step(100.0, 0, 0, False, 600, 160)
        self.assertEqual([event.kind for event in game.pop_events()], ["zombie_groan"])
        game.restart()
        self.assertEqual(game.pop_events(), [])
        game.step(0.9, 0, 0, False, 600, 160)
        self.assertEqual(game.pop_events(), [])
        game.step(0.2, 0, 0, False, 600, 160)
        self.assertEqual([event.kind for event in game.pop_events()], ["zombie_groan"])

    def test_pickup_delivery_require_distance_and_clear_line(self):
        game = self.make_game()
        game.player.x = 205.0
        game.player.angle = pi
        game.walls = [Rect(180.0, 120.0, 5.0, 80.0)]
        self.assertIsNone(game.interact())
        game.walls = []
        self.assertEqual(game.interact(), "pickup")
        self.assertTrue(game.carrying)
        self.assertIsNone(game.interact())
        game.player.x, game.player.y = game.destination
        self.assertEqual(game.interact(), "delivered")
        self.assertEqual(game.state, "won")
        time_at_win = game.time
        game.step(1.0, 1, 0, True, 0, 0)
        self.assertEqual(game.time, time_at_win)

    def test_flashlight_visibility_tracks_facing_in_every_direction(self):
        game = self.make_game()
        game.walls = []
        game.player.x, game.player.y = 600.0, 350.0
        self.assertTrue(game.is_visible(600.0, 350.0))
        for angle in (0.0, pi / 2, pi, -pi / 2, pi * 1.9):
            with self.subTest(angle=angle):
                game.player.angle = angle
                self.assertTrue(game.is_visible(600 + cos(angle) * 100,
                                                350 + sin(angle) * 100))
                self.assertFalse(game.is_visible(600 - cos(angle) * 100,
                                                 350 - sin(angle) * 100))

    def test_flashlight_cone_boundary_wrap_and_range(self):
        game = self.make_game()
        game.walls = []
        game.player.x, game.player.y = 600.0, 350.0
        game.player.angle = 0.0
        for degrees, visible in ((40, True), (-40, True), (41, False), (-41, False)):
            angle = radians(degrees)
            self.assertEqual(game.is_visible(600 + cos(angle) * 100,
                                             350 + sin(angle) * 100), visible)
        self.assertTrue(game.is_visible(940.0, 350.0))
        self.assertFalse(game.is_visible(940.01, 350.0))
        game.player.angle = radians(179)
        angle = radians(-179)
        self.assertTrue(game.is_visible(600 + cos(angle) * 100, 350 + sin(angle) * 100))

    def test_attack_does_not_hit_outside_the_narrower_flashlight(self):
        game = self.combat_scene()
        game.zombie.x = game.player.x + cos(radians(45)) * 60
        game.zombie.y = game.player.y + sin(radians(45)) * 60
        game.swing()
        game.step(0.2, 0, 0, False, 600, 200)
        self.assertEqual(game.zombie.hp, 5)
        self.assertNotIn("hit", [event.kind for event in game.pop_events()])

    def test_flashlight_wall_occlusion_and_interaction_use_same_visibility(self):
        game = self.make_game()
        game.player.x, game.player.y = 205.0, 160.0
        game.player.angle = 0.0
        self.assertFalse(game.is_visible(*game.pickup))
        self.assertIsNone(game.interact())
        game.player.angle = pi
        game.walls = [Rect(180.0, 120.0, 5.0, 80.0)]
        self.assertFalse(game.is_visible(*game.pickup))
        self.assertIsNone(game.interact())
        game.walls = []
        self.assertTrue(game.is_visible(*game.pickup))
        self.assertEqual(game.interact(), "pickup")
        game.player.x, game.player.y = game.destination[0] - 45, game.destination[1]
        self.assertFalse(game.is_visible(*game.destination))
        self.assertIsNone(game.interact())
        game.player.angle = 0.0
        self.assertTrue(game.is_visible(*game.destination))
        self.assertEqual(game.interact(), "delivered")

    def test_restart_resets_flashlight_facing_and_own_position_remains_visible(self):
        game = self.make_game()
        game.player.angle = pi
        self.assertFalse(game.is_visible(260.0, 160.0))
        game.restart()
        self.assertEqual(game.player.angle, 0.0)
        self.assertTrue(game.is_visible(260.0, 160.0))
        self.assertFalse(game.is_visible(60.0, 160.0))
        self.assertTrue(game.is_visible(game.player.x, game.player.y))

    def test_zero_health_cannot_deliver_and_failure_freezes_game(self):
        game = self.combat_scene()
        game.zombie.x, game.zombie.y = game.player.x, game.player.y
        game.step(0.1, 0, 0, False, 600, 200)
        self.assertEqual(game.player.hp, 2)
        game.step(0.5, 0, 0, False, 600, 200)
        self.assertEqual(game.player.hp, 2)
        game.step(0.5, 0, 0, False, 600, 200)
        self.assertEqual(game.player.hp, 1)
        game.pop_events()
        game.carrying = True
        game.player.x, game.player.y = game.destination
        game.player.hp = 0
        self.assertIsNone(game.interact())
        self.assertEqual(game.state, "lost")
        self.assertFalse(game.swing())
        game.step(1.0, 1, 0, True, 0, 0)
        self.assertEqual((game.player.x, game.player.y), game.destination)
        self.assertEqual(game.pop_events(), [])

    def test_walking_matches_zombie_and_running_is_one_and_a_half_times_faster(self):
        walking = self.make_game()
        running = self.make_game()
        walking.zombie.hp = running.zombie.hp = 0
        walking.step(1.0, 1, 0, False, 1000, 160)
        running.step(1.0, 1, 0, True, 1000, 160)
        self.assertEqual(walking.walk_speed, walking.zombie_speed)
        self.assertAlmostEqual(walking.player.x - 160.0, 90.0)
        self.assertAlmostEqual(running.player.x - 160.0, 135.0)
        self.assertAlmostEqual(running.stamina, 75.0)

    def test_sprint_exhaustion_recovers_before_it_can_restart(self):
        game = self.make_game()
        game.zombie.hp = 0
        game.walls = []
        game.step(4.0, 1, 0, True, 1200, 160)
        self.assertAlmostEqual(game.stamina, 0.0)
        self.assertTrue(game.exhausted)
        before = game.player.x
        game.step(1.0, 1, 0, True, 1200, 160)
        self.assertAlmostEqual(game.player.x - before, 90.0)
        self.assertAlmostEqual(game.stamina, 20.0)
        self.assertTrue(game.exhausted)
        game.step(0.3, 0, 0, False, 1200, 160)
        self.assertFalse(game.exhausted)
        self.assertAlmostEqual(game.stamina, 26.0)
        before = game.player.x
        game.step(0.2, 1, 0, True, 1200, 160)
        self.assertAlmostEqual(game.player.x - before, 27.0)
        self.assertAlmostEqual(game.stamina, 21.0)

    def test_shift_still_or_blocked_does_not_drain_or_make_footsteps(self):
        game = self.make_game()
        game.zombie.hp = 0
        game.stamina = 40.0
        game.step(0.5, 0, 0, True, 1000, 160)
        self.assertAlmostEqual(game.stamina, 50.0)
        self.assertEqual(game.pop_events(), [])
        game.player.x, game.player.y = 482.0, 350.0
        game.step(0.5, 1, 0, True, 1000, 350)
        self.assertAlmostEqual(game.player.x, 482.0)
        self.assertAlmostEqual(game.stamina, 60.0)
        self.assertEqual(game.pop_events(), [])

    def test_attacking_disables_sprint_and_uses_slow_movement(self):
        game = self.make_game()
        game.zombie.hp = 0
        game.stamina = 50.0
        game.swing()
        game.step(0.2, 1, 0, True, 1000, 160)
        self.assertAlmostEqual(game.player.x - 160.0, 12.0)
        self.assertAlmostEqual(game.stamina, 54.0)
        self.assertEqual(game.player.state, "attack")

    def test_zombie_takes_five_hits_to_die(self):
        game = self.combat_scene()
        self.assertEqual(game.zombie.max_hp, 5)
        for remaining in range(4, -1, -1):
            game.zombie.x, game.zombie.y = 260.0, 200.0
            self.assertTrue(game.swing())
            game.step(0.61, 0, 0, False, 600, 200)
            self.assertEqual(game.zombie.hp, remaining)
        self.assertEqual(game.zombie.state, "dead")

    def test_attack_noise_routes_around_building_to_fixed_sound_position(self):
        game = self.make_game()
        game.player.x, game.player.y = 450.0, 360.0
        game.zombie.x, game.zombie.y = 850.0, 360.0
        game.swing()
        game.step(0.02, 0, 0, False, 100, 360)
        self.assertFalse(game.is_visible(game.zombie.x, game.zombie.y))
        self.assertEqual(game.zombie_target, (450.0, 360.0))
        self.assertEqual(game.zombie.state, "investigate")
        # After the single noise, hide quietly elsewhere. The goal must not follow.
        game.player.x, game.player.y = 100.0, 600.0
        for _ in range(540):
            game.step(1 / 60, 0, 0, False, 100, 360)
            self.assertFalse(circle_overlaps_rect(game.zombie.x, game.zombie.y,
                                                 game.zombie.radius, game.walls[0]))
            if game.zombie.state == "search":
                break
            self.assertEqual(game.zombie_target, (450.0, 360.0))
        self.assertEqual(game.zombie.state, "search")
        self.assertLess(hypot(game.zombie.x - 450, game.zombie.y - 360), 3.0)
        game.step(3.1, 0, 0, False, 100, 360)
        self.assertEqual(game.zombie.state, "idle")
        self.assertIsNone(game.zombie_target)

    def test_noise_radius_and_dead_zombie_reaction(self):
        game = self.make_game()
        game.walls = []
        game.player.x, game.player.y = 160.0, 160.0
        game.zombie.x, game.zombie.y = 650.0, 160.0
        game.swing()
        game.step(0.1, 0, 0, False, 1000, 160)
        self.assertIsNone(game.zombie_target)
        game.zombie.x = 630.0
        game.step(0.6, 0, 0, False, 1000, 160)
        # Expired attack noise is not replayed when an enemy enters range later.
        self.assertIsNone(game.zombie_target)
        game.swing()
        game.step(0.1, 0, 0, False, 1000, 160)
        self.assertEqual(game.zombie_target, (160.0, 160.0))
        game.restart()
        game.zombie.hp = 0
        before = (game.zombie.x, game.zombie.y)
        game.swing()
        game.step(0.7, 1, 0, True, 1000, 160)
        self.assertIsNone(game.zombie_target)
        self.assertEqual((game.zombie.x, game.zombie.y), before)

    def test_running_noise_reaches_farther_than_walk_behind_wall(self):
        walking = self.make_game()
        running = self.make_game()
        for game in (walking, running):
            game.walls = [Rect(200.0, 120.0, 20.0, 100.0)]
            game.player.x, game.player.y = 160.0, 160.0
            game.zombie.x, game.zombie.y = 300.0, 160.0
        walking.step(0.5, 0, 1, False, 100, 160)
        running.step(0.5, 0, 1, True, 100, 160)
        self.assertIn("walk", [event.kind for event in walking.pop_events()])
        self.assertIn("run", [event.kind for event in running.pop_events()])
        self.assertIsNone(walking.zombie_target)
        self.assertIsNotNone(running.zombie_target)
        self.assertEqual(running.zombie.state, "investigate")

    def test_direct_sight_overrides_an_earlier_sound_and_lost_sight_remembers(self):
        game = self.combat_scene()
        game.swing()
        game.player.x = 210.0
        game.step(0.02, 0, 0, False, 600, 200)
        self.assertEqual(game.zombie.state, "chase")
        self.assertEqual(game.zombie_target, (210.0, 200.0))
        game.player.x, game.player.y = 1000.0, 600.0
        game.step(0.02, 0, 0, False, 600, 200)
        self.assertEqual(game.zombie.state, "investigate")
        self.assertEqual(game.zombie_target, (210.0, 200.0))

    def test_restart_clears_stamina_noise_and_investigation(self):
        game = self.make_game()
        game.stamina = 0.0
        game.exhausted = True
        game.swing()
        game.step(0.02, 0, 0, False, 600, 200)
        self.assertIsNotNone(game.zombie_target)
        game.restart()
        self.assertEqual(game.stamina, 100.0)
        self.assertFalse(game.exhausted)
        self.assertIsNone(game.zombie_target)
        self.assertEqual(game.search_remaining, 0.0)
        self.assertEqual(game.pop_events(), [])
        game.step(0.1, 0, 0, False, 600, 200)
        self.assertEqual(game.zombie.state, "idle")

    def test_navigation_can_leave_a_valid_rounded_corner_position(self):
        wall = Rect(500.0, 255.0, 280.0, 210.0)
        start, target = (486.0, 240.0), (450.0, 350.0)
        self.assertFalse(circle_overlaps_rect(*start, 20.0, wall))
        self.assertIsNotNone(find_path(start, target, 20.0, [wall]))

    def test_unreachable_sound_stops_in_search_instead_of_crossing_wall(self):
        game = self.make_game()
        game.player.x, game.player.y = 600.0, 360.0
        game.zombie.x, game.zombie.y = 400.0, 360.0
        game.walls = [Rect(500.0, 100.0, 20.0, 536.0)]
        game.swing()
        game.step(0.1, 0, 0, False, 600, 600)
        self.assertEqual(game.zombie.state, "search")
        self.assertEqual((game.zombie.x, game.zombie.y), (400.0, 360.0))
        game.step(3.1, 0, 0, False, 600, 600)
        self.assertEqual(game.zombie.state, "idle")

    def test_restart_restores_all_public_gameplay_state(self):
        game = Game()
        self.assertEqual(game.state, "ready")
        self.assertFalse(game.swing())
        game.start()
        game.interact()
        game.swing()
        game.player.hp, game.player.invulnerable, game.player.stun = 1, 0.5, 0.2
        game.player.x, game.player.y = 300.0, 400.0
        game.zombie.hp, game.zombie.state, game.zombie.stun = 0, "dead", 0.3
        game.time = 40.0
        game.state = "lost"
        game.restart()
        self.assertEqual(game.state, "playing")
        self.assertEqual((game.player.x, game.player.y, game.player.hp), (160.0, 160.0, 3))
        self.assertEqual((game.player.invulnerable, game.player.stun), (0.0, 0.0))
        self.assertEqual((game.zombie.x, game.zombie.y, game.zombie.hp), (390.0, 300.0, 5))
        self.assertEqual((game.zombie.state, game.zombie.stun), ("idle", 0.0))
        self.assertFalse(game.carrying)
        self.assertEqual(game.time, 0.0)
        self.assertIsNone(game.attack_elapsed)
        self.assertEqual(game.pop_events(), [])


if __name__ == "__main__":
    unittest.main()
