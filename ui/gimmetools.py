"""
GimmeTools — desktop UI for GimmeTools.

A THIN layer over the backend. It does no image/video work itself: every
action shells out to the same scripts/*.py a terminal user runs, in the same
venv, and streams their live output into the log panel. Delete this ui/ folder
and the backend is untouched.

Backend : scripts/remove_bg.py · scripts/upscale_image.py ·
          scripts/process_video.py · scripts/diagnose.py
UI       : customtkinter, cyberpunk palette matching GimmeDat.

GimmeTools — made by Kaiden.
Copyright (C) 2026 Kaiden. Licensed under GPL-3.0 (see LICENSE).
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

# ── Resolve toolkit root and reuse the backend's config ────────────────────────
# ui/gimmetools.py -> ui -> GimmeTools
TOOLKIT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = TOOLKIT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from lib.config import Config, VERSION as _LIB_VERSION
    _cfg = Config.load()
except Exception:
    _cfg = None
    _LIB_VERSION = "1.1"

try:
    import customtkinter as ctk
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    print(
        "customtkinter is not installed.\n"
        "Run:  tools\\venv\\Scripts\\python.exe -m pip install customtkinter\n"
        "Or just launch GimmeTools.bat which installs it for you.",
        file=sys.stderr,
    )
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG / PALETTE  (matches GimmeDat: near-black + purple/violet + cyan neon)
# ─────────────────────────────────────────────────────────────────────────────

VERSION = _LIB_VERSION
APP_NAME = "GimmeTools"

BG       = "#08070d"
PANEL    = "#0e0c16"
CARD     = "#13101f"
CARD2    = "#181327"
BORDER   = "#271f3e"
PURPLE   = "#7c3aed"
VIOLET   = "#8b5cf6"
PURPLE_L = "#a78bfa"
NEON     = "#22d3ee"
NEON_DIM = "#0e7490"
TEXT     = "#ece9fb"
MUTED    = "#8b85b0"
FAINT    = "#544d77"
OK       = "#34d399"
ERR      = "#fb7185"

F_DISP = "Arial Black"
F_UI   = "Segoe UI"
F_MONO = "Consolas"

IMAGE_TYPES = [("Images", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp"), ("All files", "*.*")]
VIDEO_TYPES = [("Videos", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v"), ("All files", "*.*")]


def venv_python() -> Path:
    """The interpreter that runs the backend scripts (same venv this UI uses)."""
    win = TOOLKIT_ROOT / "tools" / "venv" / "Scripts" / "python.exe"
    nix = TOOLKIT_ROOT / "tools" / "venv" / "bin" / "python"
    if win.exists():
        return win
    if nix.exists():
        return nix
    # Fall back to whatever interpreter is running this UI
    return Path(sys.executable)


# ─────────────────────────────────────────────────────────────────────────────
#  WORKER  — runs a backend script as a subprocess, streams output to a queue
# ─────────────────────────────────────────────────────────────────────────────

class Runner:
    """Runs one backend command at a time, streaming stdout/stderr lines."""

    def __init__(self, out_queue: "queue.Queue[tuple[str, str]]"):
        self.q = out_queue
        self.proc: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None

    @property
    def busy(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def run(self, script: str, args: list[str]) -> None:
        if self.busy:
            return
        # -u: unbuffered child stdout — without it Python block-buffers into
        # the pipe and the "live" log shows nothing until the process exits.
        cmd = [str(venv_python()), "-u", str(SCRIPTS_DIR / script)] + args
        self.q.put(("cmd", " ".join(f'"{c}"' if " " in c else c for c in cmd)))
        self.thread = threading.Thread(target=self._worker, args=(cmd,), daemon=True)
        self.thread.start()

    def cancel(self) -> None:
        if self.busy and self.proc:
            try:
                if os.name == "nt":
                    # Kill the whole tree — terminate() would only stop the
                    # Python wrapper and leave HandBrake/Topaz encoding forever.
                    subprocess.run(
                        ["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    self.proc.kill()
                self.q.put(("warn", "── Cancelled by user ──"))
            except Exception:
                pass

    def _worker(self, cmd: list[str]) -> None:
        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NO_WINDOW  # no console popup
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                bufsize=1,
                creationflags=flags,
                cwd=str(TOOLKIT_ROOT),
            )
            assert self.proc.stdout is not None
            for line in self.proc.stdout:
                self.q.put(("line", line.rstrip("\n")))
            code = self.proc.wait()
            if code == 0:
                self.q.put(("done", "✓ Finished successfully."))
            else:
                self.q.put(("error", f"✗ Exited with code {code}."))
        except FileNotFoundError:
            self.q.put(("error", "Could not find the venv Python. Run GimmeTools.bat to set up first."))
        except Exception as e:
            self.q.put(("error", f"Error: {e}"))
        finally:
            self.proc = None


# ─────────────────────────────────────────────────────────────────────────────
#  APP
# ─────────────────────────────────────────────────────────────────────────────

class GimmeTools(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")

        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("900x720")
        self.minsize(760, 620)
        self.configure(fg_color=BG)

        self.q: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self.runner = Runner(self.q)
        self.mode = "Remove Background"
        self.input_path = tk.StringVar()
        self.batch = tk.BooleanVar(value=False)

        self._build()
        self._poll_queue()

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)  # log row expands

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        ctk.CTkLabel(header, text="Gimme", font=(F_DISP, 30), text_color=TEXT
                     ).pack(side="left")
        ctk.CTkLabel(header, text="Tools", font=(F_DISP, 30), text_color=NEON
                     ).pack(side="left")
        ctk.CTkLabel(header, text="  local media toolkit", font=(F_UI, 13),
                     text_color=MUTED).pack(side="left", pady=(12, 0))

        # Mode selector
        self.seg = ctk.CTkSegmentedButton(
            self,
            values=["Remove Background", "Upscale Image", "Process Video"],
            command=self._on_mode,
            font=(F_UI, 13, "bold"),
            fg_color=PANEL, selected_color=PURPLE, selected_hover_color=VIOLET,
            unselected_color=CARD, unselected_hover_color=CARD2,
            text_color=TEXT,
        )
        self.seg.set(self.mode)
        self.seg.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 10))

        # Input row
        inp = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12, border_width=1,
                           border_color=BORDER)
        inp.grid(row=2, column=0, sticky="ew", padx=20, pady=4)
        inp.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            inp, textvariable=self.input_path, font=(F_MONO, 12),
            placeholder_text="Pick a file or folder…",
            fg_color=CARD, border_color=BORDER, text_color=TEXT, height=38,
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(12, 6), pady=12)

        ctk.CTkButton(inp, text="File", width=70, font=(F_UI, 12, "bold"),
                      fg_color=CARD2, hover_color=BORDER, text_color=TEXT,
                      command=self._browse_file
                      ).grid(row=0, column=1, padx=2, pady=12)
        ctk.CTkButton(inp, text="Folder", width=70, font=(F_UI, 12, "bold"),
                      fg_color=CARD2, hover_color=BORDER, text_color=TEXT,
                      command=self._browse_folder
                      ).grid(row=0, column=2, padx=(2, 12), pady=12)

        # Options panel (mode-specific, swapped)
        self.opts = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12,
                                 border_width=1, border_color=BORDER)
        self.opts.grid(row=3, column=0, sticky="ew", padx=20, pady=4)
        self.opts.grid_columnconfigure(99, weight=1)
        self._build_options()

        # Log panel
        logwrap = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12,
                               border_width=1, border_color=BORDER)
        logwrap.grid(row=4, column=0, sticky="nsew", padx=20, pady=4)
        logwrap.grid_rowconfigure(0, weight=1)
        logwrap.grid_columnconfigure(0, weight=1)

        self.log = ctk.CTkTextbox(
            logwrap, font=(F_MONO, 11), fg_color="#060509",
            text_color=MUTED, border_width=0, wrap="word",
        )
        self.log.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.log.configure(state="disabled")
        self._log_tags()

        # Action bar
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=5, column=0, sticky="ew", padx=20, pady=(6, 16))
        bar.grid_columnconfigure(0, weight=1)

        self.status = ctk.CTkLabel(bar, text="Ready.", font=(F_UI, 12),
                                   text_color=MUTED, anchor="w")
        self.status.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(bar, text="Diagnostics", width=110, font=(F_UI, 12, "bold"),
                      fg_color=CARD2, hover_color=BORDER, text_color=PURPLE_L,
                      command=self._run_diagnose
                      ).grid(row=0, column=1, padx=4)
        self.cancel_btn = ctk.CTkButton(
            bar, text="Cancel", width=90, font=(F_UI, 12, "bold"),
            fg_color=CARD2, hover_color="#3a1f2a", text_color=ERR,
            command=self.runner.cancel, state="disabled")
        self.cancel_btn.grid(row=0, column=2, padx=4)
        self.run_btn = ctk.CTkButton(
            bar, text="▶  Run", width=140, height=40, font=(F_UI, 14, "bold"),
            fg_color=PURPLE, hover_color=VIOLET, text_color="#ffffff",
            command=self._run)
        self.run_btn.grid(row=0, column=3, padx=(4, 0))

        self._welcome()

    def _build_options(self):
        """Rebuild the options row for the current mode."""
        for w in self.opts.winfo_children():
            w.destroy()

        pad = dict(padx=(12, 6), pady=12)

        if self.mode == "Remove Background":
            ctk.CTkLabel(self.opts, text="Model", font=(F_UI, 12, "bold"),
                         text_color=MUTED).grid(row=0, column=0, **pad)
            default = _cfg.get("background_removal", "model", default="birefnet-general") if _cfg else "birefnet-general"
            self.bg_model = ctk.CTkOptionMenu(
                self.opts,
                values=["birefnet-general", "birefnet-portrait", "isnet-general-use",
                        "u2net", "u2netp", "u2net_human_seg"],
                font=(F_UI, 12), fg_color=CARD, button_color=PURPLE,
                button_hover_color=VIOLET, text_color=TEXT, width=190)
            self.bg_model.set(default)
            self.bg_model.grid(row=0, column=1, pady=12)
            self._gpu_menu(col=2, key=("background_removal", "gpu"))
            self._batch_switch(col=3)

        elif self.mode == "Upscale Image":
            ctk.CTkLabel(self.opts, text="Model", font=(F_UI, 12, "bold"),
                         text_color=MUTED).grid(row=0, column=0, **pad)
            default = _cfg.get("upscale", "model", default="realesrgan-x4plus") if _cfg else "realesrgan-x4plus"
            self.up_model = ctk.CTkOptionMenu(
                self.opts,
                values=["realesrgan-x4plus", "realesrgan-x4plus-anime",
                        "realesrnet-x4plus", "realesr-animevideov3"],
                font=(F_UI, 12), fg_color=CARD, button_color=PURPLE,
                button_hover_color=VIOLET, text_color=TEXT, width=200,
                command=self._on_upscale_model)
            self.up_model.set(default)
            self.up_model.grid(row=0, column=1, pady=12)

            ctk.CTkLabel(self.opts, text="Scale", font=(F_UI, 12, "bold"),
                         text_color=MUTED).grid(row=0, column=2, padx=(16, 6), pady=12)
            dscale = str(_cfg.get("upscale", "scale", default=4)) if _cfg else "4"
            self.up_scale = ctk.CTkOptionMenu(
                self.opts, values=["2", "3", "4"], font=(F_UI, 12),
                fg_color=CARD, button_color=PURPLE, button_hover_color=VIOLET,
                text_color=TEXT, width=70)
            self.up_scale.set(dscale)
            self.up_scale.grid(row=0, column=3, pady=12)
            self._batch_switch(col=4)
            self._on_upscale_model(default)

        else:  # Process Video
            self.skip_topaz = tk.BooleanVar(value=False)
            ctk.CTkSwitch(self.opts, text="Skip Topaz (HandBrake only)",
                          variable=self.skip_topaz, font=(F_UI, 12),
                          progress_color=PURPLE, text_color=TEXT
                          ).grid(row=0, column=0, padx=14, pady=14, sticky="w")
            self._batch_switch(col=1)
            ctk.CTkLabel(self.opts,
                         text="Topaz is optional — auto-detected if installed.",
                         font=(F_UI, 11), text_color=FAINT
                         ).grid(row=0, column=2, padx=14, pady=14, sticky="w")

    def _gpu_menu(self, col: int, key: tuple[str, str]):
        ctk.CTkLabel(self.opts, text="GPU", font=(F_UI, 12, "bold"),
                     text_color=MUTED).grid(row=0, column=col, padx=(16, 6), pady=12)
        default = _cfg.get(*key, default="auto") if _cfg else "auto"
        self.gpu_menu = ctk.CTkOptionMenu(
            self.opts, values=["auto", "cpu", "cuda", "directml"],
            font=(F_UI, 12), fg_color=CARD, button_color=PURPLE,
            button_hover_color=VIOLET, text_color=TEXT, width=110)
        self.gpu_menu.set(default)
        self.gpu_menu.grid(row=0, column=col + 1, pady=12)

    def _batch_switch(self, col: int):
        ctk.CTkSwitch(self.opts, text="Batch (folder)", variable=self.batch,
                      font=(F_UI, 12), progress_color=NEON_DIM, text_color=TEXT
                      ).grid(row=0, column=col, padx=16, pady=12)

    # ── Logging into the textbox ────────────────────────────────────────────

    def _log_tags(self):
        # CTkTextbox wraps a tk.Text — configure color tags on the underlying widget.
        t = self.log._textbox
        t.tag_config("cmd",   foreground=FAINT)
        t.tag_config("line",  foreground=MUTED)
        t.tag_config("ok",    foreground=OK)
        t.tag_config("warn",  foreground="#fbbf24")
        t.tag_config("error", foreground=ERR)
        t.tag_config("info",  foreground=PURPLE_L)

    def _append(self, text: str, tag: str = "line"):
        t = self.log._textbox
        self.log.configure(state="normal")
        t.insert("end", text + "\n", tag)
        t.see("end")
        self.log.configure(state="disabled")

    def _welcome(self):
        self._append("GimmeTools ready.", "info")
        self._append(f"Toolkit: {TOOLKIT_ROOT}", "cmd")
        py = venv_python()
        if "venv" not in str(py):
            self._append("⚠ venv not found — run GimmeTools.bat to set up first.", "warn")
        else:
            self._append("Pick a file, choose options, hit Run.", "line")

    # ── Actions ─────────────────────────────────────────────────────────────

    def _on_mode(self, value: str):
        self.mode = value
        self.batch.set(False)
        self._build_options()

    def _on_upscale_model(self, model: str):
        # Only realesr-animevideov3 is multi-scale; the others are fixed 4x
        # and the binary hard-fails on any other -s value.
        if model == "realesr-animevideov3":
            self.up_scale.configure(state="normal")
        else:
            self.up_scale.set("4")
            self.up_scale.configure(state="disabled")

    def _browse_file(self):
        types = VIDEO_TYPES if self.mode == "Process Video" else IMAGE_TYPES
        path = filedialog.askopenfilename(title="Choose a file", filetypes=types)
        if path:
            self.input_path.set(path)
            self.batch.set(False)

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Choose a folder (batch)")
        if path:
            self.input_path.set(path)
            self.batch.set(True)

    def _run(self):
        if self.runner.busy:
            return
        target = self.input_path.get().strip()
        if not target:
            self.status.configure(text="Pick a file or folder first.", text_color=ERR)
            return
        if not Path(target).exists():
            self.status.configure(text="That path does not exist.", text_color=ERR)
            return

        script, args = self._build_command(target)
        self._set_running(True)
        self._append("", "line")
        self._append(f"── {self.mode} ──", "info")
        self.runner.run(script, args)

    def _build_command(self, target: str) -> tuple[str, list[str]]:
        args = [target]
        if self.batch.get():
            args.append("--batch")

        if self.mode == "Remove Background":
            args += ["--model", self.bg_model.get(), "--gpu", self.gpu_menu.get()]
            return "remove_bg.py", args

        if self.mode == "Upscale Image":
            args += ["--model", self.up_model.get(), "--scale", self.up_scale.get()]
            return "upscale_image.py", args

        # Process Video
        if self.skip_topaz.get():
            args.append("--skip-topaz")
        return "process_video.py", args

    def _run_diagnose(self):
        if self.runner.busy:
            return
        self._set_running(True)
        self._append("", "line")
        self._append("── Diagnostics ──", "info")
        self.runner.run("diagnose.py", [])

    def _set_running(self, running: bool):
        if running:
            self.run_btn.configure(state="disabled", text="Working…")
            self.cancel_btn.configure(state="normal")
            self.status.configure(text="Working…", text_color=NEON)
        else:
            self.run_btn.configure(state="normal", text="▶  Run")
            self.cancel_btn.configure(state="disabled")

    # ── Queue pump (worker thread → UI) ─────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "cmd":
                    self._append(f"$ {payload}", "cmd")
                elif kind == "line":
                    self._append(payload, self._classify(payload))
                elif kind == "done":
                    self._append(payload, "ok")
                    self.status.configure(text="Done.", text_color=OK)
                    self._set_running(False)
                elif kind == "error":
                    self._append(payload, "error")
                    self.status.configure(text="Failed — see log.", text_color=ERR)
                    self._set_running(False)
                elif kind == "warn":
                    self._append(payload, "warn")
                    self.status.configure(text="Cancelled.", text_color="#fbbf24")
                    self._set_running(False)
        except queue.Empty:
            pass
        self.after(60, self._poll_queue)

    @staticmethod
    def _classify(line: str) -> str:
        low = line.lower()
        if "error" in low or "fail" in low or "[ fail" in low:
            return "error"
        if "warn" in low or "[ warn" in low:
            return "warn"
        if "[  ok" in low or "completed" in low or "✓" in line:
            return "ok"
        return "line"


def main():
    try:
        app = GimmeTools()
        app.mainloop()
    except Exception:
        # Launched via pythonw there is no console — without this, any
        # startup crash is completely invisible to the user.
        import traceback
        crash = traceback.format_exc()
        try:
            log_path = TOOLKIT_ROOT / "logs" / "ui-crash.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(crash, encoding="utf-8")
        except Exception:
            log_path = None
        try:
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            where = f"\n\nDetails: {log_path}" if log_path else ""
            messagebox.showerror(
                "GimmeTools failed to start",
                f"{crash.strip().splitlines()[-1]}{where}",
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
