"""The pill's side of the meeting tracker: start it, know it, stop it, fix it.

cufflink.py is one long function of closures around a Tk window, which is why
this lives on its own: everything that decides *whether the user stays in
control* is here, where a test can reach it without a window, a microphone or
a meeting (#19).

    the tracker is ours      `hello()` -- a handshake, not "something is on
                             the port". Another program held 52720 once and
                             the pill took it for a running tracker.
    starting it              `launch()` -- below normal priority, so Whisper
                             can never starve the meeting app of a core.
    stopping it              `stop()` -- asked first, then ended, whatever
                             state it is in. A stop that depends on the
                             thing it stops still answering is not a stop.
    something went wrong     `report_url()` -- a GitHub issue, filled in, that
                             the user reads before sending. Never a transcript.
    putting it right         `reset_settings()`, `forget_model()`.

Standard library only. Nothing here imports tkinter, sounddevice or Whisper.
"""

import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

MEETING_PORT = 52720            # cufflink is on 52719; this is the next along
# What the tracker says to `::hello`, and nothing else on this machine does.
HELLO = "cufflink-meeting"
ISSUES = "https://github.com/Ryan-Reddy/cufflink/issues/new"
# How much of the log goes into a report. Enough to see the last start and
# what failed; short enough to read before sending, which is the point.
LOG_LINES = 40
# GitHub refuses a new-issue URL much past 8 KB; leave room for the title.
MAX_BODY = 6000


def ask(command: str, timeout: float = 1.0, port: int = MEETING_PORT):
    """One command to the tracker, its whole answer back. None if nobody
    answered -- including a program that accepts and then says nothing."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(command.encode("utf-8"))
            conn.shutdown(socket.SHUT_WR)
            parts = []
            while True:
                block = conn.recv(65536)
                if not block:
                    return b"".join(parts).decode("utf-8", "replace")
                parts.append(block)
    except OSError:
        return None


def hello(timeout: float = 1.0, port: int = MEETING_PORT):
    """The tracker's process id if it is the tracker answering, else None.

    Not a bare connect. ryans-assistant held this port as its single-instance
    lock: a connect succeeded, the pill decided the tracker was running, never
    started it, and sent ::record into a socket that nobody reads.
    """
    answer = ask("::hello", timeout=timeout, port=port)
    return parse_hello(answer)


def parse_hello(answer):
    if not answer or not answer.startswith(HELLO):
        return None
    match = re.match(rf"{HELLO} (\d+)", answer)
    return int(match.group(1)) if match else 0


def port_holder(port: int = MEETING_PORT):
    """Is the port held, and by whom? (held, pid-or-None, name-or-None).

    `netstat` rather than psutil: no new dependency for the one moment it
    matters, which is telling somebody which program is in the way.
    """
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True,
                             text=True, timeout=5,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except Exception:
        return (False, None, None)
    pid = None
    for line in out.splitlines():
        cols = line.split()
        if len(cols) >= 5 and cols[1].endswith(f":{port}") and cols[3] == "LISTENING":
            pid = int(cols[4]) if cols[4].isdigit() else None
            break
    if pid is None:
        return (False, None, None)
    return (True, pid, process_name(pid))


def process_name(pid: int):
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=5,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        first = out.strip().splitlines()[0] if out.strip() else ""
        return first.split('","')[0].strip('"') or None
    except Exception:
        return None


def command_line(here: Path, frozen: bool, executable: str) -> list:
    """How to start the tracker, from source or from the packaged exe.

    The packaged build has no Python to run meeting.py with, so the exe runs
    it itself when started with --meeting (see the top of cufflink.py).
    """
    if frozen:
        return [executable, "--meeting", "--headless"]
    runner = here / "venv" / "Scripts" / "pythonw.exe"
    if not runner.exists():
        runner = Path(executable).with_name("pythonw.exe")
    return [str(runner), str(here / "meeting.py"), "--headless"]


def launch(argv: list, cwd: Path, log: Path):
    """Start the tracker below normal priority, its output into `log`.

    Below normal so the meeting app always wins the CPU: Whisper takes every
    core it is given, and at normal priority a model loading at the start of
    a call competes with the call itself.
    """
    flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
             | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as out:
        out.write(f"\n--- started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.flush()
        return subprocess.Popen(argv, cwd=str(cwd), stdout=out, stderr=out,
                                creationflags=flags)


def stop(proc=None, pid=None, grace: float = 3.0, ask_fn=ask, kill_fn=None) -> str:
    """End the tracker. Asked nicely first, then ended regardless.

    `proc` is the handle when the pill started it; `pid` comes from the
    handshake when it did not (the pill was restarted, or someone ran
    meeting.py by hand). Only a pid the handshake vouched for is ever killed.
    """
    kill_fn = kill_fn or _kill
    asked = ask_fn("::stop", timeout=1.0) is not None
    deadline = time.monotonic() + grace
    if proc is not None:
        while time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.1)
        if proc.poll() is None:
            # The whole tree, not the handle: from source the handle is the
            # venv's launcher stub, and the tracker is its child (#7).
            kill_fn(proc.pid)
            return "stopped (it had to be ended)"
        return "stopped"
    if pid:
        while time.monotonic() < deadline and alive(pid):
            time.sleep(0.1)
        if alive(pid):
            kill_fn(pid)
            return "stopped (it had to be ended)"
        return "stopped"
    return "stopped" if asked else "was not running"


def alive(pid: int) -> bool:
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True, timeout=5,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return str(pid) in out
    except Exception:
        return False


def _kill(pid: int):
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                   timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


# ------------------------------------------------------------- reporting

# Lines in a log that could carry what somebody said: the tracker never
# prints transcript text, but a report is the wrong place to find out it does.
_SPOKEN = re.compile(r"^\s*\[?\d{1,2}:\d{2}.*\b(you|them)\b", re.I)


def log_tail(log: Path, lines: int = LOG_LINES) -> str:
    try:
        text = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(no log yet)"
    kept = [line for line in text if not _SPOKEN.match(line)]
    return "\n".join(kept[-lines:]) or "(log is empty)"


def where_it_runs(frozen: bool, here: Path) -> str:
    if frozen:
        return "packaged (Store or zip)"
    try:
        commit = subprocess.run(["git", "-C", str(here), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, timeout=5,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                                ).stdout.strip()
    except Exception:
        commit = ""
    return f"from source{f' at {commit}' if commit else ''}"


def report_url(what: str, where: str, how: str, log: str) -> str:
    """A new GitHub issue, filled in, for the user to read and then send.

    Prefilled, never posted: the browser opens on the form, and nothing leaves
    the machine until they press the button themselves. No transcript and no
    audio, ever -- the log is filtered for spoken lines on the way in.
    """
    body = (
        "**What went wrong** (say it in your own words):\n\n"
        f"{what or '…'}\n\n"
        "**Where:** " + (where or "?") + "\n\n"
        "**What I expected instead:**\n\n…\n\n"
        "---\n"
        f"- cufflink: {how}\n"
        f"- Windows: {platform.platform()}\n"
        f"- Python: {platform.python_version()}\n\n"
        "<details><summary>Last lines of the meeting log</summary>\n\n"
        f"```\n{log}\n```\n\n</details>\n\n"
        "_Nothing from your meetings is in this report: no transcript, no audio. "
        "Read it before you press Submit, and add or remove whatever you like._\n"
    )
    if len(body) > MAX_BODY:
        keep = MAX_BODY - (len(body) - len(log)) - 20
        body = body.replace(log, "…\n" + log[-max(0, keep):])
    title = f"Meeting tracker: {where or 'a problem'}"
    return f"{ISSUES}?{urlencode({'title': title, 'body': body, 'labels': 'bug'})}"


# ------------------------------------------------------------- repairing

def reset_settings(settings: Path) -> str:
    """Put settings back to the defaults, keeping the old file beside them."""
    if not settings.exists():
        return "settings are already the defaults"
    kept = settings.with_name(f"{settings.stem}.{time.strftime('%Y%m%d-%H%M%S')}.bak")
    settings.rename(kept)
    return f"settings reset; the old ones are in {kept.name}"


def forget_model(cache: Path, repo: str) -> str:
    """Delete one downloaded model so the next start fetches it whole.

    For the download that broke half way, which faster-whisper does not
    notice: it finds a folder and fails deep inside CTranslate2.
    """
    folder = cache / ("models--" + repo.replace("/", "--"))
    if not folder.exists():
        return "nothing to remove; it downloads on the next start"
    shutil.rmtree(folder, ignore_errors=True)
    return "removed; it downloads again on the next start"


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    if frozen():
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def state_home() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "cufflink"
