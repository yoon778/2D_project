import unittest

from game.combat import Zombie
from game.core import PLAYER_RADIUS, Wall, move_player, wall_blocks
from game.delivery import CABINET_NOISE_RANGE, DeliveryWorld


class ShelterCabinetTests(unittest.TestCase):
    def shelter(self, *, collect_parcel=True):
        world = DeliveryWorld()
        self.assertTrue(world.select_playable_contract(3))
        self.assertTrue(world.skip_route_sequence())
        if collect_parcel:
            self.assertTrue(world.interact())
        world.player.x, world.player.y = (1138, 738)
        return world

    @staticmethod
    def hold(world, dt, *, pressed=False, held=True, moving=False, damaged=False):
        return world.update_interaction(dt, held=held, pressed=pressed, moving=moving, damaged=damaged)

    def test_cabinet_only_opens_after_parcel_pickup_and_allows_return_leg(self):
        world = self.shelter(collect_parcel=False)
        self.assertIsNone(world.interaction_candidate)
        world.player.x, world.player.y = world.pickup
        self.assertTrue(world.interact())
        world.player.x, world.player.y = world.destination
        self.assertTrue(world.interact())
        self.assertTrue(world.returning)
        world.player.x, world.player.y = (1138, 738)
        self.assertEqual(world.interaction_candidate, "search_cabinet")
        self.assertTrue(self.hold(world, .65, pressed=True))

    def test_cancelling_search_resets_progress_without_noise_or_loot(self):
        for cancel in ({"held": False}, {"moving": True}, {"damaged": True}):
            with self.subTest(cancel=cancel):
                world = self.shelter()
                listener = Zombie(1138, 717)
                world.zombies = [listener]
                self.assertFalse(self.hold(world, .30, pressed=True))
                self.assertGreater(world.interaction_progress, 0)
                self.assertFalse(self.hold(world, .35, **cancel))
                self.assertEqual(world.interaction_progress, 0)
                self.assertFalse(world.cabinet_open)
                self.assertIsNone(world.cabinet_weapon_pickup)
                self.assertIsNone(listener.heard_at)
                self.assertFalse(self.hold(world, .65))

    def test_completion_emits_noise_through_shelf_and_only_releases_one_bat(self):
        world = self.shelter()
        x, y = world.cabinet_position
        behind_shelf = Zombie(x, y + 80)
        too_far = Zombie(x + CABINET_NOISE_RANGE + 1, y)
        world.zombies = [behind_shelf, too_far]
        self.assertTrue(any(wall_blocks(world.cabinet_position, (behind_shelf.x, behind_shelf.y), wall)
                            for wall in world.walls))
        self.assertFalse(self.hold(world, .64, pressed=True))
        self.assertIsNone(behind_shelf.heard_at)
        self.assertTrue(self.hold(world, .01))
        self.assertTrue(world.cabinet_open)
        self.assertEqual(world.cabinet_weapon_pickup, (1108, 750))
        self.assertEqual(behind_shelf.heard_at, world.cabinet_position)
        self.assertIsNone(too_far.heard_at)
        behind_shelf.heard_at = None
        self.assertFalse(self.hold(world, .65, pressed=True))
        self.assertIsNone(behind_shelf.heard_at)

    def test_search_respects_room_and_line_of_sight_and_shelf_still_collides(self):
        world = self.shelter()
        wall = Wall(1132, 747, 12, 6)
        world.walls.append(wall)
        self.assertIsNone(world.interaction_candidate)
        world.walls.remove(wall)
        move_player(world.player, 0, 1, 1, world.walls, world_size=world.world_size)
        self.assertEqual(world.player.y, 780 - PLAYER_RADIUS)
        world.player.x, world.player.y = (1138, 549)
        self.assertFalse(world.can_search_cabinet())

    def test_spares_are_independent_and_reset_restores_sealed_cabinet(self):
        world = self.shelter()
        outside_spare = world.weapon_pickup
        self.assertTrue(self.hold(world, .65, pressed=True))
        world.player.x, world.player.y = (1095, 746)
        self.assertTrue(world.pick_up_weapon())
        self.assertIsNone(world.cabinet_weapon_pickup)
        self.assertEqual(world.weapon_pickup, outside_spare)
        self.assertEqual((world.bat_uses_left, world.reserve_bat_uses_left), (8, 8))
        world.player.x, world.player.y = outside_spare
        self.assertIsNone(world.nearby_weapon)
        self.assertFalse(world.pick_up_weapon())
        self.assertEqual(world.weapon_pickup, outside_spare)
        world.bat_uses_left = 0
        self.assertTrue(world.pick_up_weapon())
        self.assertIsNone(world.weapon_pickup)
        self.assertEqual((world.bat_uses_left, world.reserve_bat_uses_left), (8, 8))
        world.reset()
        self.assertEqual(world.weapon_pickup, outside_spare)
        self.assertFalse(world.cabinet_open)
        self.assertIsNone(world.cabinet_weapon_pickup)
        self.assertTrue(world.select_playable_contract(1))
        self.assertIsNone(world.cabinet_position)
