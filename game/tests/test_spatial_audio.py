"""BGM loop, distance volume, focus and resource ownership checks."""
import ctypes
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, call, patch

from game import spatial_audio


class BackgroundMusicTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.path = Path(directory) / "배경음악.mp3"
        self.path.write_bytes(b"test fixture")
        self.backend = self.enterContext(patch.object(spatial_audio, "p", Mock()))
        self.music_handle = object()
        self.backend.Mix_QuerySpec.return_value = 1
        self.backend.Mix_LoadMUS.return_value = self.music_handle
        self.backend.Mix_PlayMusic.return_value = 0
        self.music = spatial_audio.BackgroundMusic(self.path)

    def test_start_loops_once_and_close_halts_and_frees_once(self):
        self.music.start()
        self.music.start()
        self.assertEqual(self.backend.mock_calls, [call.Mix_QuerySpec(None, None, None),
                         call.Mix_LoadMUS(str(self.path).encode("utf-8")), call.Mix_VolumeMusic(32),
                         call.Mix_PlayMusic(self.music_handle, -1)])
        self.music.close()
        self.music.close()
        self.music.start()
        self.music.update(1, distance=120)
        self.assertEqual(self.backend.mock_calls[-2:], [call.Mix_HaltMusic(), call.Mix_FreeMusic(self.music_handle)])
        self.backend.Mix_LoadMUS.assert_called_once()
        self.backend.Mix_PlayMusic.assert_called_once()
        self.backend.Mix_HaltMusic.assert_called_once()
        self.backend.Mix_FreeMusic.assert_called_once()

    def test_intro_exploration_and_distance_volume_settle_smoothly(self):
        self.music.start()
        self.music.update(.05, distance=0, opening=True)
        self.backend.Mix_VolumeMusic.assert_called_once_with(32)
        self.music.update(.05)
        first_volume = self.backend.Mix_VolumeMusic.call_args.args[0]
        self.assertGreater(first_volume, 32)
        self.assertLess(first_volume, 38)
        for distance, opening, expected in ((None, False, 38), (180, False, 38),
                                            (150, False, 27), (120, False, 16), (0, False, 16), (0, True, 32)):
            with self.subTest(distance=distance, opening=opening):
                self.music.update(3, distance=distance, opening=opening)
                self.backend.Mix_VolumeMusic.assert_called_with(expected)
        self.backend.Mix_LoadMUS.assert_called_once()
        self.backend.Mix_PlayMusic.assert_called_once()

    def test_focus_transitions_pause_once_and_resume_without_restarting(self):
        self.music.start()
        self.music.update(.1, focused=False, distance=120)
        self.music.update(2, focused=False, distance=0)
        self.backend.Mix_PauseMusic.assert_called_once()
        self.backend.Mix_VolumeMusic.assert_called_once_with(32)
        self.music.update(0, focused=True)
        self.music.update(0, focused=True)
        self.backend.Mix_ResumeMusic.assert_called_once()
        self.music.update(3, distance=120)
        self.backend.Mix_VolumeMusic.assert_called_with(16)
        self.backend.Mix_PlayMusic.assert_called_once_with(self.music_handle, -1)

    def test_missing_file_is_silent(self):
        music = spatial_audio.BackgroundMusic(self.path.with_name("missing.mp3"))
        music.start()
        music.update(1, focused=False)
        music.close()
        self.assertEqual(self.backend.mock_calls, [])

    def test_unavailable_audio_device_skips_load_and_play(self):
        self.backend.Mix_QuerySpec.return_value = 0
        self.music.start()
        self.music.start()
        self.music.update(1)
        self.music.close()
        self.assertEqual(self.backend.mock_calls, [call.Mix_QuerySpec(None, None, None)])

    def test_failed_load_leaves_no_resource_to_play_or_free(self):
        self.backend.Mix_LoadMUS.return_value = None
        self.music.start()
        self.music.close()
        self.backend.Mix_PlayMusic.assert_not_called()
        self.backend.Mix_FreeMusic.assert_not_called()
        self.backend.Mix_HaltMusic.assert_not_called()

    def test_failed_play_frees_the_loaded_resource_once(self):
        self.backend.Mix_PlayMusic.return_value = -1
        self.music.start()
        self.music.start()
        self.music.update(1, focused=False)
        self.music.close()
        self.backend.Mix_FreeMusic.assert_called_once_with(self.music_handle)
        self.backend.Mix_HaltMusic.assert_not_called()
        self.backend.Mix_PauseMusic.assert_not_called()

    def test_invalid_time_does_not_change_volume_and_invalid_distance_uses_exploration(self):
        self.music.start()
        for dt in (0, -1, math.nan, math.inf):
            self.music.update(dt, distance=0)
        self.backend.Mix_VolumeMusic.assert_called_once_with(32)
        self.music.update(3, distance=math.nan)
        self.backend.Mix_VolumeMusic.assert_called_with(38)


class ZombieAudioTests(unittest.TestCase):
    def setUp(self):
        self.backend = self.enterContext(patch.object(spatial_audio, "p", Mock()))
        self.backend.Mix_QuerySpec.return_value = 1
        names = ("zombie_step", "zombie_groan", "bat_swing", "zombie_hit")
        self.sounds = {name: ctypes.c_void_p(index) for index, name in enumerate(names, 1)}
        self.backend.Mix_LoadWAV.side_effect = lambda path: self.sounds.get(Path(path.decode()).stem)
        self.backend.Mix_PlayChannelTimed.side_effect = [0, 1]
        self.backend.Mix_Playing.return_value = True
        self.audio = spatial_audio.ZombieAudio(Path("sounds"))

    def test_footstep_and_groan_get_quieter_with_distance_and_walls(self):
        step, groan = self.sounds["zombie_step"], self.sounds["zombie_groan"]
        self.backend.Mix_GetChunk.side_effect = (step, groan, step, groan)
        self.audio.update(.4, distance=20, stride=32, active=True)
        self.audio.update(.01, distance=420, stride=0, active=True)
        self.audio.update(.01, distance=420, stride=0, active=True, occluded=True)
        self.assertEqual(self.backend.Mix_VolumeChunk.call_args_list,
                         [call(step, 46), call(groan, 58), call(step, 9), call(groan, 12),
                          call(step, 6), call(groan, 8)])
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_args_list,
                         [call(-1, step, 0, -1), call(-1, groan, 0, -1)])

    def test_bat_swing_and_hit_use_independent_effect_channels(self):
        swing, hit = self.sounds["bat_swing"], self.sounds["zombie_hit"]
        self.backend.Mix_GetChunk.side_effect = (swing, hit)
        self.audio.play_bat_swing()
        self.backend.Mix_PlayChannelTimed.assert_called_once_with(-1, swing, 0, -1)
        self.audio.play_zombie_hit()
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_args_list,
                         [call(-1, swing, 0, -1), call(-1, hit, 0, -1)])
        self.backend.Mix_HaltChannel.assert_not_called()
        self.audio.update(0, distance=None, stride=0, active=True)
        self.backend.Mix_HaltChannel.assert_not_called()
        self.audio.stop()
        self.assertEqual(self.backend.Mix_HaltChannel.call_args_list, [call(0), call(1)])


if __name__ == "__main__":
    unittest.main()
