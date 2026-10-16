"""Does the gate open on a keyboard? EnergyGate against VoiceGate (#4).

    venv\\Scripts\\python.exe gatebench.py

Three questions, asked of each gate through the real Segmenter:

  keys      keyboard recordings and nothing else. Every utterance cut here is
            a stretch of clatter handed to Whisper -- the thing #4 is about.
  speech    the Kokoro samples in samples/*.wav, alone in a quiet room. How
            much of the speech ends up inside an utterance (it must not drop).
  both      the same speech laid over the keyboard recordings: speech kept,
            and utterances cut where nobody was talking.

The keyboard recordings are public domain, from Wikimedia Commons, and are
not committed. Fetch them into samples/keys/ and convert them to 16 kHz mono
WAV (libsndfile cannot read these Ogg files), e.g. with ffmpeg:

    https://commons.wikimedia.org/wiki/File:Laptop_keyboard.ogg
    https://commons.wikimedia.org/wiki/File:Computer_keyboard.ogg
    https://commons.wikimedia.org/wiki/File:Typing_fast.ogg
    https://commons.wikimedia.org/wiki/File:Typing_medium_speed.ogg
    https://commons.wikimedia.org/wiki/File:Keyboard_noise.ogg

    ffmpeg -i Laptop_keyboard.ogg -ac 1 -ar 16000 samples\\keys\\Laptop_keyboard.wav
"""

import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

import listener
from listener import FRAME, SAMPLE_RATE, YOU, EnergyGate, Segmenter, VoiceGate

ROOT = Path(__file__).resolve().parent
SPEECH = sorted((ROOT / "samples").glob("*.wav"))
KEYS = sorted((ROOT / "samples" / "keys").glob("*.wav"))
# A frame of clean speech louder than this is speech the transcript must keep.
SPOKEN_DB = -45.0
# Speech is levelled to this before mixing, about a headset at normal voice.
SPEECH_DB = -20.0
ROOM = 10 ** (-60 / 20)         # never digital silence; see FLOOR_DB
rng = np.random.default_rng(4)


def load(path) -> np.ndarray:
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    return listener.mono16k(audio, rate)


def level(audio, db):
    rms = np.sqrt(np.mean(np.square(audio))) + 1e-12
    return audio * (10 ** (db / 20) / rms)


def quiet(seconds):
    return (rng.standard_normal(int(seconds * SAMPLE_RATE)) * ROOM).astype(np.float32)


def run(gate_factory, audio):
    """Utterances (start, end) the segmenter cuts, and the gate's cost."""
    seg = Segmenter(YOU, gate=gate_factory())
    cut = []
    spent = 0.0
    for i in range(0, len(audio) - FRAME + 1, FRAME):
        t = time.perf_counter()
        u = seg.push(audio[i:i + FRAME])
        spent += time.perf_counter() - t
        if u is not None:
            cut.append((u.start, u.end))
    u = seg.flush()
    if u is not None:
        cut.append((u.start, u.end))
    return cut, spent / max(1, len(audio) // FRAME)


def spoken(audio, offset):
    """Seconds (from the start of the mix) of the frames that are speech."""
    out = []
    for i in range(0, len(audio) - FRAME + 1, FRAME):
        if listener.rms_db(audio[i:i + FRAME]) > SPOKEN_DB:
            out.append(offset + i / SAMPLE_RATE)
    return out


def covered(times, cut):
    return sum(any(a <= t <= b for a, b in cut) for t in times)


def outside(cut, start, end):
    """Utterances that do not touch the speech at all."""
    return sum(1 for a, b in cut if b < start or a > end)


def main():
    if not SPEECH or not KEYS:
        sys.exit("need samples/*.wav (audition.py) and samples/keys/*.wav (see the docstring)")
    gates = {"EnergyGate": EnergyGate, "VoiceGate": VoiceGate}
    speech = [level(load(p), SPEECH_DB) for p in SPEECH]
    keys = [load(p) for p in KEYS]
    key_minutes = sum(len(k) for k in keys) / SAMPLE_RATE / 60
    results = {}

    for name, factory in gates.items():
        r = results[name] = {"keys": 0, "said": 0, "kept": 0, "said_mix": 0,
                             "kept_mix": 0, "false_mix": 0, "cost": []}
        for k in keys:
            cut, cost = run(factory, np.concatenate([quiet(0.5), k]))
            r["keys"] += len(cut)
            r["cost"].append(cost)
        for s in speech:
            lead = 0.5
            mix = np.concatenate([quiet(lead), s, quiet(1.5)])
            times = spoken(s, lead)
            cut, cost = run(factory, mix)
            r["said"] += len(times)
            r["kept"] += covered(times, cut)
            r["cost"].append(cost)
        for i, s in enumerate(speech):
            k = keys[i % len(keys)]
            lead = 4.0
            need = int((lead + 4.0) * SAMPLE_RATE) + len(s)
            bed = np.resize(k, need) + quiet(need / SAMPLE_RATE)[:need]
            at = int(lead * SAMPLE_RATE)
            bed[at:at + len(s)] += s
            times = spoken(s, lead)
            cut, cost = run(factory, np.concatenate([quiet(0.5), bed]))
            times = [t + 0.5 for t in times]
            r["said_mix"] += len(times)
            r["kept_mix"] += covered(times, cut)
            r["false_mix"] += outside(cut, times[0], times[-1])
            r["cost"].append(cost)

    print(f"{len(KEYS)} keyboard recordings ({key_minutes:.1f} min), "
          f"{len(SPEECH)} speech samples\n")
    print("| | utterances cut from keys alone | per minute of typing "
          "| speech kept, quiet room | speech kept, over typing "
          "| utterances cut from the typing around it | gate cost per 30 ms frame |")
    print("|---|---|---|---|---|---|---|")
    for name, r in results.items():
        print(f"| {name} | {r['keys']} | {r['keys'] / key_minutes:.1f} "
              f"| {100 * r['kept'] / r['said']:.1f}% "
              f"| {100 * r['kept_mix'] / r['said_mix']:.1f}% "
              f"| {r['false_mix']} | {1e3 * np.mean(r['cost']):.3f} ms |")


if __name__ == "__main__":
    main()
