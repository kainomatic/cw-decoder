# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Dialog "Fehler melden…": Vorschau, lokal speichern, auf GitHub melden
(ADR-0008). Der Bericht wird nur angezeigt; gesendet wird nichts."""
import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import error_report
from .gui_tooltip import attach_tooltip

log = logging.getLogger(__name__)

_LBL_TITLE = "Fehler melden"
_LBL_INFO = ("Vorschau des Fehlerberichts. Das Programm sendet nichts selbst: "
             "„Auf GitHub melden“ öffnet nur den Browser mit einem vorausgefüllten "
             "Issue, das dort geprüft und abgeschickt wird (GitHub-Konto nötig).")
_LBL_SAVE = "Lokal speichern…"
_LBL_GITHUB = "Auf GitHub melden"
_LBL_LOGDIR = "Log-Ordner öffnen"
_LBL_CLOSE = "Schließen"
_LBL_SAVE_TITLE = "Fehlerbericht speichern"
_LBL_FILETYPE = "Textdatei"

_MSG_SAVED_TITLE = "Gespeichert"
_MSG_SAVED = "Fehlerbericht gespeichert:\n{path}"
_MSG_SAVE_FAILED = "Speichern fehlgeschlagen:\n{err}"
_MSG_TRUNCATED_TITLE = "Bericht gekürzt"
_MSG_TRUNCATED = ("Der Bericht war für einen Link zu lang; im Browser fehlen die "
                  "ältesten Logzeilen. Bitte zusätzlich „Lokal speichern…“ und die "
                  "Datei an das Issue anhängen.")
_MSG_BROWSER_FAILED = "Browser konnte nicht geöffnet werden. Link:\n{url}"
_MSG_ISSUE_TITLE = "Fehlerbericht CW Decoder {version}"

_TT_PREVIEW = ("So sieht der Bericht aus: Version, System, Audiogerät und die "
               "letzten Logzeilen. Nutzerordner sind durch ~ ersetzt; keine Audiodaten.")
_TT_SAVE = "Bericht als Textdatei speichern, z. B. zum Anhängen an eine E-Mail."
_TT_GITHUB = ("Öffnet im Browser ein vorausgefülltes Issue auf GitHub. "
              "Abgeschickt wird erst mit „Submit“ im Browser.")
_TT_LOGDIR = "Ordner mit cwdecoder.log im Explorer öffnen."


class ErrorReportDialog:
    def __init__(self, parent, report_text, version, save_dir, log_dir):
        self.report_text = report_text
        self.version = version
        self.save_dir = Path(save_dir)
        self.log_dir = Path(log_dir)
        self.top = tk.Toplevel(parent)
        self.top.title(_LBL_TITLE)
        self.top.minsize(560, 380)
        self.top.transient(parent)
        self._build()

    def _build(self):
        t = self.top
        t.columnconfigure(0, weight=1)
        t.rowconfigure(1, weight=1)
        ttk.Label(t, text=_LBL_INFO, wraplength=600, justify="left").grid(
            row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        txt = scrolledtext.ScrolledText(t, wrap="none", height=20, width=90,
                                        font=("Consolas", 9))
        txt.insert("1.0", self.report_text)
        txt.configure(state="disabled")
        txt.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        attach_tooltip(txt, _TT_PREVIEW)

        row = ttk.Frame(t, padding=(10, 6))
        row.grid(row=2, column=0, sticky="ew")
        for label, cmd, tip in ((_LBL_SAVE, self._save, _TT_SAVE),
                                (_LBL_GITHUB, self._github, _TT_GITHUB),
                                (_LBL_LOGDIR, self._open_logdir, _TT_LOGDIR)):
            b = ttk.Button(row, text=label, command=cmd)
            b.pack(side="left", padx=(0, 6))
            attach_tooltip(b, tip)
        ttk.Button(row, text=_LBL_CLOSE, command=t.destroy).pack(side="right")
        t.bind("<Escape>", lambda _e: t.destroy())

    def _save(self):
        path = filedialog.asksaveasfilename(
            parent=self.top, title=_LBL_SAVE_TITLE, defaultextension=".txt",
            initialdir=str(self.save_dir), initialfile=error_report.default_report_name(),
            filetypes=[(_LBL_FILETYPE, "*.txt")])
        if not path:
            return
        try:
            error_report.save_report(self.report_text, path)
        except OSError as e:
            log.error("Fehlerbericht nicht gespeichert: %s", e)
            messagebox.showerror(_LBL_TITLE, _MSG_SAVE_FAILED.format(err=e), parent=self.top)
            return
        log.info("Fehlerbericht gespeichert: %s", path)
        messagebox.showinfo(_MSG_SAVED_TITLE, _MSG_SAVED.format(path=path), parent=self.top)

    def _github(self):
        url, truncated = error_report.build_issue_url(
            _MSG_ISSUE_TITLE.format(version=self.version), self.report_text)
        log.info("Fehlerbericht: GitHub-Issue im Browser geöffnet (gekürzt: %s)", truncated)
        if not error_report.open_in_browser(url):
            messagebox.showwarning(_LBL_TITLE, _MSG_BROWSER_FAILED.format(url=url),
                                   parent=self.top)
            return
        if truncated:
            messagebox.showinfo(_MSG_TRUNCATED_TITLE, _MSG_TRUNCATED, parent=self.top)

    def _open_logdir(self):
        open_folder_or_report(self.top, self.log_dir)


def open_folder_or_report(parent, path):
    """Ordner öffnen; klappt das nicht, Fehlerdialog statt Absturz."""
    from .gui_errors import report_exception
    from .paths import open_folder
    try:
        open_folder(path)
    except OSError as e:
        report_exception(parent, e, f"Ordner öffnen: {path}")
