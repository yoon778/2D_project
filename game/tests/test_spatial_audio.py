"""BGM loop, distance volume, focus and resource ownership checks."""
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
        self.assertGreater(first_volume, 22)
        self.assertLess(first_volume, 32)
        for distance, opening, expected in ((None, False, 22), (180, False, 22),
                                            (150, False, 15), (120, False, 8), (0, False, 8), (0, True, 32)):
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
        self.backend.Mix_VolumeMusic.assert_called_with(8)
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
        self.backend.Mix_VolumeMusic.assert_called_with(22)


if __name__ == "__main__":
    unittest.main()
