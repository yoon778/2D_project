"""Synthesize the heavy zombie's boot impact and breathy groan."""
from array import array
from math import cos, exp, pi, sin, tau, tanh
from pathlib import Path
from random import Random
import sys
import wave


RATE = 44100


class BandPass:
    def __init__(self, frequency, resonance):
        angle = tau * frequency / RATE
        alpha = sin(angle) / (2 * resonance)
        self.gain = alpha / (1 + alpha)
        self.a1 = -2 * cos(angle) / (1 + alpha)
        self.a2 = (1 - alpha) / (1 + alpha)
        self.z1 = self.z2 = 0.0

    def step(self, value):
        output = self.gain * value + self.z1
        self.z1 = self.z2 - self.a1 * output
        self.z2 = -self.gain * value - self.a2 * output
        return output


def ramp(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3 - 2 * value)


def swell(time, start, attack, end, release):
    return ramp((time - start) / attack) * ramp((end - time) / release)


def burst(age, attack, decay):
    return ramp(age / attack) * exp(-max(0.0, age) / decay)


def heavy_step():
    rng = Random(1996)
    sole = BandPass(317, .75)
    gravel = BandPass(1750, .68)
    tread = BandPass(3250, .85)
    for frame in range(round(.31 * RATE)):
        time = frame / RATE
        noise = rng.uniform(-1, 1)
        pressure, grit, rubber = sole.step(noise), gravel.step(noise), tread.step(noise)
        heel = time - .004
        toe = time - .054
        contact = (.33 * sin(tau * 75 * heel) + .20 * sin(tau * 119 * heel)
                   + .13 * sin(tau * 188 * heel)) * burst(heel, .004, .038)
        weight = (.94 * pressure + .18 * grit + .06 * rubber) * burst(heel, .003, .029)
        shift = (.70 * pressure + .135 * grit) * burst(toe, .004, .022)
        drag = (.224 * grit + .134 * rubber) * swell(time, .033, .035, .165, .075)
        yield (contact + weight + shift + drag) * ramp((.31 - time) / .030)


def heavy_groan():
    rng = Random(3272)
    chest = BandPass(126, 1.0)
    throat = BandPass(342, 3.0)
    mouth = BandPass(548, 3.8)
    voice_edge = BandPass(1040, 3.2)
    rasp = BandPass(970, .9)
    air = BandPass(2160, 1.1)
    phase, previous, pressure = 0.0, 0.0, 1.0
    for frame in range(round(1.12 * RATE)):
        time = frame / RATE
        pitch = (54 - 10 * time + 11 * exp(-((time - .37) / .19) ** 2)
                 + 3.2 * sin(tau * 6.7 * time) + 1.1 * sin(tau * 19 * time))
        phase += pitch / RATE
        if phase >= 1.0:
            phase -= 1.0
            pressure = rng.uniform(.51, 1.21)
        if phase < .57:
            pulse = .5 - .5 * cos(pi * phase / .57)
        else:
            pulse = .5 + .5 * cos(pi * min(1.0, (phase - .57) / .18))
        source = (pulse - previous) * 71 * pressure
        previous = pulse
        noise = rng.uniform(-1, 1)
        open_mouth = swell(time, .20, .25, .89, .32)
        voiced = (1.2 * chest.step(source) + .68 * throat.step(source)
                  + (.20 + .72 * open_mouth) * mouth.step(source) + .25 * voice_edge.step(source))
        breath = .58 * rasp.step(noise) + .25 * air.step(noise)
        growl = swell(time, .094, .17, .99, .22) * (.76 + .24 * sin(tau * 4.8 * time))
        exhale = .23 * swell(time, .005, .065, .30, .12) + .37 * swell(time, .74, .14, 1.11, .15)
        yield tanh(1.2 * (growl * (voiced + .45 * breath) + exhale * breath))


def write_cue(directory, name, signal, peak):
    samples = list(signal)
    gain = peak / max(map(abs, samples))
    pcm = array('h', (round(gain * value) for value in samples))
    if sys.byteorder != 'little':
        pcm.byteswap()
    with wave.open(str(directory / f'{name}.wav'), 'wb') as wav:
        wav.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        wav.writeframes(pcm.tobytes())


def main():
    assets = Path(__file__).resolve().parents[2] / 'game/assets/audio'
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else assets
    write_cue(destination, 'zombie_step_heavy', heavy_step(), 15850)
    write_cue(destination, 'zombie_groan_heavy', heavy_groan(), 15400)


if __name__ == '__main__':
    main()
