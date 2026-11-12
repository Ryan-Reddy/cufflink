"""How far behind the meeting tracker is, without a microphone (#34).

    venv\\Scripts\\python.exe lagbench.py
    venv\\Scripts\\python.exe lagbench.py --refine-threads 4 --refine-beam 1

A meeting is played into the same pipeline the tracker runs -- a frame queue,
`listener.Meeting.feed` on one thread, `Meeting.refine` with the better model
on another, the Silero gate -- at the speed of real time, as two sources
taking turns. Nothing is captured and nothing is played.

The speech is made once by Kokoro and kept in samples/ (gitignored):
samples/lag-you.wav and samples/lag-them.wav. Same length, each silent while
the other talks.

For every line it reports:

  fast     seconds from the end of the utterance to its first line (`base`)
  refined  seconds from the end of the utterance to the better hearing
  rtf      seconds of work per second of audio, for each pass

The end of an utterance is where the segmenter closes it, which is
SILENCE_TO_CUT after the voice stops; that wait is in every number.
"""

import argparse
import os
import queue
import statistics
import sys
import threading
import time
from pathlib import Path

import numpy as np

import listener
from listener import FRAME, FRAME_SECONDS, SAMPLE_RATE, THEM, YOU

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"

# Two people taking turns. Long and short turns, because a long one is what
# makes the better pass fall behind.
TURNS = [
    (YOU, "Good morning, everyone. Shall we start with the release plan?"),
    (THEM, "Yes. The build for the Store went out yesterday, and the first "
           "reports are in. Most of them are about the meeting tracker."),
    (YOU, "What do people say about it?"),
    (THEM, "They say it is useful, but it lags behind. The words come up a "
           "few seconds after somebody stops talking, and in a long meeting "
           "the corrections arrive much later than that."),
    (YOU, "That matches what I saw. Do we know where the time goes?"),
    (THEM, "Not yet. There are two models. The small one rewrites what the "
           "base one wrote, and they share the same processor."),
    (YOU, "Then we measure it first, and change one thing."),
    (THEM, "Agreed. I will also move the controls onto the pill, because now "
           "they are hidden in the menu and people cannot find them."),
    (YOU, "Good. Let us look at the numbers on Friday."),
    (THEM, "Fine by me. I will send the report before then."),
]
# One person who talks for a long time without a pause: a talk, a demo, a
# colleague reading out a plan. Kokoro's pauses between sentences are shorter
# than SILENCE_TO_CUT, so each turn is one utterance until MAX_UTTERANCE.
LONG = [
    (THEM, "Let me walk you through the plan for the next release, because "
           "there are a few moving parts and I want everybody to have the same "
           "picture before we start. First, the meeting tracker. People like "
           "it, but they tell us the words come up late, and when a colleague "
           "talks for a long time nothing appears at all until they stop. "
           "Second, the controls. Record, stop and the transcripts are in a "
           "menu, and in the middle of a call nobody wants to open a menu. "
           "Third, the Store listing, which needs new screenshots once the "
           "first two are done."),
    (YOU, "That sounds right. Which one comes first?"),
    (THEM, "The lag comes first, because it changes how the whole thing feels. "
           "We will measure it on a recording, change the one thing that "
           "matters most, and measure it again. Then the buttons go on the "
           "pill, next to the record button, where people already look. The "
           "screenshots wait until both of those are merged."),
]
GAP = 1.2           # seconds of room between turns
ROOM_DB = -60.0


def kokoro_dir() -> Path:
    for here in (ROOT / "models", Path(r"C:\github\cufflink\models")):
        if (here / "kokoro-v1.0.onnx").exists():
            return here
    raise SystemExit("no kokoro-v1.0.onnx in models/; run from a checkout with one")


def make_speech(script="turns"):
    """Both sides of the meeting as two equal-length tracks, made once."""
    import soundfile as sf

    turns = LONG if script == "long" else TURNS
    you_path = SAMPLES / f"lag-{script}-you.wav"
    them_path = SAMPLES / f"lag-{script}-them.wav"
    if you_path.exists() and them_path.exists():
        you, _ = sf.read(you_path, dtype="float32")
        them, _ = sf.read(them_path, dtype="float32")
        return you, them
    from kokoro_onnx import Kokoro

    here = kokoro_dir()
    kokoro = Kokoro(str(here / "kokoro-v1.0.onnx"), str(here / "voices-v1.0.bin"))
    voices = {YOU: "af_heart", THEM: "bm_george"}
    rng = np.random.default_rng(34)
    room = 10 ** (ROOM_DB / 20)
    tracks = {YOU: [], THEM: []}
    for who, text in turns:
        audio, rate = kokoro.create(text, voice=voices[who], speed=1.0, lang="en-us")
        audio = listener.mono16k(np.asarray(audio, np.float32), rate)
        gap = np.zeros(int(GAP * SAMPLE_RATE), np.float32)
        for side in tracks:
            said = audio if side == who else np.zeros_like(audio)
            tracks[side] += [said, gap]
    out = []
    for side in (YOU, THEM):
        track = np.concatenate(tracks[side])
        track = track + rng.standard_normal(len(track)).astype(np.float32) * room
        out.append(track.astype(np.float32))
    SAMPLES.mkdir(exist_ok=True)
    sf.write(you_path, out[0], SAMPLE_RATE)
    sf.write(them_path, out[1], SAMPLE_RATE)
    return out[0], out[1]


class Timed:
    """A transcriber that writes down how long each call took."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = []             # (audio seconds, work seconds)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def transcribe(self, audio, sample_rate=SAMPLE_RATE):
        started = time.perf_counter()
        text = self.inner.transcribe(audio, sample_rate)
        self.calls.append((len(audio) / sample_rate, time.perf_counter() - started))
        return text


def run(args, you, them):
    if args.below_normal:
        import meeting

        meeting.below_normal()
    fast = Timed(listener.WhisperTranscriber(
        args.model, language="en", threads=args.threads, beam=args.beam))
    better = Timed(listener.WhisperTranscriber(
        args.refine_with, language="en",
        threads=args.refine_threads or args.threads,
        beam=args.refine_beam or args.beam)) if args.refine_with else None
    fast.load()
    if better:
        better.load()
    # Warm both once: the first call pays for allocations a meeting pays
    # before anyone talks.
    fast.transcribe(you[:SAMPLE_RATE])
    if better:
        better.transcribe(you[:SAMPLE_RATE])
    fast.calls.clear()
    if better:
        better.calls.clear()

    first, refined, ends, starts = {}, {}, {}, {}
    t0 = [0.0]

    def heard(line):
        now = time.perf_counter() - t0[0]
        ends[line.id] = (line.source, line.end, line.text)
        starts.setdefault(line.id, line.start)
        if line.id not in first:
            first[line.id] = now
        else:
            refined[line.id] = now

    meeting = listener.Meeting(fast, on_line=heard, refine=bool(better))
    frames: queue.Queue = queue.Queue()
    running = threading.Event()
    running.set()
    fed_all = threading.Event()

    def produce():
        count = min(len(you), len(them)) // FRAME
        for k in range(count):
            due = t0[0] + (k + 1) * FRAME_SECONDS
            wait = due - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            for source, track in ((YOU, you), (THEM, them)):
                frames.put((source, track[k * FRAME:(k + 1) * FRAME]))
        fed_all.set()

    def consume():
        while running.is_set():
            try:
                source, frame = frames.get(timeout=0.2)
            except queue.Empty:
                continue
            meeting.feed(source, frame)

    def improve():
        while running.is_set():
            if better is None or not meeting.awaiting:
                time.sleep(0.05)
                continue
            line_id = meeting.awaiting[0][0]
            meeting.refine(better)
            refined.setdefault(line_id, time.perf_counter() - t0[0])

    t0[0] = time.perf_counter()
    threads = [threading.Thread(target=f, daemon=True) for f in (produce, consume, improve)]
    for t in threads:
        t.start()
    fed_all.wait()
    while not frames.empty():
        time.sleep(0.1)
    deadline = time.perf_counter() + 600
    while better and (meeting.awaiting or len(refined) < len(first)) \
            and time.perf_counter() < deadline:
        time.sleep(0.1)
    time.sleep(0.3)
    running.clear()

    rows = []
    for line_id in sorted(first):
        source, end, text = ends[line_id]
        rows.append((line_id, source, end, first[line_id] - end,
                     refined[line_id] - end if line_id in refined else None, text,
                     first[line_id] - starts[line_id]))
    return rows, fast.calls, (better.calls if better else [])


def wer(reference, hypothesis):
    """Word error rate, after lower case and without punctuation."""
    import re

    def words(text):
        return re.sub(r"[^a-z0-9' ]+", " ", text.lower()).split()
    ref, hyp = words(reference), words(hypothesis)
    row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, row[0] = row[0], i
        for j, h in enumerate(hyp, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (r != h))
    return row[-1] / max(1, len(ref))


def rtf(calls):
    audio = sum(a for a, _ in calls)
    return sum(w for _, w in calls) / audio if audio else 0.0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default="base")
    p.add_argument("--refine-with", default="small")
    p.add_argument("--threads", type=int, default=None)
    p.add_argument("--beam", type=int, default=5)
    p.add_argument("--refine-threads", type=int, default=None)
    p.add_argument("--refine-beam", type=int, default=None)
    p.add_argument("--below-normal", action="store_true",
                   help="run at the priority the tracker runs at")
    p.add_argument("--quiet", action="store_true", help="only the summary")
    p.add_argument("--script", default="turns", choices=("turns", "long"),
                   help="short turns, or long turns without a pause")
    p.add_argument("--max-utterance", type=float, default=None,
                   help="override listener.MAX_UTTERANCE, in seconds")
    args = p.parse_args(argv)

    if args.max_utterance:
        listener.MAX_UTTERANCE = args.max_utterance
    you, them = make_speech(args.script)
    seconds = min(len(you), len(them)) / SAMPLE_RATE
    threads = args.threads or listener._default_threads()
    print(f"cpu: {os.cpu_count()} logical; {args.model} threads={threads} "
          f"beam={args.beam}; {args.refine_with or '-'} "
          f"threads={args.refine_threads or threads} "
          f"beam={args.refine_beam or args.beam}; meeting {seconds:.0f}s; "
          f"cut at {listener.MAX_UTTERANCE:.0f}s")
    rows, fast_calls, better_calls = run(args, you, them)
    if not args.quiet:
        print(f"{'id':>3} {'who':4} {'end':>6} {'fast':>6} {'refined':>8}  text")
        for line_id, source, end, lag, late, text, _ in rows:
            late_s = f"{late:8.1f}" if late is not None else "       -"
            print(f"{line_id:3} {source:4} {end:6.1f} {lag:6.1f} {late_s}  {text[:50]}")
    lags = [r[3] for r in rows]
    lates = [r[4] for r in rows if r[4] is not None]
    print(f"fast    lag median {statistics.median(lags):.1f}s  max {max(lags):.1f}s  "
          f"rtf {rtf(fast_calls):.2f}  lines {len(rows)}")
    waits = [r[6] for r in rows]
    print(f"first words wait median {statistics.median(waits):.1f}s  "
          f"max {max(waits):.1f}s  (line shown - utterance start)")
    turns = LONG if args.script == "long" else TURNS
    for source in (YOU, THEM):
        said = " ".join(t for w, t in turns if w == source)
        heard = " ".join(r[5] for r in rows if r[1] == source)
        print(f"wer {source:4} {wer(said, heard):.3f}")
    if lates:
        print(f"refined lag median {statistics.median(lates):.1f}s  "
              f"max {max(lates):.1f}s  rtf {rtf(better_calls):.2f}")


if __name__ == "__main__":
    sys.exit(main())
