"""BGM loop, distance volume, focus and resource ownership checks."""
import ctypes
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
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

    def test_music_gain_applies_to_stream_while_paused(self):
        settings = spatial_audio.AudioSettings(master=50, music=50, effects=0)
        music = spatial_audio.BackgroundMusic(self.path, settings=settings)
        self.addCleanup(music.close)
        music.start()
        self.backend.Mix_VolumeMusic.assert_called_once_with(8)
        settings.master = 0
        music.update(0, focused=False)
        self.backend.Mix_VolumeMusic.assert_called_with(0)
        settings.master = 100
        music.update(0, focused=False)
        self.backend.Mix_VolumeMusic.assert_called_with(16)
        music.update(0, focused=True)
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


class AdaptiveMusicTests(unittest.TestCase):
    def setUp(self):
        directory = Path(self.enterContext(TemporaryDirectory()))
        self.paths = tuple(directory / f"{name}.ogg" for name in ("base", "near", "chase"))
        for path in self.paths:
            path.write_bytes(b"test fixture")
        self.backend = self.enterContext(patch.object(spatial_audio, "p", Mock()))
        self.backend.Mix_QuerySpec.return_value = 1
        self.chunks = [SimpleNamespace(contents=SimpleNamespace(alen=256)) for _ in self.paths]
        self.backend.Mix_LoadWAV.side_effect = self.chunks
        self.backend.Mix_AllocateChannels.side_effect = lambda size: 8 if size == -1 else size
        self.backend.Mix_ReserveChannels.side_effect = lambda size: size
        self.backend.Mix_Volume.return_value = 128
        self.backend.Mix_PlayChannelTimed.side_effect = lambda channel, *_: channel
        self.music = spatial_audio.BackgroundMusic(self.paths[0], layers=self.paths[1:])
        self.addCleanup(self.music.close)

    def test_approach_chase_and_release_mix_the_running_layers(self):
        self.music.start()
        self.assertEqual(self.music._score._volumes, (30, 0, 0))
        self.music.update(.09, distance=70)
        self.assertTrue(0 < self.music._score._volumes[1] < 23)
        self.music.update(4, distance=70)
        self.assertEqual(self.music._score._volumes, (20, 24, 0))
        self.music.update(4, distance=200, chasing=True)
        self.assertEqual(self.music._score._volumes, (16, 14, 38))
        self.music.update(.1, distance=200)
        self.assertTrue(0 < self.music._score._volumes[2] < 38)
        self.music.update(8, distance=200)
        self.assertEqual(self.music._score._volumes, (30, 0, 0))
        self.music.update(4, distance=70, chasing=True)
        self.music.reset()
        self.assertEqual(self.music._score._volumes, (30, 0, 0))
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_args_list,
                         [call(index, chunk, -1, -1) for index, chunk in enumerate(self.chunks)])

    def test_delivery_pressure_rises_then_relief_fades_without_pausing_or_restarting_layers(self):
        self.music.start()
        self.music.update(.28, threat=1, combat=0)
        self.assertEqual(self.music._score._volumes, (24, 15, 0))
        self.music.update(4, threat=.4, combat=1)
        self.assertEqual(self.music._score._volumes, (16, 14, 38))
        self.music.update(.45, relief=True, threat=1, combat=1)
        fade_start = self.music._score._volumes
        self.assertTrue(all(0 < volume < old for volume, old in zip(fade_start, (16, 14, 38))))
        self.backend.Mix_Pause.assert_not_called()
        self.music.update(1.5, relief=True, focused=False)
        self.assertEqual(self.music._score._volumes, fade_start)
        self.music.update(1.25, relief=True)
        self.assertEqual(self.music._score._volumes, (0, 0, 0))
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_count, 3)
        self.music.reset()
        self.assertEqual(self.music._score._volumes, (30, 0, 0))

    def test_pause_resume_and_close_preserve_channel_ownership(self):
        self.music.start()
        for focused in (False, False, True, True):
            self.music.update(0, focused=focused)
        channels = [call(index) for index in range(3)]
        self.assertEqual(self.backend.Mix_Pause.call_args_list, channels)
        self.assertEqual(self.backend.Mix_Resume.call_args_list, channels)
        self.music.close()
        self.music.close()
        self.assertEqual(self.backend.Mix_HaltChannel.call_args_list, channels)
        self.assertEqual(self.backend.Mix_FreeChunk.call_args_list, [call(chunk) for chunk in self.chunks])
        self.assertEqual(self.backend.Mix_AllocateChannels.call_args_list, [call(-1), call(11), call(8)])
        self.assertEqual(self.backend.Mix_ReserveChannels.call_args_list, [call(3), call(0)])

    def test_stem_gains_change_while_paused_without_restarting_layers(self):
        settings = spatial_audio.AudioSettings(master=50)
        music = spatial_audio.BackgroundMusic(self.paths[0], layers=self.paths[1:], settings=settings)
        self.addCleanup(music.close)
        music.start()
        self.assertEqual(music._score._volumes, (15, 0, 0))
        music.update(4, distance=70, chasing=True)
        scaled_chase = music._score._volumes
        settings.music = 0
        music.update(.05, focused=False, distance=200)
        self.assertEqual(music._score._volumes, (0, 0, 0))
        settings.music = 100
        music.update(0, focused=True)
        self.assertEqual(music._score._volumes, scaled_chase)
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_count, 3)

    def test_mismatched_stems_release_chunks_and_fall_back_to_base_music(self):
        self.chunks[-1].contents.alen = 240
        self.backend.Mix_PlayMusic.return_value = 0
        self.music.start()
        self.backend.Mix_PlayChannelTimed.assert_not_called()
        self.backend.Mix_AllocateChannels.assert_not_called()
        self.assertEqual(self.backend.Mix_FreeChunk.call_args_list, [call(chunk) for chunk in self.chunks])
        self.backend.Mix_LoadMUS.assert_called_once_with(str(self.paths[0]).encode("utf-8"))
        self.backend.Mix_PlayMusic.assert_called_once_with(self.backend.Mix_LoadMUS.return_value, -1)

    def test_failed_layer_start_restores_effect_channel_volumes(self):
        self.backend.Mix_PlayChannelTimed.side_effect = [0, 1, -1]
        self.backend.Mix_PlayMusic.return_value = 0
        self.music.start()
        self.assertEqual(self.backend.Mix_HaltChannel.call_args_list, [call(0), call(1)])
        self.assertEqual(self.backend.Mix_Volume.call_args_list[-3:], [call(n, 128) for n in range(3)])
        self.assertEqual(self.backend.Mix_FreeChunk.call_args_list, [call(chunk) for chunk in self.chunks])
        self.backend.Mix_ReserveChannels.assert_called_with(0)
        self.backend.Mix_PlayMusic.assert_called_once()


class ZombieAudioTests(unittest.TestCase):
    def setUp(self):
        self.backend = self.enterContext(patch.object(spatial_audio, "p", Mock()))
        self.backend.Mix_QuerySpec.return_value = 1
        names = ("zombie_step", "zombie_step_heavy", "zombie_groan", "bat_swing", "zombie_hit", "zombie_hit_heavy",
                 "player_walk", "player_run", "player_sneak", "player_hit",
                 "parcel_pickup", "parcel_drop", "bottle_pickup", "map_rustle",
                 "bottle_break", "gate_open", "bridge_motor", "vehicle_alarm", "truck_arrive")
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

    def test_bridge_motor_plays_once_with_distance_and_panning(self):
        motor = self.sounds["bridge_motor"]
        self.audio.play_bridge_motor(520, pan=-1.0)
        self.backend.Mix_PlayChannelTimed.assert_not_called()
        self.audio.play_bridge_motor(260, pan=-1.0)
        self.backend.Mix_VolumeChunk.assert_called_once_with(motor, 43)
        self.backend.Mix_PlayChannelTimed.assert_called_once_with(-1, motor, 0, -1)
        self.backend.Mix_SetPanning.assert_called_once_with(0, 255, 80)

    def test_corner_steps_follow_the_patrol_even_when_a_closer_zombie_is_still(self):
        step, groan = self.sounds["zombie_step"], self.sounds["zombie_groan"]
        far = spatial_audio.PatrolFootstep(170, 32, -.9, True)
        near = spatial_audio.PatrolFootstep(75, 32, -.6, True)
        self.backend.Mix_PlayChannelTimed.side_effect = range(5)
        self.backend.Mix_Playing.return_value = False
        self.audio.update(.4, distance=30, stride=0, active=True, pan=1.0, patrol_step=far)
        self.audio.update(.7, distance=30, stride=0, active=True, pan=1.0, patrol_step=near)
        self.audio.update(.7, distance=30, stride=0, active=True, pan=1.0, patrol_step=far)
        self.audio.update(.7, distance=30, stride=0, active=True, pan=1.0)
        calls = self.backend.Mix_VolumeChunk.call_args_list
        step_gains = [gain for sound, gain in (entry.args for entry in calls) if sound == step]
        self.assertEqual(len(step_gains), 3)
        self.assertGreater(step_gains[1], step_gains[0] * 2)
        self.assertEqual(step_gains[2], step_gains[0])
        self.assertIn(call(groan, 57), calls)
        self.assertEqual(self.backend.Mix_SetPanning.call_args_list,
                         [call(0, 255, 98), call(1, 80, 255), call(2, 255, 150), call(3, 255, 98)])

    def test_heavy_steps_keep_their_own_stride_distance_and_pan_behind_a_wall(self):
        heavy, regular = self.sounds["zombie_step_heavy"], self.sounds["zombie_step"]
        half_step = spatial_audio.HeavyFootstep(260, 18, .8, True)
        self.audio.update(.1, distance=100, stride=0, active=True, heavy_step=half_step)
        self.backend.Mix_PlayChannelTimed.assert_not_called()
        self.audio.update(.1, distance=100, stride=32, active=True, pan=-1, heavy_step=half_step)
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_args_list,
                         [call(-1, heavy, 0, -1), call(-1, regular, 0, -1)])
        self.assertEqual(self.backend.Mix_VolumeChunk.call_args_list, [call(heavy, 25), call(regular, 39)])
        self.assertEqual(self.backend.Mix_SetPanning.call_args_list, [call(0, 115, 255), call(1, 255, 80)])

    def test_heavy_steps_play_without_regular_zombies_and_stop_on_pause_or_leave(self):
        sound = self.sounds["zombie_step_heavy"]
        self.backend.Mix_GetChunk.return_value = sound
        self.audio.update(.1, distance=None, stride=0, active=True,
                          heavy_step=spatial_audio.HeavyFootstep(100, 36, 0.0, False))
        self.backend.Mix_PlayChannelTimed.assert_called_once_with(-1, sound, 0, -1)
        self.backend.Mix_HaltChannel.assert_not_called()
        self.audio.update(.1, distance=None, stride=0, active=False, preserve_map_cue=True)
        self.backend.Mix_HaltChannel.assert_called_once_with(0)

        self.audio.update(.1, distance=None, stride=0, active=True,
                          heavy_step=spatial_audio.HeavyFootstep(100, 36, 0.0, False))
        self.audio.update(.1, distance=None, stride=0, active=True,
                          heavy_step=spatial_audio.HeavyFootstep(520, 36, 0.0, False))
        self.assertEqual(self.backend.Mix_HaltChannel.call_args_list, [call(0), call(1)])
        self.audio.update(.1, distance=None, stride=0, active=True,
                          heavy_step=spatial_audio.HeavyFootstep(100, 35, 0.0, False))
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_count, 2)

    def test_opposite_shared_steps_accumulate_per_source_and_update_per_channel(self):
        self.backend.Mix_PlayChannelTimed.side_effect = [3, 4]
        step = self.sounds["zombie_step"]
        self.backend.Mix_GetChunk.return_value = step
        left = spatial_audio.ZombieFootstep(10, 60, 16, -1, True)
        right = spatial_audio.ZombieFootstep(20, 260, 16, 1)

        def update(*sources, active=True):
            self.audio.update(.03, distance=None, stride=0, active=active, footstep_sources=sources)

        update(left, right)
        self.backend.Mix_PlayChannelTimed.assert_not_called()
        self.backend.Mix_VolumeChunk.reset_mock()
        update(left, right)
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_args_list, [call(-1, step, 0, -1)] * 2)
        self.assertEqual(self.backend.Mix_SetPanning.call_args_list, [call(3, 255, 80), call(4, 80, 255)])
        self.assertEqual(self.backend.Mix_Volume.call_args_list, [call(3, 28), call(4, 24)])
        update(left, spatial_audio.ZombieFootstep(20, 390, 0, 1))
        self.assertEqual(self.backend.Mix_Volume.call_args_list[-2:], [call(3, 28), call(4, 12)])
        self.backend.Mix_VolumeChunk.assert_not_called()
        update(active=False)
        self.assertEqual(self.backend.Mix_HaltChannel.call_args_list, [call(3), call(4)])

    def test_reused_channel_has_one_owner_and_resets_gain_and_pan_for_effects(self):
        step = self.sounds["zombie_step"]
        self.backend.Mix_GetChunk.return_value = step
        self.backend.Mix_PlayChannelTimed.side_effect = [3, 3, 3]
        left = spatial_audio.ZombieFootstep(10, 260, 32, -1)
        right = spatial_audio.ZombieFootstep(20, 390, 32, 1)

        def update(*sources):
            self.audio.update(.03, distance=None, stride=0, active=True, footstep_sources=sources)

        update(left, spatial_audio.ZombieFootstep(20, 390, 0, 1))
        self.backend.Mix_Playing.return_value = False
        update(right, spatial_audio.ZombieFootstep(10, 260, 0, -1))
        self.backend.Mix_Playing.return_value = True
        update(right)
        self.backend.Mix_HaltChannel.assert_not_called()
        self.assertEqual(self.audio._channels, {("zombie_step", 20): 3})
        self.audio.play_bat_swing()
        self.assertEqual(self.audio._channels, {"bat_swing": 3})
        self.backend.Mix_Volume.assert_called_with(3, 128)
        self.backend.Mix_SetPanning.assert_called_with(3, 255, 255)

    def test_a_stopped_source_finishes_its_step_until_the_same_side_is_replaced(self):
        self.backend.Mix_PlayChannelTimed.side_effect = [3, 4, 5]
        self.backend.Mix_GetChunk.return_value = self.sounds["zombie_step"]

        def update(*sources):
            self.audio.update(.03, distance=None, stride=0, active=True, footstep_sources=sources)

        left = spatial_audio.ZombieFootstep(10, 60, 32, -1)
        right = spatial_audio.ZombieFootstep(20, 60, 32, 1)
        replacement = spatial_audio.ZombieFootstep(30, 90, 16, -.7)
        update(left)
        update()
        update(right, replacement)
        update()
        self.backend.Mix_HaltChannel.assert_not_called()
        update(replacement)
        self.backend.Mix_HaltChannel.assert_called_once_with(3)
        self.assertEqual(set(self.audio._channels.values()), {4, 5})

    def test_directional_patrol_and_heavy_keep_distinct_spacings_and_wall_gain(self):
        self.backend.Mix_PlayChannelTimed.side_effect = [3, 4]
        patrol = spatial_audio.ZombieFootstep(10, 110, 16, -.9, True, "patrol")
        heavy = spatial_audio.ZombieFootstep(20, 260, 18, .8, True, "heavy")
        for _ in range(2):
            self.audio.update(.03, distance=None, stride=0, active=True, footstep_sources=(patrol, heavy))
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_args_list,
                         [call(-1, self.sounds[name], 0, -1) for name in ("zombie_step", "zombie_step_heavy")])
        self.assertEqual(self.backend.Mix_Volume.call_args_list, [call(3, 31), call(4, 25)])
        self.assertEqual(self.backend.Mix_SetPanning.call_args_list, [call(3, 255, 98), call(4, 115, 255)])

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

    def test_heavy_zombie_hit_uses_the_low_impact_clip(self):
        hit = self.sounds["zombie_hit_heavy"]
        self.audio.play_zombie_hit(heavy=True)
        self.backend.Mix_VolumeChunk.assert_called_once_with(hit, 88)
        self.backend.Mix_PlayChannelTimed.assert_called_once_with(-1, hit, 0, -1)

    def test_effect_gain_scales_one_shots_and_can_mute_spatial_steps(self):
        settings = spatial_audio.AudioSettings(master=50, music=0, effects=50)
        audio = spatial_audio.ZombieAudio(Path("sounds"), settings=settings)
        audio.play_parcel_pickup()
        self.backend.Mix_VolumeChunk.assert_called_once_with(self.sounds["parcel_pickup"], 10)
        settings.effects = 0
        audio.update(.01, distance=20, stride=32, active=True)
        self.backend.Mix_VolumeChunk.assert_called_with(self.sounds["zombie_step"], 0)

    def test_player_gaits_use_distinct_distance_and_volume(self):
        self.backend.Mix_PlayChannelTimed.side_effect = (0, 1, 2)
        for kind, sprinting, sneaking, distance, volume in (
            ("player_walk", False, False, 32, 34),
            ("player_run", True, False, 48, 50),
            ("player_sneak", True, True, 32, 16),
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

    def test_truck_cue_survives_the_scene_freeze_and_stops_on_pause(self):
        arrive, swing = self.sounds["truck_arrive"], self.sounds["bat_swing"]
        self.backend.Mix_GetChunk.side_effect = [swing, arrive]
        self.audio.play_truck_cue("arriving", 260, pan=1.0)
        self.audio.play_bat_swing()
        self.assertEqual(self.backend.Mix_PlayChannelTimed.call_args_list,
                         [call(-1, arrive, 0, -1), call(-1, swing, 0, -1)])
        self.assertEqual(self.backend.Mix_VolumeChunk.call_args_list, [call(arrive, 39), call(swing, 74)])
        self.audio.update(0, distance=None, stride=0, active=False, preserve_truck_cues=True)
        self.backend.Mix_HaltChannel.assert_called_once_with(1)
        self.audio.update(0, distance=None, stride=0, active=False)
        self.assertEqual(self.backend.Mix_HaltChannel.call_args_list, [call(1), call(0)])


if __name__ == "__main__":
    unittest.main()
