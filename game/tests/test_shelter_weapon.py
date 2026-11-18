import unittest

from game.combat import CombatWorld, Zombie
from game.core import Wall
from game.delivery import DeliveryWorld
from game.delivery_layouts import NeighborhoodWall


class ShelterWeaponTests(unittest.TestCase):
    def shelter(self):
        world = DeliveryWorld()
        self.assertTrue(world.select_playable_contract(3))
        self.assertTrue(world.skip_route_sequence())
        world.player.x, world.player.y, world.player.aim_angle = 1000, 320, 0
        return world

    def test_durability_is_shelter_only_and_resets_with_a_fresh_bat_and_pickup(self):
        self.assertIsNone(CombatWorld().bat_uses_left)
        world = self.shelter()
        pickup = world.weapon_pickup
        world.bat_uses_left = 0
        world.reserve_bat_uses_left = 3
        world.weapon_pickup = None
        world.reset()
        self.assertEqual((world.bat_uses_left, world.bat_max_uses, world.weapon_pickup), (8, 8, pickup))
        self.assertIsNone(world.reserve_bat_uses_left)
        self.assertFalse(world.swap_weapon())
        for number in (1, 2, 4):
            with self.subTest(number=number):
                self.assertTrue(world.select_playable_contract(number))
                self.assertIsNone(world.bat_uses_left)
                self.assertIsNone(world.reserve_bat_uses_left)
                self.assertFalse(world.unarmed)
                self.assertIsNone(world.weapon_pickup)
                self.assertFalse(world.swap_weapon())

    def test_bat_whiffs_are_free_and_multiple_targets_spend_one_use_at_contact(self):
        world = self.shelter()
        world.zombies.clear()
        self.assertTrue(world.start_attack(stationary_swing=True))
        world.update(0.66)
        self.assertEqual(world.bat_uses_left, 8)

        world.zombies = [Zombie(1034, 320, stun_remaining=2), Zombie(1036, 329, stun_remaining=2)]
        for remaining in range(7, -1, -1):
            for zombie in world.zombies:
                zombie.hp = 5
                zombie.stun_remaining = 2
                zombie.recoil_angle = None
            world.zombies[0].x, world.zombies[0].y = 1034, 320
            world.zombies[1].x, world.zombies[1].y = 1036, 329
            self.assertTrue(world.start_attack(stationary_swing=True))
            world.update(0.239)
            self.assertEqual(world.bat_uses_left, remaining + 1)
            world.update(0.001)
            self.assertEqual(world.bat_uses_left, remaining)
            self.assertEqual([zombie.hp for zombie in world.zombies], [4, 4])
            self.assertFalse(world.attack.unarmed)
            self.assertEqual(world.attack.duration, 0.66)
            world.update(0.42)
        self.assertTrue(world.unarmed)

    def test_moving_car_alarm_contact_spends_wear_only_for_a_bat(self):
        world = self.shelter()
        world.zombies.clear()
        world.walls = [NeighborhoodWall(1030, 310, 20, 30, "parked-car", height=36)]
        for remaining in (7, 6):
            self.assertTrue(world.start_attack())
            world.update(0.18)
            self.assertEqual(world.vehicle_hit, (1030, 320))
            self.assertEqual(world.bat_uses_left, remaining)
            self.assertEqual(world.vehicle_alarm is not None, remaining == 7)
            world.update(0.42)

        world.bat_uses_left = 0
        self.assertTrue(world.start_attack())
        world.update(0.16)
        self.assertIsNone(world.vehicle_hit)
        self.assertIsNone(world.vehicle_alarm)

    def test_punch_range_noise_recovery_and_single_target(self):
        world = self.shelter()
        world.bat_uses_left = 0
        primary = Zombie(1035, 320, stun_remaining=2)
        secondary = Zombie(1028, 329, stun_remaining=2)
        too_far = Zombie(1038, 320, stun_remaining=2)
        outside_noise = Zombie(1180, 320, stun_remaining=2)
        world.zombies = [secondary, too_far, primary, outside_noise]
        self.assertTrue(world.start_attack(stationary_swing=True))
        self.assertTrue(world.attack.unarmed)
        self.assertFalse(world.attack.uses_stationary_swing)
        self.assertEqual((world.attack.hit_time, world.attack.duration), (0.16, 0.42))
        self.assertEqual(too_far.heard_at, (1000, 320))
        self.assertIsNone(outside_noise.heard_at)
        world.update(0.159)
        self.assertEqual(primary.hp, 5)
        world.update(0.001)
        self.assertEqual(world.attack.hit_targets, (primary,))
        self.assertEqual(primary.stun_remaining, 0.24)
        self.assertIsNone(primary.recoil_angle)
        self.assertEqual([zombie.hp for zombie in world.zombies], [5, 5, 4, 5])
        world.update(0.26)
        self.assertIsNone(world.attack)

    def test_bat_pickup_requires_reach_line_of_sight_and_no_active_attack(self):
        world = self.shelter()
        pickup_x, pickup_y = world.weapon_pickup
        world.player.x, world.player.y = pickup_x - 48, pickup_y
        self.assertFalse(world.pick_up_weapon())
        world.player.x, world.player.y = pickup_x - 24, pickup_y
        world.bat_uses_left = 0
        self.assertTrue(world.start_attack())
        self.assertFalse(world.pick_up_weapon())
        world.update(0.42)
        blocker = Wall(pickup_x - 17, pickup_y - 6, 4, 12)
        world.walls.append(blocker)
        self.assertFalse(world.pick_up_weapon())
        world.walls.remove(blocker)
        self.assertTrue(world.pick_up_weapon())
        self.assertEqual(world.bat_uses_left, 8)
        self.assertIsNone(world.reserve_bat_uses_left)
        self.assertIsNone(world.weapon_pickup)
        self.assertFalse(world.pick_up_weapon())

    def test_swap_preserves_each_bats_wear(self):
        world = self.shelter()
        world.player.x, world.player.y = world.weapon_pickup
        self.assertTrue(world.pick_up_weapon())
        self.assertEqual((world.bat_uses_left, world.reserve_bat_uses_left), (8, 8))

        world.player.x, world.player.y = 1000, 320
        world.zombies = [Zombie(1034, 320, stun_remaining=2)]
        self.assertTrue(world.start_attack(stationary_swing=True))
        world.update(0.66)
        self.assertEqual((world.bat_uses_left, world.reserve_bat_uses_left), (7, 8))
        self.assertTrue(world.swap_weapon())
        self.assertEqual((world.bat_uses_left, world.reserve_bat_uses_left), (8, 7))
        self.assertTrue(world.swap_weapon())
        self.assertEqual((world.bat_uses_left, world.reserve_bat_uses_left), (7, 8))

    def test_broken_bat_stays_out_of_reserve_and_last_swing_must_finish(self):
        world = self.shelter()
        world.bat_uses_left = 1
        world.reserve_bat_uses_left = 6
        world.zombies = [Zombie(1034, 320, stun_remaining=2)]
        self.assertTrue(world.start_attack(stationary_swing=True))
        self.assertFalse(world.swap_weapon())
        world.update(0.24)
        self.assertTrue(world.unarmed)
        self.assertEqual(world.reserve_bat_uses_left, 6)
        self.assertFalse(world.swap_weapon())
        world.update(0.42)
        self.assertTrue(world.swap_weapon())
        self.assertFalse(world.unarmed)
        self.assertEqual((world.bat_uses_left, world.reserve_bat_uses_left), (6, None))
        self.assertFalse(world.swap_weapon())

    def test_pickup_and_swap_wait_for_route_and_living_player(self):
        world = DeliveryWorld()
        self.assertTrue(world.select_playable_contract(3))
        world.player.x, world.player.y = world.weapon_pickup
        world.reserve_bat_uses_left = 6
        world.bat_uses_left = 0
        self.assertFalse(world.pick_up_weapon())
        self.assertFalse(world.swap_weapon())
        world.skip_route_sequence()
        world.player.x, world.player.y = world.weapon_pickup
        world.player_hp = 0
        self.assertFalse(world.pick_up_weapon())
        self.assertFalse(world.swap_weapon())
        self.assertEqual((world.bat_uses_left, world.reserve_bat_uses_left), (0, 6))
