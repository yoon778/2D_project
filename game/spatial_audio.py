"""Distance-based zombie sounds, independent of flashlight visibility."""
from math import hypot
from pathlib import Path


class SpatialAudio:
    hearing_range = 520.0
    channels = {"zombie_step": 6, "zombie_groan": 7}
    maximum_volume = {"zombie_step": 48, "zombie_groan": 60}

    def __init__(self, p, base_dir):
        self.p = p
        self.enabled = bool(p.audio_on)
        self.sounds = {}
        self._active = set()
        self._player = None
        self._allowed = False
        if self.enabled:
            # Automatic player effects use channels 8..15; zombie channels stay
            # independent, so one source's gain cannot alter another sound.
            p.Mix_AllocateChannels(max(16, p.Mix_AllocateChannels(-1)))
            p.Mix_ReserveChannels(8)
            for kind in self.channels:
                self.sounds[kind] = p.load_wav(
                    str(Path(base_dir) / "assets" / "audio" / (kind + ".wav"))
                )

    def volume(self, kind, distance):
        return round(self.maximum_volume[kind] * max(0.0, 1.0 - distance / self.hearing_range))

    def play(self, kind, x, y, listener_x, listener_y):
        if not self.enabled or not self._allowed or kind not in self.channels:
            return False
        gain = self.volume(kind, hypot(x - listener_x, y - listener_y))
        if gain <= 0:
            return False
        channel = self.channels[kind]
        if kind in self._active and self.p.Mix_Playing(channel):
            return False
        self.p.Mix_Volume(channel, gain)
        if self.p.Mix_PlayChannelTimed(channel, self.sounds[kind].wav, 0, -1) < 0:
            return False
        self._active.add(kind)
        return True

    def update(self, game, focused=True):
        if not self.enabled:
            return
        if self._player is not game.player:
            self.stop()
            self._player = game.player
        self._allowed = bool(focused and game.state == "playing"
                             and game.player.hp > 0 and game.zombie.hp > 0)
        if not self._allowed:
            self.stop()
            return
        distance = hypot(game.zombie.x - game.player.x, game.zombie.y - game.player.y)
        for kind in tuple(self._active):
            channel = self.channels[kind]
            if not self.p.Mix_Playing(channel):
                self._active.remove(kind)
                continue
            gain = self.volume(kind, distance)
            if gain <= 0:
                self.p.Mix_HaltChannel(channel)
                self._active.remove(kind)
            else:
                self.p.Mix_Volume(channel, gain)

    def stop(self):
        if self.enabled:
            for kind in self._active:
                self.p.Mix_HaltChannel(self.channels[kind])
        self._active.clear()

    def reset(self):
        self.stop()
        self._player = None
        self._allowed = False

    def close(self):
        self.reset()
        self.sounds.clear()
        self.enabled = False
