from pathlib import Path
from types import SimpleNamespace
import unittest

from game.spatial_audio import SpatialAudio


class FakeSDL:
    def __init__(self, audio_on=True):
        self.audio_on = audio_on
        self.allocated = 8
        self.reserved = 0
        self.loaded = []
        self.played = []
        self.volumes = {}
        self.playing = set()
        self.halted = []

    def Mix_AllocateChannels(self, count):
        if count >= 0:
            self.allocated = count
        return self.allocated

    def Mix_ReserveChannels(self, count):
        self.reserved = count

    def load_wav(self, path):
        self.loaded.append(Path(path).name)
        return SimpleNamespace(wav=Path(path).stem)

    def Mix_PlayChannelTimed(self, channel, chunk, loops, ticks):
        self.played.append((channel, chunk, loops, ticks))
        self.playing.add(channel)
        return channel

    def Mix_Volume(self, channel, gain):
        self.volumes[channel] = gain

    def Mix_Playing(self, channel):
        return channel in self.playing

    def Mix_HaltChannel(self, channel):
        self.halted.append(channel)
        self.playing.discard(channel)


def scene():
    return SimpleNamespace(
        player=SimpleNamespace(x=100.0, y=200.0, hp=3),
        zombie=SimpleNamespace(x=360.0, y=200.0, hp=5),
        state="playing",
        # Any accidental flashlight/LOS dependency must fail the test.
        is_visible=lambda *args: (_ for _ in ()).throw(AssertionError("visibility queried")),
    )


class SpatialAudioTests(unittest.TestCase):
    def make_audio(self):
        p = FakeSDL()
        audio = SpatialAudio(p, Path("game"))
        game = scene()
        audio.update(game)
        return p, audio, game

    def test_channels_are_reserved_and_distance_gain_is_independent(self):
        p, audio, game = self.make_audio()
        self.assertEqual((p.allocated, p.reserved), (16, 8))
        self.assertTrue(audio.play("zombie_step", 100, 200, 100, 200))
        self.assertTrue(audio.play("zombie_groan", 360, 200, 100, 200))
        self.assertEqual(p.volumes, {6: 48, 7: 30})
        self.assertEqual(p.played, [(6, "zombie_step", 0, -1), (7, "zombie_groan", 0, -1)])
        # Loudness changes only on the dedicated channel, never on a shared chunk.
        self.assertFalse(hasattr(p, "Mix_VolumeChunk"))

    def test_far_cutoff_and_unsupported_events_do_not_play(self):
        p, audio, game = self.make_audio()
        self.assertFalse(audio.play("zombie_step", 620, 200, 100, 200))
        self.assertFalse(audio.play("zombie_groan", 800, 200, 100, 200))
        self.assertFalse(audio.play("hit", 100, 200, 100, 200))
        self.assertEqual(p.played, [])
        self.assertGreater(audio.volume("zombie_groan", 100), audio.volume("zombie_groan", 300))

    def test_updates_follow_moving_source_and_listener_without_restarting(self):
        p, audio, game = self.make_audio()
        audio.play("zombie_step", game.zombie.x, game.zombie.y, game.player.x, game.player.y)
        audio.play("zombie_groan", game.zombie.x, game.zombie.y, game.player.x, game.player.y)
        self.assertEqual(p.volumes, {6: 24, 7: 30})
        game.player.x = 230
        audio.update(game)
        self.assertEqual(p.volumes, {6: 36, 7: 45})
        game.zombie.x = 100
        game.player.x = 100
        audio.update(game)
        self.assertEqual(p.volumes, {6: 48, 7: 60})
        self.assertEqual(len(p.played), 2)
        self.assertFalse(audio.play("zombie_groan", 100, 200, 100, 200))
        game.player.x = 700
        audio.update(game)
        self.assertEqual(p.playing, set())
        self.assertCountEqual(p.halted, [6, 7])

    def test_focus_results_death_and_restart_stop_and_block_queued_sounds(self):
        for reason in ("focus", "ready", "won", "lost", "zombie_dead", "player_dead", "restart"):
            with self.subTest(reason=reason):
                p, audio, game = self.make_audio()
                audio.play("zombie_groan", 360, 200, 100, 200)
                if reason in ("ready", "won", "lost"):
                    game.state = reason
                elif reason == "zombie_dead":
                    game.zombie.hp = 0
                elif reason == "player_dead":
                    game.player.hp = 0
                elif reason == "restart":
                    game.player = SimpleNamespace(x=100.0, y=200.0, hp=3)
                audio.update(game, focused=reason != "focus")
                self.assertNotIn(7, p.playing)
                self.assertEqual(p.halted, [7])
                if reason != "restart":
                    self.assertFalse(audio.play("zombie_groan", 360, 200, 100, 200))
                else:
                    self.assertTrue(audio.play("zombie_groan", 360, 200, 100, 200))

    def test_finished_samples_reset_and_close(self):
        p, audio, game = self.make_audio()
        audio.play("zombie_step", 100, 200, 100, 200)
        p.playing.clear()  # The real mixer naturally finishes the short sample.
        audio.update(game)
        self.assertTrue(audio.play("zombie_step", 100, 200, 100, 200))
        audio.reset()
        self.assertFalse(audio.play("zombie_step", 100, 200, 100, 200))
        audio.update(game)
        self.assertTrue(audio.play("zombie_step", 100, 200, 100, 200))
        audio.close()
        self.assertFalse(audio.enabled)
        self.assertEqual(audio.sounds, {})
        self.assertFalse(audio.play("zombie_step", 100, 200, 100, 200))

    def test_audio_disabled_does_not_load_or_call_mixer(self):
        p = FakeSDL(audio_on=False)
        audio = SpatialAudio(p, Path("game"))
        audio.update(scene())
        self.assertFalse(audio.play("zombie_step", 100, 200, 100, 200))
        audio.stop()
        audio.close()
        self.assertEqual((p.loaded, p.played, p.halted), ([], [], []))
        self.assertEqual(p.allocated, 8)


if __name__ == "__main__":
    unittest.main()
