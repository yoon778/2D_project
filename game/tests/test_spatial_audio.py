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

    def test_chase_ducks_smoothly_and_recovers_to_distance_volume(self):
        self.music.start()
        self.music.update(3, distance=150, opening=True, chasing=True)
        self.backend.Mix_VolumeMusic.assert_called_once_with(32)
        self.music.update(.05, distance=150, chasing=True)
        partial = self.backend.Mix_VolumeMusic.call_args.args[0]
        self.assertGreater(partial, 10)
        self.assertLess(partial, 32)
        self.music.update(3, distance=150, chasing=True)
        self.backend.Mix_VolumeMusic.assert_called_with(10)
        self.music.update(.05, distance=150)
        partial = self.backend.Mix_VolumeMusic.call_args.args[0]
        self.assertGreater(partial, 10)
        self.assertLess(partial, 27)
        self.music.update(3, distance=150)
        self.backend.Mix_VolumeMusic.assert_called_with(27)
        self.backend.Mix_PlayMusic.assert_called_once_with(self.music_handle, -1)

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
        names = ("zombie_step", "zombie_groan", "bat_swing", "zombie_hit",
                 "player_walk", "player_run", "player_sneak", "player_hit",
                 "parcel_pickup", "parcel_drop", "bottle_pickup", "map_rustle",
                 "bottle_break", "gate_open", "vehicle_alarm")
        self.sounds = {name: ctypes.c_void_p(index) for index, name in enumerate(names, 1)}
        self.backend.Mix_LoadWAV.side_effect = lambda path: self.sounds.get(Path(path.decode()).stem)
        self.backend.Mix_PlayChannelTimed.side_effect = [0, 1]
        self.backend.Mix_Playing.return_value = True
        self.audio = spatial_audio.ZombieAudio(Path("sounds"))

    def test_footstep_and_groan_get_quieter_with_distance_and_walls(self):
        step, groan = self.sounds["zombie_step"], self.sounds["zombie_groan"]
        self.backend.Mix_GetChunk.side_effect = (step, groan, step, groan)
        self.audio.update(.4, distance=20, stride=32, active=True, pan=-1.0)
        self.audio.update(.01, distance=420, stride=0, active=True, pan=1.0)
        self.audio.update(.01, distance=420, stride=0, active=True, occluded=True)
        self.assertEqual(self.backend.Mix_VolumeChunk.call_args_list,
                         [call(step, 46), call(groan, 58), call(step, 9), call(groan, 12),
                          call(step, 6), call(groan, 8)])
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_args_list,
                         [call(-1, step, 0, -1), call(-1, groan, 0, -1)])
        self.assertEqual(self.backend.Mix_SetPanning.call_args_list, [call(0, 255, 80), call(1, 255, 80)])

    def test_new_sounds_pan_by_position_and_center_reused_channels(self):
        self.backend.Mix_PlayChannelTimed.side_effect = (0, 1, 2, 0)
        self.audio.play_bottle_break(260, pan=-4.0)
        self.audio.play_gate_open(0, pan=.5)
        self.audio.play_vehicle_alarm(0, pan=math.nan)
        self.audio.play_bat_swing()
        self.assertEqual(self.backend.Mix_SetPanning.call_args_list,
                         [call(0, 255, 80), call(1, 168, 255), call(2, 255, 255), call(0, 255, 255)])
        self.assertEqual(self.backend.Mix_VolumeChunk.call_args_list, [
            call(self.sounds["bottle_break"], 41), call(self.sounds["gate_open"], 72),
            call(self.sounds["vehicle_alarm"], 76), call(self.sounds["bat_swing"], 74),
        ])

    def test_failed_channel_allocation_does_not_set_panning(self):
        self.backend.Mix_PlayChannelTimed.side_effect = (-1,)
        self.audio.play_gate_open(0, pan=1.0)
        self.backend.Mix_SetPanning.assert_not_called()

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

    def test_player_gaits_use_distinct_distance_and_volume(self):
        self.backend.Mix_PlayChannelTimed.side_effect = (0, 1, 2)
        for kind, sprinting, sneaking, distance, volume in (
            ("player_walk", False, False, 32, 42),
            ("player_run", True, False, 48, 67),
            ("player_sneak", True, True, 32, 20),
        ):
            with self.subTest(kind=kind):
                sound = self.sounds[kind]
                count = self.backend.Mix_PlayChannelTimed.call_count
                self.audio.update_player_steps(distance - 1, sprinting=sprinting, sneaking=sneaking)
                self.audio.update_player_steps(0, sprinting=sprinting, sneaking=sneaking)
                self.assertEqual(self.backend.Mix_PlayChannelTimed.call_count, count)
                self.audio.update_player_steps(1, sprinting=sprinting, sneaking=sneaking)
                self.assertEqual(self.backend.Mix_PlayChannelTimed.call_count, count + 1)
                self.backend.Mix_PlayChannelTimed.assert_called_with(-1, sound, 0, -1)
                self.backend.Mix_VolumeChunk.assert_called_with(sound, volume)

    def test_player_steps_preserve_fraction_on_gait_change_and_reset_on_stop(self):
        run, walk = self.sounds["player_run"], self.sounds["player_walk"]
        self.backend.Mix_GetChunk.return_value = run
        self.audio.update_player_steps(16, sprinting=False, sneaking=False)
        self.audio.update_player_steps(24, sprinting=True, sneaking=False)
        self.backend.Mix_PlayChannelTimed.assert_called_once_with(-1, run, 0, -1)
        self.audio.update_player_steps(16, sprinting=False, sneaking=False)
        self.audio.stop()
        self.backend.Mix_HaltChannel.assert_called_once_with(0)
        self.audio.update_player_steps(16, sprinting=False, sneaking=False)
        self.backend.Mix_PlayChannelTimed.assert_called_once_with(-1, run, 0, -1)
        self.audio.update_player_steps(16, sprinting=False, sneaking=False)
        self.backend.Mix_PlayChannelTimed.assert_called_with(-1, walk, 0, -1)

    def test_player_hit_uses_a_distinct_effect_channel(self):
        zombie, player = self.sounds["zombie_hit"], self.sounds["player_hit"]
        self.audio.play_zombie_hit()
        self.audio.play_player_hit()
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_args_list,
                         [call(-1, zombie, 0, -1), call(-1, player, 0, -1)])
        self.backend.Mix_VolumeChunk.assert_called_with(player, 78)

    def test_interaction_effects_use_distinct_chunks_and_only_map_tail_survives_pause(self):
        self.backend.Mix_PlayChannelTimed.side_effect = range(4)
        chunks = [self.sounds[name] for name in ("parcel_pickup", "parcel_drop", "bottle_pickup", "map_rustle")]
        self.backend.Mix_GetChunk.side_effect = chunks
        self.audio.play_parcel_pickup()
        self.audio.play_parcel_drop()
        self.audio.play_bottle_pickup()
        self.audio.play_map_toggle()
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_args_list,
                         [call(-1, chunk, 0, -1) for chunk in chunks])
        self.assertEqual(self.backend.Mix_VolumeChunk.call_args_list,
                         [call(chunk, gain) for chunk, gain in zip(chunks, (40, 46, 35, 33))])
        self.audio.update(0, distance=None, stride=0, active=False, preserve_map_cue=True)
        self.audio.update(0, distance=None, stride=0, active=False, preserve_map_cue=True)
        self.assertEqual(self.backend.Mix_HaltChannel.call_args_list, [call(0), call(1), call(2)])
        self.audio.update(0, distance=None, stride=0, active=False)
        self.assertEqual(self.backend.Mix_HaltChannel.call_args_list, [call(0), call(1), call(2), call(3)])


if __name__ == "__main__":
    unittest.main()
