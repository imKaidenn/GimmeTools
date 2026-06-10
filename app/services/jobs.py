"""
GimmeTools — background job queue.

Jobs run the same CLI scripts a terminal user runs, in the toolkit venv, as
child processes — the UI stays a thin layer. The queue is a single worker
thread: one media job at a time (the tools saturate the GPU on their own),
with pause/resume between items, reordering of queued items, tree-kill
cancellation, and a persisted history.

Thread-safety: every public method takes the internal lock; `snapshot()`
returns plain dicts safe to hand to the UI.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# Matches the "[3/10] name.jpg" lines the batch CLIs print.
_PROGRESS_RE = re.compile(r"^\[(\d+)/(\d+)\]")

QUEUED, RUNNING, DONE, FAILED, CANCELLED = "queued", "running", "done", "failed", "cancelled"
_TERMINAL = (DONE, FAILED, CANCELLED)

_HISTORY_LIMIT = 200
_LOG_TAIL = 300


@dataclass
class Job:
    id: str
    tool_id: str
    tool_name: str
    label: str                    # short human label (file name / "folder (12 items)")
    cmd: list[str]
    status: str = QUEUED
    created: float = field(default_factory=time.time)
    started: Optional[float] = None
    ended: Optional[float] = None
    exit_code: Optional[int] = None
    progress_cur: int = 0
    progress_total: int = 0
    log: deque = field(default_factory=lambda: deque(maxlen=_LOG_TAIL))

    def to_dict(self, with_log: bool = False) -> dict:
        d = {
            "id": self.id,
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "label": self.label,
            "status": self.status,
            "created": self.created,
            "started": self.started,
            "ended": self.ended,
            "exit_code": self.exit_code,
            "progress_cur": self.progress_cur,
            "progress_total": self.progress_total,
        }
        if with_log:
            d["log"] = list(self.log)
        return d


class JobQueue:
    def __init__(self, python_exe: Path, scripts_dir: Path, history_path: Path,
                 on_change: Optional[Callable[[], None]] = None) -> None:
        self._python = python_exe
        self._scripts = scripts_dir
        self._history_path = history_path
        self._on_change = on_change
        self._lock = threading.RLock()
        self._queue: list[Job] = []
        self._current: Optional[Job] = None
        self._history: list[dict] = self._load_history()
        self._paused = False
        self._wake = threading.Event()
        self._stop = False
        self._proc: Optional[subprocess.Popen] = None
        self._seq = itertools.count(1)
        self._worker = threading.Thread(target=self._run_loop, daemon=True)
        self._worker.start()

    # ── Public API ─────────────────────────────────────────────────────────

    def enqueue(self, tool_id: str, tool_name: str, label: str, script: str,
                args: list[str]) -> str:
        return self.enqueue_cmd(
            tool_id, tool_name, label,
            [str(self._python), "-u", str(self._scripts / script)] + args,
        )

    def enqueue_cmd(self, tool_id: str, tool_name: str, label: str,
                    cmd: list[str]) -> str:
        """Queue an arbitrary command (e.g. first-run setup with the bootstrap
        interpreter rather than the venv one)."""
        job = Job(
            id=f"job-{next(self._seq)}-{uuid.uuid4().hex[:6]}",
            tool_id=tool_id,
            tool_name=tool_name,
            label=label,
            cmd=list(cmd),
        )
        with self._lock:
            self._queue.append(job)
        self._wake.set()
        self._notify()
        return job.id

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            if self._current and self._current.id == job_id:
                self._kill_tree()
                return True
            for job in self._queue:
                if job.id == job_id:
                    self._queue.remove(job)
                    job.status = CANCELLED
                    job.ended = time.time()
                    self._archive(job)
                    self._notify()
                    return True
        return False

    def move(self, job_id: str, direction: int) -> bool:
        """Move a queued job up (-1) or down (+1)."""
        with self._lock:
            ids = [j.id for j in self._queue]
            if job_id not in ids:
                return False
            i = ids.index(job_id)
            j = i + (1 if direction > 0 else -1)
            if not 0 <= j < len(self._queue):
                return False
            self._queue[i], self._queue[j] = self._queue[j], self._queue[i]
        self._notify()
        return True

    def pause(self) -> None:
        with self._lock:
            self._paused = True
        self._notify()

    def resume(self) -> None:
        with self._lock:
            self._paused = False
        self._wake.set()
        self._notify()

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()
            self._save_history()
        self._notify()

    def get_log(self, job_id: str) -> list[str]:
        with self._lock:
            if self._current and self._current.id == job_id:
                return list(self._current.log)
            for h in self._history:
                if h["id"] == job_id:
                    return h.get("log", [])
        return []

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "paused": self._paused,
                "current": self._current.to_dict(with_log=True) if self._current else None,
                "queue": [j.to_dict() for j in self._queue],
                "history": [
                    {k: v for k, v in h.items() if k != "log"}
                    for h in self._history[:50]
                ],
            }

    def active_count(self) -> int:
        with self._lock:
            return len(self._queue) + (1 if self._current else 0)

    def shutdown(self) -> None:
        """Kill any running child and stop the worker (app exit)."""
        with self._lock:
            self._stop = True
            self._kill_tree()
        self._wake.set()

    # ── Worker ─────────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        while not self._stop:
            job: Optional[Job] = None
            with self._lock:
                if not self._paused and self._queue:
                    job = self._queue.pop(0)
                    job.status = RUNNING
                    job.started = time.time()
                    self._current = job
            if job is None:
                self._wake.wait(timeout=0.5)
                self._wake.clear()
                continue

            self._notify()
            self._execute(job)

            with self._lock:
                self._current = None
                self._archive(job)
            self._notify()

    def _execute(self, job: Job) -> None:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            with self._lock:
                self._proc = subprocess.Popen(
                    job.cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    bufsize=1,
                    creationflags=flags,
                )
            proc = self._proc
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip("\n")
                job.log.append(line)
                m = _PROGRESS_RE.match(line)
                if m:
                    job.progress_cur = int(m.group(1))
                    job.progress_total = int(m.group(2))
                    self._notify()
            code = proc.wait()
            job.exit_code = code
            job.status = DONE if code == 0 else (
                CANCELLED if job.status == CANCELLED else FAILED
            )
        except Exception as e:  # noqa: BLE001 — job must always reach a terminal state
            job.log.append(f"Error: {e}")
            job.status = FAILED
        finally:
            job.ended = time.time()
            with self._lock:
                self._proc = None

    def _kill_tree(self) -> None:
        """Kill the running child and its whole process tree (HandBrake etc.)."""
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        if self._current:
            self._current.status = CANCELLED
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                proc.kill()
        except Exception:
            pass

    # ── History persistence ────────────────────────────────────────────────

    def _archive(self, job: Job) -> None:
        entry = job.to_dict(with_log=True)
        entry["log"] = entry["log"][-40:]   # keep history file small
        self._history.insert(0, entry)
        del self._history[_HISTORY_LIMIT:]
        self._save_history()

    def _load_history(self) -> list[dict]:
        try:
            data = json.loads(self._history_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_history(self) -> None:
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            self._history_path.write_text(
                json.dumps(self._history, indent=1), encoding="utf-8"
            )
        except OSError:
            pass

    def _notify(self) -> None:
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass


# ── Self-test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        q = JobQueue(
            python_exe=Path(sys.executable),
            scripts_dir=Path(tmp),
            history_path=Path(tmp) / "history.json",
        )
        # A "script" that just prints — exercises the full pipeline.
        script = Path(tmp) / "ok.py"
        script.write_text("print('[1/2] a')\nprint('[2/2] b')\nprint('done')\n")
        jid = q.enqueue("t", "Test", "two items", "ok.py", [])

        for _ in range(100):
            snap = q.snapshot()
            if snap["history"] and snap["history"][0]["id"] == jid:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("job never finished")

        h = q.snapshot()["history"][0]
        assert h["status"] == DONE, h
        assert h["progress_total"] == 2, h
        assert "done" in q.get_log(jid)

        # Failure path
        bad = Path(tmp) / "bad.py"
        bad.write_text("import sys; sys.exit(3)\n")
        jid2 = q.enqueue("t", "Test", "fails", "bad.py", [])
        for _ in range(100):
            snap = q.snapshot()
            if snap["history"] and snap["history"][0]["id"] == jid2:
                break
            time.sleep(0.05)
        assert q.snapshot()["history"][0]["status"] == FAILED

        # Pause holds the queue
        q.pause()
        jid3 = q.enqueue("t", "Test", "held", "ok.py", [])
        time.sleep(0.4)
        assert q.snapshot()["queue"], "paused queue should hold the job"
        q.resume()
        for _ in range(100):
            if q.snapshot()["history"] and q.snapshot()["history"][0]["id"] == jid3:
                break
            time.sleep(0.05)
        assert q.snapshot()["history"][0]["status"] == DONE

        q.shutdown()
    print("jobs.py OK")
