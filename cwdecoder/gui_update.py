# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Update-Dialog (ADR-0013): aktuelle und neue Version, Link zu den
Release-Notes, "Herunterladen und installieren" mit Fortschritt, "Später",
Haken "Nicht mehr an Updates erinnern".

Threading (ADR-0009): Der Download läuft in einem eigenen Thread und meldet
Fortschritt, Ergebnis und Fehler über die Queue self.msgs; _poll() holt sie
per after() im tk-Thread ab.

    UpdateDialog(parent, current_version, result,
                 on_install=lambda path: ...,   # Installer starten, App beenden
                 on_later=lambda: ...,          # Hinweis im Hilfe-Menü
                 on_opt_out=lambda: ...)        # update_check = false
"""
import logging
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk

from .gui_tooltip import attach_tooltip
from .updater import UpdateError, download_update

log = logging.getLogger(__name__)

POLL_MS = 50

# -- Beschriftungen --------------------------------------------------------
_LBL_TITLE = "Update verfügbar"
_LBL_HEAD = "Eine neue Version des CW Decoders ist verfügbar."
_LBL_CURRENT = "Installiert:"
_LBL_NEW = "Neu:"
_LBL_NOTES = "Release-Notes ansehen"
_LBL_INSTALL = "Herunterladen und installieren"
_LBL_LATER = "Später"
_LBL_OPT_OUT = "Nicht mehr an Updates erinnern"

# -- Meldungen -------------------------------------------------------------
_MSG_DOWNLOADING = "Lade herunter … {done:.1f} von {total:.1f} MB"
_MSG_STARTING = "Download fertig – Installer startet, der CW Decoder beendet sich."
_MSG_FAILED = "Download fehlgeschlagen: {err}"

# -- Tooltips --------------------------------------------------------------
_TT_NOTES = "Änderungen der neuen Version auf GitHub im Browser öffnen."
_TT_INSTALL = ("Setup-Datei von GitHub laden und installieren. Der CW Decoder "
               "beendet sich dafür und startet danach mit der neuen Version neu.")
_TT_LATER = ("Dialog schließen. Das Update bleibt im Hilfe-Menü erreichbar "
             "und wird beim nächsten Start wieder angeboten.")
_TT_OPT_OUT = ("Beim Start nicht mehr automatisch nach Updates suchen. "
               "Hilfe → Nach Updates suchen geht weiterhin.")
_TT_PROGRESS = "Fortschritt des Downloads."


class UpdateDialog:
    def __init__(self, parent, current_version, result, on_install, on_later,
                 on_opt_out, download=download_update):
        self.result = result
        self.on_install = on_install
        self.on_later = on_later
        self.on_opt_out = on_opt_out
        self.download = download
        self.msgs = queue.Queue()
        self.downloading = False
        self.closed = False

        top = self.top = tk.Toplevel(parent)
        top.title(_LBL_TITLE)
        top.resizable(False, False)
        try:
            top.transient(parent)
        except tk.TclError:
            pass
        frm = ttk.Frame(top, padding=16)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=_LBL_HEAD, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        grid = ttk.Frame(frm)
        grid.pack(anchor="w", pady=(8, 4))
        ttk.Label(grid, text=_LBL_CURRENT).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(grid, text=f"v{current_version}").grid(row=0, column=1, sticky="w")
        ttk.Label(grid, text=_LBL_NEW).grid(row=1, column=0, sticky="w", padx=(0, 10))
        ttk.Label(grid, text=f"v{result.new_version}",
                  font=("Segoe UI", 9, "bold")).grid(row=1, column=1, sticky="w")

        if result.release_url:
            link = ttk.Label(frm, text=_LBL_NOTES, foreground="#1a5fb4", cursor="hand2")
            link.pack(anchor="w", pady=(2, 8))
            link.bind("<Button-1>", lambda _e: webbrowser.open(result.release_url))
            attach_tooltip(link, _TT_NOTES)

        self.progress = ttk.Progressbar(frm, length=380, mode="determinate")
        attach_tooltip(self.progress, _TT_PROGRESS)
        self.info_var = tk.StringVar(value="")
        self.info = ttk.Label(frm, textvariable=self.info_var, wraplength=380,
                              justify="left")

        self.opt_out_var = tk.BooleanVar(value=False)
        cb = ttk.Checkbutton(frm, text=_LBL_OPT_OUT, variable=self.opt_out_var)
        cb.pack(anchor="w", pady=(8, 0))
        attach_tooltip(cb, _TT_OPT_OUT)

        row = ttk.Frame(frm)
        row.pack(fill="x", pady=(12, 0))
        self.btn_later = ttk.Button(row, text=_LBL_LATER, command=self.later)
        self.btn_later.pack(side="right")
        attach_tooltip(self.btn_later, _TT_LATER)
        self.btn_install = ttk.Button(row, text=_LBL_INSTALL, command=self.start_download)
        self.btn_install.pack(side="right", padx=(0, 8))
        attach_tooltip(self.btn_install, _TT_INSTALL)
        self.btn_install.focus_set()

        top.protocol("WM_DELETE_WINDOW", self.later)
        top.bind("<Escape>", lambda _e: self.later())
        self._poll_id = top.after(POLL_MS, self._poll)

    # ------------------------------------------------------------------
    def start_download(self):
        if self.downloading:
            return
        self.downloading = True
        self.btn_install.configure(state="disabled")
        self.btn_later.configure(state="disabled")
        self.progress.configure(value=0, maximum=max(self.result.asset.size, 1))
        self.progress.pack(fill="x", pady=(8, 0), before=self.btn_install.master)
        self.info.pack(anchor="w", pady=(4, 0), before=self.btn_install.master)
        self.info_var.set(_MSG_DOWNLOADING.format(done=0, total=self.result.asset.size / 1e6))
        threading.Thread(target=self._download_thread, daemon=True,
                         name="update-download").start()

    def _download_thread(self):
        """Läuft im Download-Thread: kein tk-Aufruf, nur die Queue."""
        try:
            path = self.download(self.result.asset,
                                 on_progress=lambda d, t: self.msgs.put(("progress", (d, t))))
        except UpdateError as e:
            self.msgs.put(("error", str(e)))
        except Exception as e:  # noqa: BLE001 - im Dialog anzeigen statt Thread-Tod
            log.exception("Update-Download: unerwarteter Fehler")
            self.msgs.put(("error", f"{type(e).__name__}: {e}"))
        else:
            self.msgs.put(("done", path))

    def _poll(self):
        if self.closed:
            return
        try:
            while True:
                kind, val = self.msgs.get_nowait()
                if kind == "progress":
                    done, total = val
                    self.progress.configure(value=done, maximum=max(total, 1))
                    self.info_var.set(_MSG_DOWNLOADING.format(done=done / 1e6,
                                                              total=total / 1e6))
                elif kind == "error":
                    self.downloading = False
                    self.btn_install.configure(state="normal")
                    self.btn_later.configure(state="normal")
                    self.info_var.set(_MSG_FAILED.format(err=val))
                elif kind == "done":
                    self.info_var.set(_MSG_STARTING)
                    self.top.update_idletasks()
                    self.close()
                    self.on_install(val)
                    return
        except queue.Empty:
            pass
        self._poll_id = self.top.after(POLL_MS, self._poll)

    def later(self):
        if self.downloading:
            return
        opt_out = bool(self.opt_out_var.get())
        self.close()
        if opt_out:
            self.on_opt_out()
        else:
            self.on_later()

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.top.after_cancel(self._poll_id)
        except tk.TclError:
            pass
        self.top.destroy()
