"""Render original cardboard and paper effects for Dead Route."""
from array import array
from math import cos, exp, pi, sin, tau
from pathlib import Path
from random import Random
import sys
import wave


RATE = 44100


def rub(time, start, length, swell):
    phase = (time - start) / length
    if not 0 < phase < 1:
        return 0.0
    return sin(pi * phase) ** swell


def contact(time, start, pitch, decay):
    age = time - start
    if age <= 0:
        return 0.0
    attack = min(1.0, age / .004)
    body = sin(tau * pitch * age) + .48 * sin(tau * pitch * 1.79 * age)
    return attack * exp(-age / decay) * body


def parcel_pickup(t, paper, rubbing, body):
    grip = rub(t, .005, .115, 1.4)
    slide = rub(t, .056, .19, .8) * (.68 + .32 * cos(tau * 13 * t))
    return (.55 * rubbing + .22 * paper) * grip + (.62 * rubbing + .45 * body) * slide


def parcel_drop(t, paper, rubbing, body):
    box = .50 * contact(t, .009, 126, .034) + .16 * contact(t, .063, 179, .021)
    hit = (.42 * rubbing + .85 * body) * rub(t, .009, .055, .63)
    settle = (.32 * paper + .74 * rubbing) * rub(t, .047, .20, 1.3)
    return box + hit + settle


def map_rustle(t, paper, rubbing, _body):
    unfold = rub(t, .004, .125, 1.4) + rub(t, .093, .126, 1.15)
    flatten = rub(t, .177, .118, .88)
    flutter = .78 + .22 * cos(tau * 31 * t + .13)
    return (.63 * paper + .24 * rubbing) * unfold * flutter + (.31 * paper + .46 * rubbing) * flatten


def make_sound(directory, name, duration, peak, shape):
    random = Random(name)
    high = middle = low = 0.0
    signal = []
    total_frames = round(duration * RATE)
    for frame in range(total_frames):
        time = frame / RATE
        noise = random.uniform(-1, 1)
        high += .43 * (noise - high)
        middle += .13 * (noise - middle)
        low += .034 * (noise - low)
        tail = min(1.0, (total_frames - 1 - frame) / (.015 * RATE))
        signal.append(tail * shape(time, high - middle, middle - low, low))
    gain = peak * 32767 / max(map(abs, signal))
    pcm = array('h', (round(value * gain) for value in signal))
    if sys.byteorder != 'little':
        pcm.byteswap()
    with wave.open(str(directory / f'{name}.wav'), 'wb') as output:
        output.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        output.writeframes(pcm.tobytes())


def main():
    default = Path(__file__).resolve().parents[2] / 'game/assets/audio'
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    make_sound(directory, 'parcel_pickup', .26, .58, parcel_pickup)
    make_sound(directory, 'parcel_drop', .31, .67, parcel_drop)
    make_sound(directory, 'map_rustle', .30, .44, map_rustle)


if __name__ == '__main__':
    main()
