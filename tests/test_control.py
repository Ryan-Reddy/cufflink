"""Tests for staying in control of the meeting tracker (#19).

    venv\\Scripts\\python.exe -m unittest discover -s tests -v

What went wrong in a real meeting: another program held the tracker's port,
nothing could stop the tracker short of Task Manager, and nobody could say
what had happened. So: the pill must know the tracker from anything else on
its port, a stop must work whatever the tracker is doing, the tracker must
refuse to run where it could not be stopped, and a report must be easy to make
and carry nothing from the meeting itself.
"""

import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import meeting  # noqa: E402
import meetingctl  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Answering:
    """A server on a port that answers every line with `reply`."""

    def __init__(self, reply):
        self.port = free_port()
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", self.port))
        self.sock.listen(4)
        self.reply = reply
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                conn.recv(1024)
                conn.sendall(self.reply.encode())

    def close(self):
        self.sock.close()


class Silent:
    """Holds a port and never answers: what ryans-assistant's lock looked
    like to the pill."""

    def __init__(self):
        self.port = free_port()
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", self.port))
        self.sock.listen(1)

    def close(self):
        self.sock.close()


class KnowingTheTracker(unittest.TestCase):

    def test_the_tracker_says_who_it_is(self):
        server = Answering(f"{meetingctl.HELLO} 4242")
        try:
            self.assertEqual(meetingctl.hello(port=server.port), 4242)
        finally:
            server.close()

    def test_something_else_on_the_port_is_not_the_tracker(self):
        server = Answering("hello, I am the assistant")
        try:
            self.assertIsNone(meetingctl.hello(port=server.port))
        finally:
            server.close()

    def test_a_port_that_is_held_and_never_answers_is_not_the_tracker(self):
        """The case that sent ::record into a socket nobody read."""
        lock = Silent()
        try:
            started = time.monotonic()
            self.assertIsNone(meetingctl.hello(timeout=0.5, port=lock.port))
            self.assertLess(time.monotonic() - started, 2.0)
        finally:
            lock.close()

    def test_nothing_on_the_port_is_not_the_tracker(self):
        self.assertIsNone(meetingctl.hello(timeout=0.3, port=free_port()))

    def test_the_tracker_answers_hello_with_its_pid(self):
        session = SimpleNamespace(minutes=None)
        answer = meeting.Session.command(session, "::hello")
        self.assertEqual(meetingctl.parse_hello(answer), __import__("os").getpid())


class RefusingToRunUnstoppable(unittest.TestCase):

    def test_a_taken_port_stops_the_tracker_before_it_starts(self):
        lock = Silent()
        try:
            with mock.patch.object(meeting, "MEETING_PORT", lock.port), \
                    mock.patch.object(meetingctl, "port_holder",
                                      return_value=(True, 99, "pythonw.exe")):
                with self.assertRaises(SystemExit) as stopped:
                    meeting.Session._bind(SimpleNamespace())
            self.assertIn("pythonw.exe", str(stopped.exception))
            self.assertIn("not starting", str(stopped.exception))
        finally:
            lock.close()

    def test_a_free_port_is_taken(self):
        port = free_port()
        with mock.patch.object(meeting, "MEETING_PORT", port):
            server = meeting.Session._bind(SimpleNamespace())
        try:
            self.assertEqual(server.getsockname()[1], port)
        finally:
            server.close()


class Stopping(unittest.TestCase):
    """A stop that depends on the tracker still answering is not a stop."""

    def test_a_tracker_that_stops_when_asked_is_not_killed(self):
        proc = mock.Mock()
        proc.poll.side_effect = [None, 0, 0]
        said = meetingctl.stop(proc=proc, grace=1.0, ask_fn=lambda *a, **k: "stopping")
        self.assertEqual(said, "stopped")
        proc.kill.assert_not_called()

    def test_a_tracker_that_hangs_is_ended_anyway(self):
        proc = mock.Mock()
        proc.poll.return_value = None
        said = meetingctl.stop(proc=proc, grace=0.2, ask_fn=lambda *a, **k: None)
        proc.kill.assert_called_once()
        self.assertIn("ended", said)

    def test_a_tracker_this_pill_did_not_start_is_ended_by_its_pid(self):
        killed = []
        with mock.patch.object(meetingctl, "alive", return_value=True):
            said = meetingctl.stop(pid=4242, grace=0.2, ask_fn=lambda *a, **k: None,
                                   kill_fn=killed.append)
        self.assertEqual(killed, [4242])
        self.assertIn("ended", said)

    def test_with_nothing_running_it_says_so(self):
        self.assertEqual(meetingctl.stop(ask_fn=lambda *a, **k: None), "was not running")


class Starting(unittest.TestCase):

    def test_from_source_it_runs_meeting_py_without_a_window(self):
        with TemporaryDirectory() as tmp:
            here = Path(tmp)
            argv = meetingctl.command_line(here, frozen=False,
                                           executable=r"C:\Python\python.exe")
        self.assertTrue(argv[0].endswith("pythonw.exe"))
        self.assertTrue(argv[1].endswith("meeting.py"))

    def test_packaged_the_exe_runs_the_tracker_itself(self):
        argv = meetingctl.command_line(Path("."), frozen=True,
                                       executable=r"C:\Apps\cufflink.exe")
        self.assertEqual(argv[:2], [r"C:\Apps\cufflink.exe", "--meeting"])

    def test_it_starts_below_normal_priority(self):
        with TemporaryDirectory() as tmp, \
                mock.patch.object(meetingctl.subprocess, "Popen") as popen:
            meetingctl.launch(["x"], Path(tmp), Path(tmp) / "meeting.log")
        flags = popen.call_args.kwargs["creationflags"]
        self.assertTrue(flags & 0x00004000, "BELOW_NORMAL_PRIORITY_CLASS")

    def test_the_cli_takes_its_arguments_from_the_exe(self):
        """cufflink.exe --meeting passes the rest through to meeting.main."""
        with mock.patch.object(meeting, "list_devices", return_value=None) as listed,                 mock.patch.object(meeting, "below_normal"):
            meeting.main(["--devices"])
        listed.assert_called_once()


class Reporting(unittest.TestCase):

    def report(self, log="started\nmodel: base ready in 3s"):
        url = meetingctl.report_url("the stop button did nothing",
                                    "the meeting tracker", "from source at abc123", log)
        query = parse_qs(urlparse(url).query)
        return url, query["title"][0], query["body"][0]

    def test_it_goes_to_a_new_issue_here_for_the_user_to_send(self):
        url, title, _ = self.report()
        self.assertTrue(url.startswith("https://github.com/Ryan-Reddy/cufflink/issues/new?"))
        self.assertIn("meeting tracker", title)

    def test_it_says_what_where_and_which_version(self):
        _, _, body = self.report()
        self.assertIn("the stop button did nothing", body)
        self.assertIn("from source at abc123", body)
        self.assertIn("Windows:", body)
        self.assertIn("model: base ready", body)

    def test_spoken_lines_never_reach_a_report(self):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "meeting.log"
            log.write_text("started\n[00:12] you: our secret plan\n"
                           "00:13 them  the numbers\nmodel: base ready\n",
                           encoding="utf-8")
            tail = meetingctl.log_tail(log)
        self.assertNotIn("secret plan", tail)
        self.assertNotIn("the numbers", tail)
        self.assertIn("model: base ready", tail)

    def test_a_long_log_still_fits_in_a_url_github_accepts(self):
        url, _, body = self.report(log="\n".join(f"line {i} " + "x" * 80 for i in range(400)))
        self.assertLess(len(body), meetingctl.MAX_BODY + 200)
        self.assertIn("line 399", body)

    def test_no_log_yet_is_said_plainly(self):
        self.assertEqual(meetingctl.log_tail(Path("does-not-exist.log")), "(no log yet)")


class Repairing(unittest.TestCase):

    def test_resetting_settings_keeps_the_old_ones(self):
        with TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.json"
            settings.write_text("{}", encoding="utf-8")
            said = meetingctl.reset_settings(settings)
            self.assertFalse(settings.exists())
            self.assertEqual(len(list(Path(tmp).glob("settings.*.bak"))), 1)
            self.assertIn("reset", said)

    def test_resetting_defaults_is_a_no_op(self):
        with TemporaryDirectory() as tmp:
            self.assertIn("already", meetingctl.reset_settings(Path(tmp) / "settings.json"))

    def test_forgetting_a_model_removes_only_that_one(self):
        with TemporaryDirectory() as tmp:
            cache = Path(tmp)
            small = cache / "models--Systran--faster-whisper-small"
            base = cache / "models--Systran--faster-whisper-base"
            small.mkdir()
            base.mkdir()
            meetingctl.forget_model(cache, "Systran/faster-whisper-small")
            self.assertFalse(small.exists())
            self.assertTrue(base.exists())


if __name__ == "__main__":
    unittest.main()
