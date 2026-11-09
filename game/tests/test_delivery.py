import unittest

from game.combat import ATTACK_HIT_TIME, Zombie
from game.core import Wall
from game.delivery import DeliveryWorld, PLAYER_START, ZOMBIE_START, ZOMBIE_STARTS


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
        self.assertEqual([(zombie.x, zombie.y) for zombie in world.zombies], list(ZOMBIE_STARTS))
        self.assertTrue(all(zombie.alive for zombie in world.zombies))

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

    def test_attack_hits_only_nearest_zombie_in_reach_and_facing(self):
        world = self.world
        world.player.x, world.player.y, world.player.aim_angle = (1000, 1100, 0.0)
        farther, behind, nearest = Zombie(1060, 1100), Zombie(970, 1100), Zombie(1040, 1100)
        world.zombies = [farther, behind, nearest]
        self.assertTrue(world.start_attack())
        world.update(ATTACK_HIT_TIME)
        self.assertIs(world.attack.hit_target, nearest)
        self.assertEqual([zombie.hp for zombie in world.zombies], [5, 5, 4])
        self.assertEqual(farther.stun_remaining, 0.0)
        self.assertGreater(nearest.stun_remaining, 0.0)

    def test_noise_is_investigated_independently_across_a_wall(self):
        world = self.world
        world.player.x, world.player.y = (975, 1000)
        world.walls = [Wall(1010, 930, 40, 160)]
        south, north, distant = Zombie(1100, 950), Zombie(1120, 1080), Zombie(1610, 1050)
        world.zombies = [south, north, distant]
        world.start_attack()
        world.update(0.05)
        self.assertEqual([zombie.state for zombie in world.zombies], ["investigate", "investigate", "idle"])
        self.assertEqual(south.target, north.target)
        self.assertNotEqual(south.investigation_route[0], north.investigation_route[0])

    def test_delivery_sprint_opens_distance_from_a_chasing_zombie(self):
        world = self.world
        world.player.aim_angle = 0.0
        zombie = Zombie(world.player.x - 90, world.player.y)
        world.zombies = [zombie]
        world.update(1.0, 1, 0, sprint=True)
        self.assertEqual(zombie.state, "chase")
        self.assertAlmostEqual(world.player.x - PLAYER_START[0], 210.0)
        self.assertAlmostEqual(world.player.x - zombie.x, 210.0)
        self.assertLess(world.stamina, 100.0)
