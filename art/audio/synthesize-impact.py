"""Synthesize the bat impacts for the regular and heavy zombies."""
from array import array
from math import cos, exp, pi, sin, tanh
from pathlib import Path
from random import Random
import sys
import wave

RATE = 44100
TAU = 2 * pi


class BandPass:
    def __init__(self, center, q):
        omega = TAU * center / RATE
        alpha = sin(omega) / (2 * q)
        self.b0 = alpha / (1 + alpha)
        self.a1 = -2 * cos(omega) / (1 + alpha)
        self.a2 = (1 - alpha) / (1 + alpha)
        self.z1 = self.z2 = 0.0

    def step(self, value):
        result = self.b0 * value + self.z1
        self.z1 = -self.a1 * result + self.z2
        self.z2 = -self.b0 * value - self.a2 * result
        return result


def smoothstep(value):
    p = min(1.0, max(0.0, value))
    return p * p * (3.0 - 2.0 * p)


def burst(age, rise, decay):
    return smoothstep(age / rise) * exp(-max(0.0, age) / decay)


def resonances(age, partials):
    if age <= 0.0:
        return 0.0
    return sum(weight * sin(TAU * pitch * age + phase) * exp(-age / decay)
               for pitch, weight, phase, decay in partials)


def render(*, heavy):
    duration = .310 if heavy else .230
    peak = 20550 if heavy else 18500
    rng = Random(106011 if heavy else 106010)
    edge = BandPass(2290 if heavy else 2780, 0.76)
    pressure = BandPass(119 if heavy else 212, 0.78)
    cloth = BandPass(496 if heavy else 640, 0.8)
    wood_modes = ((942, .31, .5, .0048), (1512, .28, -.4, .0064),
                  (2270, .17, .22, .0043), (3450, .07, -.15, .0020))
    body_modes = ((76, .48, .05, .053), (116, .28, .68, .042),
                  (171, .20, -.24, .033), (230, .12, .15, .022)) if heavy else (
                  (119, .38, .06, .028), (202, .25, .48, .022),
                  (271, .17, -.27, .015), (359, .087, .12, .010))
    body_gain = 1.06 if heavy else .90
    edge_gain = 1.38 if heavy else 1.49
    drive = 1.34 if heavy else 1.36
    signal = []
    previous_input = previous_output = 0.0
    highpass = exp(-TAU * 24 / RATE)
    for frame in range(round(duration * RATE)):
        t = frame / RATE
        noise = rng.uniform(-1.0, 1.0)
        edge_noise = edge.step(noise)
        body_noise = pressure.step(noise)
        cloth_noise = cloth.step(noise)
        wood = (.66 * edge_noise * burst(t - .0003, .0006, .0038)
                + resonances(t - .0003, wood_modes) * smoothstep((t - .0003) / .00072))
        wood *= smoothstep((.016 - t) / .006)
        body_age = t - .0016
        body = (resonances(body_age, body_modes) * smoothstep(body_age / .0028)
                + .64 * body_noise * burst(body_age, .0049, .041 if heavy else .018))
        reaction = .46 * cloth_noise * burst(t - .0105, .005, .032 if heavy else .016)
        reaction *= smoothstep(((.125 if heavy else .092) - t) / .030)
        value = tanh(drive * (edge_gain * wood + body_gain * body + reaction))
        previous_output = highpass * (previous_output + value - previous_input)
        previous_input = value
        signal.append(previous_output * smoothstep((duration - t) / .018))
    reference = max(map(abs, signal))
    return array('h', (round(peak * sample / reference) for sample in signal))


def main():
    assets = Path(__file__).resolve().parents[2] / 'game/assets/audio'
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else assets
    for name, heavy in (('zombie_hit', False), ('zombie_hit_heavy', True)):
        samples = render(heavy=heavy)
        if sys.byteorder != 'little':
            samples.byteswap()
        with wave.open(str(destination / f'{name}.wav'), 'wb') as sound:
            sound.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            sound.writeframes(samples.tobytes())


if __name__ == '__main__':
    main()
