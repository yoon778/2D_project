"""Synthesize the bottle pickup and roll-up shutter closing cues."""
from array import array
from math import exp, sin, tau
from pathlib import Path
from random import Random
import sys
import wave


RATE = 44100


def ramp(value):
    fraction = min(1.0, max(0.0, value))
    return fraction * fraction * (3.0 - 2.0 * fraction)


def damped_modes(age, modes, attack=.001):
    if age <= 0:
        return 0.0
    return ramp(age / attack) * sum(gain * sin(tau * pitch * age) * exp(-age / decay)
                                    for pitch, gain, decay in modes)


def bottle_pickup():
    duration = .24
    random = Random(134)
    contact = ((1320, .13, .031), (1780, .53, .027), (3090, .31, .017), (4620, .23, .012))
    settle = ((1550, .12, .039), (2090, .21, .033), (3830, .09, .019))
    previous = fabric = 0.0
    for frame in range(round(duration * RATE)):
        time = frame / RATE
        noise = random.uniform(-1, 1)
        grain = noise - previous
        previous = noise
        fabric += .15 * (noise - fabric)
        scrape = .12 * grain * ramp(time / .008) * ramp((.038 - time) / .025)
        grip = .33 * fabric * ramp((time - .042) / .016) * ramp((.14 - time) / .046)
        clinks = damped_modes(time - .017, contact) + damped_modes(time - .076, settle)
        yield (scrape + grip + clinks) * ramp((duration - time) / .029)


def shutter_close():
    duration = .90
    random = Random(520)
    slats = ((337, .21, .025), (763, .22, .029), (1260, .15, .016), (2400, .09, .009))
    stop = ((78, .66, .045), (143, .49, .047), (257, .26, .065), (630, .20, .050),
            (1120, .17, .029), (1790, .10, .014))
    slat_times = (.081, .159, .226, .285, .338, .387, .433, .476, .519, .560, .601, .642)
    previous = track = phase = 0.0
    slat_index = 0
    for frame in range(round(duration * RATE)):
        time = frame / RATE
        noise = random.uniform(-1, 1)
        edge = noise - previous
        previous = noise
        track += .09 * (noise - track)
        motion = ramp((time - .044) / .064) * ramp((.695 - time) / .041)
        phase += tau * (58 + 35 * ramp((time - .06) / .53)) / RATE
        chatter = .72 + .28 * sin(phase)
        roll = motion * ((.27 * sin(phase) + .13 * sin(2 * phase) + .60 * track) * chatter + .094 * edge)
        if slat_index + 1 < len(slat_times) and time >= slat_times[slat_index + 1]:
            slat_index += 1
        rattle = damped_modes(time - slat_times[slat_index], slats)
        closing = damped_modes(time - .688, stop, attack=.0028)
        yield (roll + .9 * rattle + closing) * ramp((duration - time) / .045)


def main():
    assets = Path(__file__).resolve().parents[2] / 'game/assets/audio'
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else assets
    for name, render, peak in (('bottle_pickup', bottle_pickup, 16000),
                               ('shutter_close', shutter_close, 18750)):
        signal = list(render())
        gain = peak / max(map(abs, signal))
        samples = array('h', (round(gain * sample) for sample in signal))
        if sys.byteorder != 'little':
            samples.byteswap()
        with wave.open(str(destination / f'{name}.wav'), 'wb') as sound:
            sound.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            sound.writeframes(samples.tobytes())


if __name__ == '__main__':
    main()
