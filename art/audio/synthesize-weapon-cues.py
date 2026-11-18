"""Bake weapon and shelter supply sounds."""
from array import array
from math import exp, sin, tau
from pathlib import Path
from random import Random
import wave


RATE = 44100
DESTINATION = Path(__file__).resolve().parents[2] / "game/assets/audio"


def pulse(time, start, decay):
    age = time - start
    if age <= 0:
        return 0.0
    return min(1.0, age / .002) * exp(-age / decay)


def generate(duration, seed, sample):
    rng = Random(seed)
    smooth = 0.0
    for index in range(round(duration * RATE)):
        time = index / RATE
        noise = rng.uniform(-1, 1)
        smooth += .14 * (noise - smooth)
        yield sample(time, smooth, noise - smooth)


def bat_crack(time, low, high):
    snap = pulse(time, 0, .012) + .62 * pulse(time, .022, .018)
    wood = .32 * sin(tau * 330 * time) + .20 * sin(tau * 503 * time)
    return snap * (.44 * high + .33 * low) + pulse(time, 0, .032) * wood


def fist_contact(time, low, high):
    thud = .72 * sin(tau * 107 * time) + .26 * sin(tau * 174 * time) + .5 * low
    return pulse(time, 0, .019) * thud + .13 * pulse(time, .002, .007) * high


def cabinet_open(time, low, high):
    latch = pulse(time, .012, .016)
    slide = pulse(time, .066, .046) * (1 + .25 * sin(tau * 31 * time))
    stop = pulse(time, .172, .025)
    metal = .24 * sin(tau * 605 * time) + .17 * sin(tau * 933 * time)
    return latch * (.32 * high + metal) + slide * (.38 * low + .22 * high) + stop * (.42 * low + metal)


def write(name, samples):
    values = list(samples)
    gain = 25000 / max(map(abs, values))
    with wave.open(str(DESTINATION / f"{name}.wav"), "wb") as audio:
        audio.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        audio.writeframes(array("h", (round(value * gain) for value in values)).tobytes())


if __name__ == "__main__":
    write("bat_break", generate(.17, 423, bat_crack))
    write("fist_hit", generate(.13, 258, fist_contact))
    write("cabinet_open", generate(.29, 1907, cabinet_open))
