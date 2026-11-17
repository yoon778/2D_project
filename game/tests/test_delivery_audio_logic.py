import unittest

from game.delivery_audio_state import DeliveryAudioState, EnemyAcoustics, select_footstep_sources


def enemy(source=1, *, state="idle", distance=100, stride=0, pan=0, occluded=False, kind="regular"):
    return EnemyAcoustics(source, state, distance, stride, pan, occluded, kind)


class DeliveryAudioLogicTests(unittest.TestCase):
    def test_distant_chase_does_not_start_combat_music(self):
        audio = DeliveryAudioState()
        self.assertEqual(audio.update(.05, [enemy(state="chase", distance=350, stride=2)]), (0, 0))
        threat, combat = audio.update(.05, [enemy(state="chase", distance=240, stride=2)])
        self.assertGreater(threat, 0)
        self.assertEqual(combat, 0)
        clear_threat, clear_combat = audio.update(.05, [enemy(state="chase", distance=80, stride=2)])
        covered_threat, covered_combat = audio.update(
            .05, [enemy(state="chase", distance=80, stride=2, occluded=True)])
        self.assertGreater(clear_combat, .8)
        self.assertGreater(clear_threat, covered_threat)
        self.assertLess(covered_combat, clear_combat)

    def test_moving_investigators_build_approach_without_forcing_combat(self):
        audio = DeliveryAudioState()
        idle, _ = audio.update(.05, [enemy()])
        standing, _ = audio.update(.05, [enemy(state="investigate")])
        moving, _ = audio.update(.05, [enemy(state="investigate", stride=2)])
        crowd, combat = audio.update(.05, [enemy(i, state="investigate", stride=2) for i in range(12)])
        self.assertLess(idle, standing)
        self.assertLess(standing, moving)
        self.assertGreater(crowd, moving)
        self.assertLessEqual(crowd - moving, .221)
        self.assertEqual(combat, 0)

    def test_recent_swing_contact_and_damage_release_then_reset(self):
        audio = DeliveryAudioState()
        threat, combat = audio.update(.05, [], impact=.32)
        self.assertEqual((threat, combat), (.32, .32))
        self.assertLess(audio.update(.15, [])[1], combat)
        self.assertEqual(audio.update(.05, [], impact=.8), (.8, .8))
        self.assertEqual(audio.update(.05, [], impact=1.0), (1.0, 1.0))
        self.assertEqual(audio.update(0, []), (1.0, 1.0))
        self.assertEqual(audio.update(1.1, []), (0.0, 0.0))
        audio.update(.05, [], impact=.8)
        audio.reset()
        self.assertEqual(audio.update(.05, []), (0.0, 0.0))

    def test_only_one_walking_source_per_side_with_independent_id_and_stride(self):
        idle_left = enemy(1, distance=12, pan=-1)
        left = enemy(2, distance=80, stride=.55, pan=-1, kind="patrol", occluded=True)
        weaker_left = enemy(3, distance=200, stride=1.4, pan=-1, occluded=True)
        right = enemy(4, distance=90, stride=.9, pan=1, kind="heavy")
        weaker_right = enemy(5, distance=86, stride=1.9, pan=1, occluded=True)
        far = enemy(6, distance=521, stride=3, pan=1)
        self.assertEqual(select_footstep_sources([idle_left, left, weaker_left, right, weaker_right, far]),
                         (left, right))
        switched_side = enemy(2, distance=76, stride=.6, pan=.25, kind="patrol", occluded=True)
        self.assertEqual(select_footstep_sources([idle_left, switched_side]), (switched_side,))
        self.assertEqual((switched_side.source_id, switched_side.stride), (left.source_id, .6))
