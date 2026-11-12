"""The meeting tracker keeps up, and its controls are on the pill (#34).

    venv\\Scripts\\python.exe -m pytest -q tests/test_pill_controls.py

Two findings from a test of the Store build. A long turn showed nothing
until it ended or was cut at 25 s. And stop and the transcripts felt hidden
in the menu.
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import listener  # noqa: E402
import meeting  # noqa: E402

try:
    import cufflink

    has_cufflink = True
except Exception:  # pragma: no cover - headless CI
    cufflink = None
    has_cufflink = False


class ALongTurnShowsWhileItIsStillGoing(unittest.TestCase):
    """The lag Ryan saw. Nothing of a turn shows until the turn ends or the
    segmenter cuts it, and the cut was at 25 s: the first words of a long
    turn waited up to 27 s. lagbench.py has the numbers."""

    def test_the_cut_comes_within_ten_seconds(self):
        self.assertLessEqual(listener.MAX_UTTERANCE, 10.0)

    def test_a_long_turn_gives_its_first_piece_by_ten_seconds_of_audio(self):
        segmenter = listener.Segmenter(listener.YOU, gate=listener.EnergyGate())
        seconds = 30.0
        t = np.arange(int(seconds * listener.SAMPLE_RATE)) / listener.SAMPLE_RATE
        tone = (np.sin(2 * np.pi * 180.0 * t) * 0.14).astype(np.float32)
        quiet = np.zeros(int(0.5 * listener.SAMPLE_RATE), np.float32)
        audio = np.concatenate([quiet, tone])
        first_at = None
        for k in range(len(audio) // listener.FRAME):
            got = segmenter.push(audio[k * listener.FRAME:(k + 1) * listener.FRAME])
            if got is not None:
                first_at = (k + 1) * listener.FRAME_SECONDS
                break
        self.assertIsNotNone(first_at)
        self.assertLessEqual(first_at, 0.5 + listener.MAX_UTTERANCE + 0.1)


def quiet_session(**args):
    """A session with no devices, no models and no port."""
    session = meeting.Session.__new__(meeting.Session)
    session.sources = []
    session.window = meeting._NoWindow()
    session.minutes = meeting.Minutes()
    session.args = SimpleNamespace(no_mic=True, no_loopback=True, **args)
    return session


class TheButtonsReachTheTracker(unittest.TestCase):
    """Each button on the pill sends one line on the port. These are the
    answers the pill draws from."""

    def test_record_with_nothing_to_record_says_so(self):
        self.assertEqual(quiet_session().command("::record"), "nothing to record")

    def test_pause_when_paused_is_harmless(self):
        self.assertEqual(quiet_session().command("::pause"), "paused")

    def test_stop_closes_the_tracker(self):
        session = quiet_session()
        self.assertEqual(session.command("::stop"), "stopping")
        self.assertTrue(session.window._stop.is_set())

    def test_where_names_the_transcripts_folder(self):
        where = quiet_session().command("::where")
        self.assertEqual(Path(where).name, "meetings")


@unittest.skipUnless(has_cufflink, "cufflink needs a display and a tray")
class WhatThePillShows(unittest.TestCase):

    def test_stopped_it_offers_record(self):
        faces = cufflink.listen_faces(recording=False, running=False)
        self.assertEqual(faces["record"]["text"], "●")
        self.assertFalse(faces["record"]["live"])

    def test_recording_it_offers_pause_and_stays_red(self):
        faces = cufflink.listen_faces(recording=True, running=True)
        self.assertEqual(faces["record"]["text"], "❚❚")
        self.assertTrue(faces["record"]["live"])

    def test_stop_is_dim_when_nothing_runs(self):
        self.assertFalse(cufflink.listen_faces(False, running=False)["stop"]["enabled"])
        self.assertTrue(cufflink.listen_faces(False, running=True)["stop"]["enabled"])

    def test_the_transcripts_are_always_one_click_away(self):
        for recording, running in ((False, False), (False, True), (True, True)):
            self.assertTrue(
                cufflink.listen_faces(recording, running)["transcripts"]["enabled"])


if __name__ == "__main__":
    unittest.main()
