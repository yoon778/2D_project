"""Synthesize the iron gate opening cue."""
from array import array
from math import cos, exp, sin, tau
from pathlib import Path
from random import Random
import sys
import wave


RATE = 44100
DURATION = .90
PEAK = 22000


class BandPass:
    def __init__(self, frequency, resonance):
        angle = tau * frequency / RATE
        damping = sin(angle) / (2 * resonance)
        self.b0 = damping / (1 + damping)
        self.a1 = -2 * cos(angle) / (1 + damping)
        self.a2 = (1 - damping) / (1 + damping)
        self.z1 = self.z2 = 0.0

    def step(self, sample):
        result = self.b0 * sample + self.z1
        self.z1 = self.z2 - self.a1 * result
        self.z2 = -self.b0 * sample - self.a2 * result
        return result


def ramp(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def ring(age, partials):
    if age <= 0:
        return 0.0
    return ramp(age / .0017) * sum(level * sin(tau * hz * age) * exp(-age / decay)
                                   for hz, level, decay in partials)


def synthesize():
    random = Random(4810)
    friction = BandPass(550, .68)
    scrape = BandPass(2575, .87)
    latch_modes = ((826, .37, .018), (1541, .32, .012), (2557, .25, .010), (3954, .17, .006))
    stop_modes = ((101, .46, .041), (183, .35, .055), (311, .27, .039), (617, .16, .075),
                  (1149, .12, .043), (1978, .08, .024), (3244, .095, .011))
    motion_start, motion_end = .066, .648
    phase = 0.0
    signal = []

    for frame in range(round(DURATION * RATE)):
        time = frame / RATE
        noise = random.uniform(-1, 1)
        body = friction.step(noise)
        grit = scrape.step(noise)

        latch = .45 * ring(time - .009, latch_modes) + .23 * ring(time - .042, latch_modes)

        travel = ramp((time - motion_start) / .097) * ramp((motion_end - time) / .068)
        stick_slip = .63 + .22 * sin(tau * 7.3 * time) + .15 * sin(tau * 11.1 * time + .7)
        phase += tau * (465 + 205 * travel + 47 * sin(tau * 3.4 * time)) / RATE
        hinge = (.27 * sin(phase) + .10 * sin(2.13 * phase + .7 * sin(tau * 12.3 * time)))
        moving_gate = travel * (stick_slip * (hinge + .66 * body) + .40 * grit)
        loose_bars = .10 * ring(time - .262, latch_modes) + .13 * ring(time - .519, latch_modes)

        stop = .68 * ring(time - .655, stop_modes) + .13 * ring(time - .696, latch_modes)
        signal.append((latch + moving_gate + loose_bars + stop) * ramp((DURATION - time) / .038))

    gain = PEAK / max(map(abs, signal))
    return array('h', (round(gain * sample) for sample in signal))


def main():
    default = Path(__file__).resolve().parents[2] / 'game/assets/audio/gate_open.wav'
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    samples = synthesize()
    if sys.byteorder != 'little':
        samples.byteswap()
    with wave.open(str(destination), 'wb') as sound:
        sound.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        sound.writeframes(samples.tobytes())


if __name__ == '__main__':
    main()
