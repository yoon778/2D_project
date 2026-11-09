import unittest

from game.core import Wall
from game.delivery import DeliveryWorld, PLAYER_START, ZOMBIE_START


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.world = DeliveryWorld()

    def test_requires_pickup_and_reaches_success_only_at_destination(self):
        world = self.world
        world.player.x, world.player.y = world.destination
        self.assertFalse(world.interact())
        world.player.x, world.player.y = PLAYER_START
        self.assertTrue(world.interact())
        self.assertEqual(world.parcel, "carrying")
        self.assertFalse(world.interact())
        world.player.x, world.player.y = world.destination
        self.assertTrue(world.interact())
        self.assertEqual((world.parcel, world.result), ("delivered", "delivered"))
        world.update(0.5, 1, 0, sprint=True)
        self.assertEqual((world.player.x, world.player.y), world.destination)
        self.assertFalse(world.interact())

    def test_interaction_cannot_reach_through_wall(self):
        world = self.world
        world.walls = [Wall(155, 135, 4, 40)]
        self.assertFalse(world.interact())
        self.assertEqual(world.parcel, "waiting")

    def test_zero_health_overrides_delivery_and_reset_restores_run(self):
        world = self.world
        world.interact()
        world.player.x, world.player.y = world.destination
        world.player_hp = 0
        world.stamina = 2
        world.zombie.hp = 0
        self.assertFalse(world.interact())
        self.assertEqual(world.result, "defeated")
        world.reset()
        self.assertEqual((world.player_hp, world.stamina), (3, 100))
        self.assertEqual((world.result, world.parcel), ("playing", "waiting"))
        self.assertEqual((world.player.x, world.player.y), PLAYER_START)
        self.assertEqual((world.zombie.x, world.zombie.y, world.zombie.hp), (*ZOMBIE_START, 5))
        self.assertEqual((world.zombie.state, world.zombie.target), ("idle", None))

    def test_killing_zombie_leaves_delivery_active_and_corpse_cannot_be_hit(self):
        world = self.world
        world.player.aim_angle = 0
        world.zombie.x, world.zombie.y = (175, 145)
        world.zombie.hp = 1
        self.assertTrue(world.start_attack())
        world.update(0.6)
        self.assertEqual((world.zombie.hp, world.result), (0, "playing"))
        self.assertTrue(world.start_attack())
        world.update(0.6)
        self.assertEqual(world.zombie.hp, 0)
        self.assertTrue(world.interact())
