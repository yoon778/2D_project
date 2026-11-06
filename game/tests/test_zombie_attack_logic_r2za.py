"""R2-ZA telegraph, one-shot strike, cancellation and timestep regressions."""
import math
import unittest

from game.combat import CombatWorld
from game.core import Wall


class ZombieAttackLogicTests(unittest.TestCase):
    def make_world(self, distance=28.0, angle=math.pi):
        world = CombatWorld()
        world.walls = []
        world.zombie.x = world.player.x - distance * math.cos(angle)
        world.zombie.y = world.player.y - distance * math.sin(angle)
        world.player.aim_angle = math.remainder(angle + math.pi, math.tau)
        return world

    def test_eight_directions_windup_single_strike_stationary_recovery_and_next_update(self):
        for facing, angle in (("right", 0), ("back_right", math.pi / 4), ("back", math.pi / 2),
                              ("back_left", 3 * math.pi / 4), ("left", math.pi),
                              ("front_left", -3 * math.pi / 4), ("front", -math.pi / 2),
                              ("front_right", -math.pi / 4)):
            with self.subTest(facing=facing):
                world = self.make_world(angle=angle)
                origin = (world.zombie.x, world.zombie.y)
                world.update(.299)
                attack = world.zombie.attack
                self.assertIsNotNone(attack)
                self.assertEqual(attack.facing, facing)
                self.assertAlmostEqual(math.remainder(attack.angle - angle, math.tau), 0)
                self.assertAlmostEqual(attack.elapsed, .299)
                self.assertEqual(world.player_hp, 3)
                world.update(.001)
                self.assertEqual(world.player_hp, 2)
                self.assertEqual(world.player_invulnerable_remaining, 1)
                self.assertTrue(attack._hit_done)
                world.update(.5)
                self.assertIsNone(world.zombie.attack)
                self.assertEqual((world.zombie.x, world.zombie.y), origin)
                self.assertEqual(world.player_hp, 2)
                world.update(.001)
                self.assertIsNotNone(world.zombie.attack)
                self.assertIsNot(world.zombie.attack, attack)

    def test_strike_rechecks_range_cone_and_wall_and_never_retries_a_miss(self):
        for distance, offset, wall, expected in (
                (28, 0, None, 2), (28.0001, 0, None, 3),
                (28, math.radians(50), None, 2), (28, math.radians(-50), None, 2),
                (28, math.radians(50.0001), None, 3), (28, math.pi, None, 3),
                (28, 0, Wall(492, 170, 4, 20), 3)):
            with self.subTest(distance=distance, offset=offset, wall=wall):
                world = self.make_world()
                world.update(.1)
                attack = world.zombie.attack
                position = (world.zombie.x, world.zombie.y)
                world.player.x = world.zombie.x + distance * math.cos(attack.angle + offset)
                world.player.y = world.zombie.y + distance * math.sin(attack.angle + offset)
                if wall:
                    world.walls = [wall]
                world.update(.2)
                self.assertEqual(world.player_hp, expected)
                self.assertTrue(attack._hit_done)
                self.assertEqual((world.zombie.x, world.zombie.y), position)
                self.assertEqual(attack.facing, "left")
                world.player.x, world.player.y = world.zombie.x - 10, world.zombie.y
                world.walls = []
                world.update(.499)
                self.assertEqual(world.player_hp, expected)

    def test_walking_away_evades_and_a_wall_prevents_attack_start(self):
        world = self.make_world()
        world.update(.001)
        world.update(.299, -1, 0)
        self.assertEqual(world.player_hp, 3)
        self.assertEqual(world.zombie.x, 508)
        self.assertGreater(world.zombie.x - world.player.x, 28)
        world = self.make_world()
        world.walls = [Wall(492, 170, 4, 20)]
        world.update(.8)
        self.assertIsNone(world.zombie.attack)
        self.assertEqual(world.player_hp, 3)

    def test_immunity_blocks_only_damage_and_defeat_cancels_all_attacks(self):
        world = self.make_world()
        world.player_invulnerable_remaining = .4
        world.update(.3)
        self.assertEqual(world.player_hp, 3)
        self.assertTrue(world.zombie.attack._hit_done)
        world.update(.5)
        self.assertIsNone(world.zombie.attack)
        world.update(.3)
        self.assertEqual(world.player_hp, 2)
        world = self.make_world()
        world.player_hp = 1
        world.player.aim_angle = math.pi
        world.update(.2)
        world.start_attack("left")
        world.update(.1)
        self.assertEqual((world.player_hp, world.result), (0, "defeated"))
        self.assertIsNone(world.attack)
        self.assertIsNone(world.zombie.attack)
        before = (world.player.x, world.zombie.x)
        world.update(1, 1, 0)
        self.assertEqual((world.player.x, world.zombie.x), before)

    def test_player_hit_simultaneous_priority_stun_and_death_cancel_pending_damage(self):
        world = self.make_world()
        world.update(.12)
        cancelled = world.zombie.attack
        self.assertTrue(world.start_attack())
        world.update(.18)
        self.assertEqual((world.player_hp, world.zombie.hp, world.zombie.stun_remaining), (3, 4, .4))
        self.assertIsNone(world.zombie.attack)
        self.assertFalse(cancelled._hit_done)
        world.update(.3)
        self.assertEqual(world.player_hp, 3)
        self.assertIsNone(world.zombie.attack)
        for dead in (False, True):
            with self.subTest(dead=dead):
                world = self.make_world()
                world.update(.2)
                if dead:
                    world.zombie.hp = 0
                else:
                    world.zombie.stun_remaining = .4
                world.update(.1)
                self.assertIsNone(world.zombie.attack)
                self.assertEqual(world.player_hp, 3)

    def test_zero_dt_reset_and_terminal_results_clear_attack_state(self):
        world = self.make_world()
        world.update(0)
        self.assertIsNone(world.zombie.attack)
        world.update(.15)
        attack = world.zombie.attack
        for dt in (0, -.1, math.nan, math.inf):
            world.update(dt, 1, 0)
            self.assertIs(world.zombie.attack, attack)
            self.assertAlmostEqual(attack.elapsed, .15)
            self.assertEqual(world.player_hp, 3)
        world.reset()
        self.assertIsNone(world.zombie.attack)
        self.assertEqual((world.zombie.hp, world.player_hp, world.result), (5, 3, "playing"))

    def test_normal_dt_partitions_keep_strikes_immunity_recovery_and_movement_consistent(self):
        for distance, total, axis, player_attack in ((28, .3, 0, False), (28, .8, 0, False),
                (28, 1.9, 0, False), (28, 3.5, 0, False), (60, 1.2, 0, False),
                (28, 1.2, -1, False), (28, 1.2, 0, True)):
            reference = None
            for steps in ((total,), (.05,), (.016,), (.01,), (1 / 60,), (1 / 240,), (.0173,),
                          (.005, .0213, .0037, .0173, 1 / 240)):
                with self.subTest(distance=distance, total=total, steps=steps, axis=axis, player_attack=player_attack):
                    world = self.make_world(distance)
                    if player_attack:
                        world.start_attack()
                    remaining = total
                    index = 0
                    while remaining > 1e-12:
                        dt = min(steps[index % len(steps)], remaining)
                        world.update(dt, axis, 0)
                        remaining -= dt
                        index += 1
                    attack = world.zombie.attack
                    observed = (world.player.x, world.player.y, world.zombie.x, world.zombie.y,
                                world.player_hp, world.zombie.hp, world.zombie.stun_remaining,
                                world.player_invulnerable_remaining, world.attack.elapsed if world.attack else -1,
                                attack.elapsed if attack else -1, attack.angle if attack else 0)
                    labels = (world.result, attack.facing if attack else None, attack._hit_done if attack else None)
                    if reference is None:
                        reference = observed, labels
                    else:
                        self.assertEqual(labels, reference[1])
                        for actual, expected in zip(observed, reference[0]):
                            self.assertAlmostEqual(actual, expected, places=8)


if __name__ == "__main__":
    unittest.main()
