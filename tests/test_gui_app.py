# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""GUI: Fenstertitel, Einstellungen, Menü, Rauchtest."""
import gc
import json
import os
import re
import subprocess
import sys

import pytest

from conftest import requires_display

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_window_title():
    pytest.importorskip("tkinter", reason="tkinter fehlt")
    from cwdecoder.__version__ import __version__
    from cwdecoder.gui import window_title
    assert window_title("stable") == f"CW Decoder v{__version__}"
    assert window_title("beta") == f"CW Decoder v{__version__} BETA"
    assert window_title("stable", "1.2.3") == "CW Decoder v1.2.3"


def test_gui_texts_are_constants():
    """Alle Tooltip-, Label- und Meldungstexte als Modulkonstanten."""
    pytest.importorskip("tkinter", reason="tkinter fehlt")
    from cwdecoder import gui
    names = [n for n in vars(gui) if n.startswith(("_LBL_", "_MSG_", "_TT_"))]
    assert len([n for n in names if n.startswith("_TT_")]) >= 10
    assert all(isinstance(getattr(gui, n), str) for n in names)


@pytest.fixture
def app(app_env, monkeypatch):
    sys.path.insert(0, os.path.dirname(__file__))
    import gui_smoke
    monkeypatch.setitem(sys.modules, "sounddevice", gui_smoke.make_fake_sounddevice(48000))
    from cwdecoder import config
    from cwdecoder.gui import App
    path = config.get_config_path()
    config.save(dict(config.defaults(), record_default=True, fixed_freq=650.0), path)
    a = App(cfg=config.load(path), config_path=path)
    a.update()
    yield a
    a._quit()
    # Tk-Objekte im Hauptthread abräumen (sonst räumt sie später ein
    # Hilfs-Thread ab, z. B. von subprocess, und Tcl stürzt ab)
    del a
    gc.collect()


@requires_display
@pytest.mark.gui
def test_app_reads_and_writes_config(app):
    from cwdecoder import config
    assert app.rec_var.get() is True
    assert app.auto_var.get() is False and app.fixed_freq == 650.0
    assert app.dev_var.get().endswith("Fake USB Audio")
    app.auto_var.set(True)
    app._auto_changed()
    app.wipe_var.set(False)
    app._n1mm_changed()
    app._device_changed()
    saved = json.loads(config.get_config_path().read_text(encoding="utf-8"))
    assert saved["fixed_freq"] is None
    assert saved["n1mm_wipe"] is False
    assert saved["device_name"] == "Fake USB Audio"


@requires_display
@pytest.mark.gui
def test_cli_override_is_not_saved(app_env, monkeypatch):
    sys.path.insert(0, os.path.dirname(__file__))
    import gui_smoke
    monkeypatch.setitem(sys.modules, "sounddevice", gui_smoke.make_fake_sounddevice(48000))
    from cwdecoder import config
    from cwdecoder.gui import App
    path = config.get_config_path()
    a = App(n1mm=False, cfg=dict(config.defaults(), n1mm_enabled=True), config_path=path)
    try:
        assert a.n1mm_var.get() is False
        assert not path.exists()            # Start allein speichert nichts
    finally:
        a._quit()
        del a
        gc.collect()


@requires_display
@pytest.mark.gui
def test_menu_entries(app):
    labels = []
    for i in range(app.menubar.index("end") + 1):
        if app.menubar.type(i) != "cascade":
            continue
        sub = app.nametowidget(app.menubar.entrycget(i, "menu"))
        labels.append(app.menubar.entrycget(i, "label"))
        for k in range(sub.index("end") + 1):
            if sub.type(k) == "command":
                labels.append(sub.entrycget(k, "label"))
    for want in ("Datei", "Aufnahmeordner öffnen", "Beenden", "Hilfe", "Nach Updates suchen",
                 "Log-Ordner öffnen", "Fehler melden…", "Über CW Decoder"):
        assert want in labels


@requires_display
@pytest.mark.gui
def test_about_and_error_report_dialogs(app):
    dlg = app.show_about()
    app.update()
    dlg.destroy()
    rep = app.open_error_report()
    app.update()
    assert "Fehlerbericht" in rep.report_text and "Fake USB Audio" in rep.report_text
    rep.top.destroy()


@requires_display
@pytest.mark.gui
@pytest.mark.slow
def test_gui_smoke():
    """Bestehender GUI-Rauchtest, im eigenen Prozess (mehrere Tk-Fenster,
    ausgetauschtes sounddevice-Modul)."""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "gui_smoke.py")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr


@requires_display
@pytest.mark.gui
def test_rufzeichen_spalte_bei_hoher_skalierung(app_env, monkeypatch):
    """Bei 200 % Skalierung und 900 px Breite bleibt die rechte Spalte sichtbar (#9)."""
    sys.path.insert(0, os.path.dirname(__file__))
    import gui_smoke
    import tkinter as tk
    monkeypatch.setitem(sys.modules, "sounddevice", gui_smoke.make_fake_sounddevice(48000))
    orig_init = tk.Tk.__init__

    def scaled_init(self, *args, **kw):
        orig_init(self, *args, **kw)
        self.tk.call("tk", "scaling", 2.0)   # vor dem Anlegen der Widgets

    monkeypatch.setattr(tk.Tk, "__init__", scaled_init)
    from cwdecoder import config
    from cwdecoder.gui import App
    a = App(cfg=config.defaults(), config_path=config.get_config_path())
    try:
        a.geometry("900x560")
        a.update()
        assert a.right_col.winfo_ismapped()
        assert a.right_col.winfo_width() > 150, a.right_col.winfo_width()
    finally:
        a._quit()
        del a
        gc.collect()


@requires_display
@pytest.mark.gui
def test_rufzeichen_im_text_markiert_und_klickbar(app, monkeypatch):
    """Spotter-Positionen werden im Text markiert, Klick übergibt das Rufzeichen (#9)."""
    sent = []
    monkeypatch.setattr(app, "_send_call", sent.append)
    g = app.gen
    # Strom wie vom LiveDecoder: "CQ DE" + zusammengeklebt "DEDJ7PR"
    for piece in ["C", "Q", " ", "<BT>", " ", "D", "E", "D", "J", "7", "P", "R", " "]:
        app.msgs.put(("text", g, piece))
    # Zeichen ohne Leerzeichen: C0 Q1 <BT>2 D3 E4 D5 J6 7 7 P8 R9 -> DJ7PR = 5..10
    app.msgs.put(("span", g, ("DJ7PR", 5, 10)))
    app.msgs.put(("span", g + 1, ("XX1XX", 0, 2)))     # veraltete Generation: ignorieren
    app._poll()
    rng = app.text.tag_ranges("call")
    assert len(rng) == 2
    assert app.text.get(rng[0], rng[1]) == "DJ7PR"
    assert app.text.tag_ranges("call:DJ7PR")
    app.update()
    x, y, _w, h = app.text.bbox(rng[0])
    assert app._call_at(x + 1, y + h // 2) == "DJ7PR"

    class Ev:
        pass
    ev = Ev()
    ev.x, ev.y = x + 1, y + h // 2
    app._call_clicked(ev)
    assert sent == ["DJ7PR"] and app.calls[0] == "DJ7PR"
    app._clear()
    assert app._tokens == {}


@requires_display
@pytest.mark.gui
def test_rufzeichen_knoepfe_mit_flagge_und_land(app, monkeypatch):
    """Knopf: Rufzeichen, Flagge, Landesname; ohne Flagge bzw. ohne Land (#11)."""
    sent = []
    monkeypatch.setattr(app, "_send_call", sent.append)
    for call in ["OY1CT", "DP0GVN", "QQ1A", "UA9ABC", "DJ7PR"]:
        app._add_call(call)
    app.update()
    rows = app.call_rows
    # mit Flagge: Bild aus dem Cache, Name auf Deutsch
    oy = rows["OY1CT"]
    assert oy["name"]["text"] == "Färöer"
    assert str(oy["flag"]["image"]) == str(app._flag_cache["fo"])
    assert app._flag_cache["fo"].width() == 24
    # iso null (Antarktis): Platzhalter statt Flagge, Name trotzdem da
    ant = rows["DP0GVN"]
    assert ant["name"]["text"] == "Antarktis"
    assert str(ant["flag"]["image"]) == str(app._flag_cache[""])
    # unbekannt: nur das Rufzeichen
    qq = rows["QQ1A"]
    assert qq["flag"] is None and qq["name"] is None and qq["call"]["text"] == "QQ1A"
    # langer Name gekürzt, voll im Tooltip
    ru = rows["UA9ABC"]
    assert ru["name"]["text"] == "Asiat. Russla…"
    assert "Asiat. Russland (UA9, AS, CQ 17, ITU 30)" in ru["tooltip"]
    assert "\nDeutschland (DL, EU, CQ 14, ITU 28)\n" in rows["DJ7PR"]["tooltip"]
    assert rows["DJ7PR"]["tooltip"].endswith("in Super Check Partial")
    # feste Breite: alle Knöpfe mit Land gleich breit, Spalte springt nicht
    widths = {rows[c]["row"].winfo_reqwidth() for c in ("OY1CT", "DP0GVN", "UA9ABC", "DJ7PR")}
    assert len(widths) == 1, widths
    col = app.right_col.winfo_width()
    app._add_call("VP2VAB")      # Br. Jungfernins.
    app.update()
    assert app.right_col.winfo_width() == col
    # Klick auf Flagge bzw. Namen übergibt das Rufzeichen
    monkeypatch.setattr(app, "winfo_containing", lambda x, y: rows["OY1CT"]["flag"])
    rows = app.call_rows
    for part in ("flag", "name", "call"):
        w = rows["OY1CT"][part]
        monkeypatch.setattr(app, "winfo_containing", lambda x, y, w=w: w)
        w.event_generate("<ButtonPress-1>")
        w.event_generate("<ButtonRelease-1>")
    app.update()
    assert sent == ["OY1CT"] * 3
    # Tooltip der Markierung im Text nennt das Land
    assert "Färöer" in app._call_tooltip("x", "OY1CT")


@requires_display
@pytest.mark.gui
def test_unsichere_zeichen_grau_und_rufzeichen_tooltip(app):
    """Unsichere Zeichen tragen den Tag unsure; Rufzeichen-Markierung liegt
    darüber, Knopf-Tooltip nennt unsichere Zeichen (ADR-0023, #18)."""
    from cwdecoder import gui
    g = app.gen
    stream = [("C", 1.0), ("Q", 0.9), " ", ("O", 1.0), ("Z", 1.0), ("1", 0.2),
              ("H", 0.3), ("G", 1.0), ("T", 1.0), " "]
    for item in stream:
        if item == " ":
            app.msgs.put(("text", g, " "))
        else:
            app.msgs.put(("char", g, item))
    app.msgs.put(("call", g, "OZ1HGT"))
    app.msgs.put(("span", g, ("OZ1HGT", 2, 8)))
    app._poll()
    rng = app.text.tag_ranges(gui.UNSURE_TAG)
    grey = "".join(app.text.get(rng[i], rng[i + 1]) for i in range(0, len(rng), 2))
    assert grey == "1H"
    assert app.text.tag_cget(gui.UNSURE_TAG, "foreground") == gui.UNSURE_FG
    names = list(app.text.tag_names())
    assert names.index(gui.CALL_TAG) > names.index(gui.UNSURE_TAG)   # Priorität
    assert "OZ1HGT" in app.unsure_calls
    tip = app.call_rows["OZ1HGT"]["tooltip"]
    assert gui._TT_CALL_UNSURE in tip
    assert all(w._cw_tooltip.text == tip for w in app.call_rows["OZ1HGT"]["widgets"])
    assert app.call_rows["OZ1HGT"]["call"]["text"] == "OZ1HGT"     # Knopf-Text gleich
    # sicheres Vorkommen bestätigt das Rufzeichen
    for ch in "OZ1HGT":
        app.msgs.put(("char", g, (ch, 1.0)))
    app.msgs.put(("text", g, " "))
    app.msgs.put(("span", g, ("OZ1HGT", 8, 14)))
    app._poll()
    assert "OZ1HGT" not in app.unsure_calls
    assert gui._TT_CALL_UNSURE not in app.call_rows["OZ1HGT"]["tooltip"]


def _calls_visible(app, height):
    app.geometry(f"900x{height}")
    app.update()
    app._refit_calls()
    app.update()
    rows = [p["row"] for p in app.call_rows.values()]
    frame_bottom = app.call_frame.winfo_rooty() + app.call_frame.winfo_height()
    for r in rows:
        assert r.winfo_rooty() + r.winfo_height() <= frame_bottom, (height, r)
    cb = app.cb_n1mm
    assert cb.winfo_ismapped()
    win_bottom = app.winfo_rooty() + app.winfo_height()
    assert cb.winfo_rooty() + cb.winfo_height() <= win_bottom
    assert cb.winfo_rooty() >= frame_bottom
    return len(rows)


@requires_display
@pytest.mark.gui
def test_rufzeichen_spalte_nur_sichtbare_knoepfe(app):
    """#14: Bei 400 px Höhe und 12 Rufzeichen ragt kein Knopf aus der Spalte,
    der N1MM-Haken bleibt sichtbar; bei 900 px passen mehr Knöpfe."""
    app.minsize(760, 300)
    app.geometry("900x400")
    app.update()
    for k in range(12):
        app._add_call(f"DL{k}ABC")
    app.update()
    n_small = _calls_visible(app, 400)
    n_big = _calls_visible(app, 900)
    assert 0 < n_small < 12
    assert n_big > n_small
    assert app.calls[0] == "DL11ABC" and len(app.calls) == 12
    # neueste oben
    assert list(app.call_rows)[0] == "DL11ABC"
    # Größenänderung über <Configure> (entprellt) zieht die Liste nach
    import time
    app.geometry("900x400")
    t_end = time.monotonic() + 1.0
    while time.monotonic() < t_end:
        app.update()
    assert len(app.call_rows) == n_small


def _pump(app, secs, until=None):
    import time
    t_end = time.monotonic() + secs
    while time.monotonic() < t_end:
        app.update()
        if until is not None and until():
            return True
        time.sleep(0.01)
    return until() if until is not None else True


@requires_display
@pytest.mark.gui
def test_ringpuffer_speichern_und_nochmal_hoeren(app):
    """#19: Knöpfe, Strg+S/Strg+R, Quittung über App.msgs, Stopp der Wiedergabe."""
    import sounddevice
    from cwdecoder import gui
    from cwdecoder.paths import get_recordings_dir
    assert str(app.btn_save["state"]) == "disabled"
    assert str(app.btn_replay["state"]) == "disabled"
    assert app.btn_save["text"] == "Letzte 30 s speichern"
    assert app.btn_replay["text"] == "Nochmal hören"
    assert app.btn_save._cw_tooltip.text == gui._TT_SAVE_LAST
    assert app.btn_replay._cw_tooltip.text == gui._TT_REPLAY
    for seq in ("<Control-s>", "<Control-r>"):
        assert app.bind(seq)
    app.rec_var.set(False)
    app.auto_var.set(True)                          # Fixture: fest 650 Hz, Signal 700 Hz
    app._toggle()                                   # Start (Fake-Soundkarte)
    assert _pump(app, 5, lambda: "CQ" in app.text.get("1.0", "end"))
    assert str(app.btn_save["state"]) == "normal"
    # Strg+S im Textfeld: Speichern läuft im Hintergrund, Quittung über msgs
    app.text.focus_force()
    app.text.event_generate("<Control-s>")
    assert _pump(app, 5, lambda: app.saved_paths)
    wav = app.saved_paths[0]
    assert os.path.dirname(wav) == str(get_recordings_dir())
    assert wav.endswith("_letzte30s.wav") and os.path.exists(wav[:-4] + ".txt")
    assert "Gespeichert: " + os.path.basename(wav) in app.status.get()
    assert "Gespeichert" in app.status.get()        # bleibt trotz Status-Updates stehen
    _pump(app, 0.6)
    assert "Gespeichert" in app.status.get()
    assert "s" not in app.text.get("end-2c", "end")  # Strg+S tippt nichts ins Textfeld
    # Strg+R: Wiedergabe, Knopf wird „Stopp“, zweites Strg+R bricht ab
    app.text.event_generate("<Control-r>")
    assert app.btn_replay["text"] == "Stopp"
    assert _pump(app, 1, lambda: "Wiedergabe" in app.status.get())
    app.text.event_generate("<Control-r>")
    # nach dem Abbruch bleibt der Ausschnitt festgehalten (#25)
    assert _pump(app, 5, lambda: app.btn_replay["text"] == gui._LBL_REPLAY_HELD)
    out = sounddevice.played[-1]
    assert out.samplerate == 48000 and 0 < out.n < 10 * 48000
    assert "abort" in out.events
    assert "Wiedergabe abgebrochen" in app.status.get()
    assert re.search(r"festgehalten \d+ s – noch \d+ s", app.status.get())
    app._toggle()                                   # Stop
    app.hold.release()
    app._tick_hold()
    app._update_ring_buttons()
    assert str(app.btn_save["state"]) == "disabled"
    assert str(app.btn_replay["state"]) == "disabled"


@requires_display
@pytest.mark.gui
def test_ringpuffer_einstellungen(app):
    from cwdecoder import config
    menus = [app.menubar.entrycget(i, "label") for i in range(app.menubar.index("end") + 1)
             if app.menubar.type(i) == "cascade"]
    assert "Einstellungen" in menus
    dlg = app.open_ring_settings()
    app.update()
    assert all(e._cw_tooltip.text for e in dlg.entries.values())
    assert dlg.entry_rate._cw_tooltip.text and dlg.device_box._cw_tooltip.text
    dlg.set_text("save_last_s", "20")
    dlg.set_text("replay_s", "99")                  # ungültig: springt zurück
    assert dlg.apply() is False
    assert "ungültig" in dlg.note.cget("text")
    assert dlg.entries["replay_s"].get() == "10"
    assert app.btn_save["text"] == "Letzte 20 s speichern"
    dlg.set_text("replay_rate", "0,7")
    dlg.set_text("replay_hold_s", "8")
    dlg.set_text("ring_seconds", "15")              # kleiner als Speichern: kürzt mit
    dlg.close()
    saved = json.loads(config.get_config_path().read_text(encoding="utf-8"))
    assert saved["ring_seconds"] == 15 and saved["save_last_s"] == 15
    assert saved["replay_rate"] == 0.7 and saved["replay_s"] == 10
    assert saved["replay_hold_s"] == 8 and app.hold.hold_s == 8
    assert app.replay_rate_now == 0.7               # Regler springt auf das neue Starttempo
    assert app.ring_dialog is None


def _feed_word(app, g, word, cuts=(), spans=(), start=0):
    """Ein Wort wie vom LiveDecoder: Zeichen, am Wortende erst Zerlegung und
    Rufzeichen-Spannen (Spotter), dann das Leerzeichen."""
    for ch in word:
        app.msgs.put(("char", g, (ch, 1.0)))
    if cuts:
        app.msgs.put(("seg", g, [start + c for c in cuts]))
    for call, a, b in spans:
        app.msgs.put(("span", g, (call, a, b)))
    app.msgs.put(("text", g, " "))


@requires_display
@pytest.mark.gui
def test_scp_farben_vorschlag_und_trenner(app, monkeypatch):
    """ADR-0026, #23: grün = in SCP, gelb = nicht; Vorschlag bei genau einem
    Nachbarn; Trenner · grau im Text, echte Leerzeichen an die Engine."""
    from cwdecoder import config, gui, scp
    monkeypatch.setattr(scp, "DEFAULT", scp.ScpDb({"DJ7PR", "IZ4BPF", "OY1CT", "OY1CW"}))
    fed, sent = [], []
    monkeypatch.setattr(app, "_engine_emit", fed.append)
    app._engine_words.emit = fed.append
    monkeypatch.setattr(app, "_send_call", sent.append)
    g = app.gen
    # DEDJ7PR -> DE·DJ7PR (Strom: D0 E1 D2 J3 7 4 P5 R6)
    _feed_word(app, g, "DEDJ7PR", cuts=[2], spans=[("DJ7PR", 2, 7)])
    _feed_word(app, g, "Z4BPF", spans=[("Z4BPF", 7, 12)], start=7)
    _feed_word(app, g, "OY1CQ", spans=[("OY1CQ", 12, 17)], start=12)
    for c in ("DJ7PR", "Z4BPF", "OY1CQ"):
        app.msgs.put(("call", g, c))
    app._poll()
    app.update()
    assert app.text.get("1.0", "end-1c") == f"DE{gui.SEGMENT_SEP}DJ7PR Z4BPF OY1CQ "
    rng = app.text.tag_ranges(gui.INFERRED_TAG)
    assert [app.text.get(rng[0], rng[1])] == [gui.SEGMENT_SEP]
    assert app.text.tag_cget(gui.INFERRED_TAG, "foreground") == gui.INFERRED_FG
    # Markierung trotz eingefügtem Trenner an der richtigen Stelle
    calls = app.text.tag_ranges(gui.CALL_TAG)
    marked = [app.text.get(calls[i], calls[i + 1]) for i in range(0, len(calls), 2)]
    assert marked == ["DJ7PR", "Z4BPF", "OY1CQ"]
    green = app.text.tag_ranges(gui.CALL_SCP_TAG)
    assert [app.text.get(green[0], green[1])] == ["DJ7PR"] and len(green) == 2
    names = list(app.text.tag_names())
    assert names.index(gui.CALL_SCP_TAG) > names.index(gui.CALL_TAG)
    # N1MM-Engine bekommt echte Leerzeichen, je Wort am Wortende
    assert "".join(fed) == "DE DJ7PR Z4BPF OY1CQ "
    # Knöpfe: grün bzw. gelb, Tooltips mit SCP-Zeile und Vorschlag
    rows = app.call_rows
    assert rows["DJ7PR"]["call"]["bg"] == gui.CALL_SCP_BG
    assert rows["Z4BPF"]["call"]["bg"] == gui.CALL_TAG_BG
    assert rows["DJ7PR"]["tooltip"].endswith(gui._TT_CALL_SCP)
    tip = rows["Z4BPF"]["tooltip"]
    assert gui._TT_CALL_NOT_SCP in tip and "ähnlich: IZ4BPF" in tip
    assert gui._TT_CALL_ADOPT.format(call="IZ4BPF") in tip
    tip = rows["OY1CQ"]["tooltip"]
    assert "ähnlich: OY1CT, OY1CW" in tip and "übernehmen" not in tip
    assert app.call_suggestion("Z4BPF") == "IZ4BPF"
    assert app.call_suggestion("OY1CQ") is None         # mehrere: kein Vorschlag
    assert app.call_suggestion("DJ7PR") is None         # bekannt: nichts
    assert rows["Z4BPF"]["call"].bind("<Button-3>")
    # übernehmen: Knopf ersetzt, Übergabe wie Klick, nie automatisch
    assert sent == []
    app.adopt_call("Z4BPF", "IZ4BPF")
    assert "IZ4BPF" in app.calls and "Z4BPF" not in app.calls
    assert sent == ["IZ4BPF"]
    assert app.call_rows["IZ4BPF"]["call"]["bg"] == gui.CALL_SCP_BG
    # Menü: Zerlegung aus -> gespeichert, Engine bekommt wieder sofort jedes Zeichen
    app.segment_var.set(False)
    app._segment_changed()
    assert config.load(app.config_path)["segment_words"] is False
    fed.clear()
    app.msgs.put(("char", g, ("K", 1.0)))
    app._poll()
    assert fed == ["K"]


@requires_display
@pytest.mark.gui
def test_menue_zerlegung(app):
    from cwdecoder import gui
    labels = [app.settings_menu.entrycget(k, "label")
              for k in range(app.settings_menu.index("end") + 1)
              if app.settings_menu.type(k) == "checkbutton"]
    assert labels == [gui._LBL_MENU_SEGMENT, gui._LBL_MENU_ENGINE_SEG]
    assert app.segment_var.get() is True and app.engine_seg_var.get() is True


@requires_display
@pytest.mark.gui
def test_kurzer_knopf_wird_ersetzt(app):
    """Review #23: IK2J -> IK2JET am selben Platz, Markierung des kurzen bleibt."""
    from cwdecoder import gui
    g = app.gen
    _feed_word(app, g, "IK2J", spans=[("IK2J", 0, 4)])
    for c in ("IK2J", "OY1CT"):
        app.msgs.put(("call", g, c))
    app.msgs.put(("replace", g, ("IK2J", "IK2JET")))
    app._poll()
    app.update()
    assert app.calls == ["OY1CT", "IK2JET"]          # Platz von IK2J behalten
    assert "IK2J" not in app.call_rows and "IK2JET" in app.call_rows
    assert app.text.tag_ranges(gui.CALL_TAG_PREFIX + "IK2J")
    # ohne kurzen Knopf: neues Rufzeichen kommt wie gewohnt nach oben
    app.replace_call("XX1XX", "DL1ABC")
    assert app.calls[0] == "DL1ABC"


@requires_display
@pytest.mark.gui
def test_festhalten_regler_und_geraet(app, monkeypatch):
    """#25: Strg+R hält fest, innerhalb der Frist dasselbe Material, danach
    neu; Strg+S speichert das festgehaltene; Regler wirkt sofort; Gerät."""
    import sounddevice
    from cwdecoder import gui
    app.set_ring_settings(replay_hold_s=1)
    app.rec_var.set(False)
    app.auto_var.set(True)
    app._toggle()
    assert _pump(app, 5, lambda: "CQ" in app.text.get("1.0", "end"))
    app.toggle_replay()
    first = app.hold.clip
    assert first is not None and app.btn_replay["text"] == "Stopp"
    app.set_replay_rate(0.5)                        # mitten im Durchgang
    assert app.replay_rate_now == 0.5 and "0.50×" in app.status.get()
    assert app.rate_label["text"] == "0.50×"
    app.toggle_replay()                             # Stopp
    assert _pump(app, 5, lambda: app.replay_secs is None)
    assert app.btn_replay["text"] == gui._LBL_REPLAY_HELD
    # Strg+S speichert genau den festgehaltenen Ausschnitt
    app.save_last()
    assert _pump(app, 5, lambda: app.saved_paths)
    assert app.saved_paths[-1].endswith("_festgehalten.wav")
    assert os.path.exists(app.saved_paths[-1][:-4] + ".txt")
    # innerhalb der Frist: dasselbe Material, Regler bleibt
    app.toggle_replay()
    assert app.hold.clip is first and app.replay_rate_now == 0.5
    app.toggle_replay()
    assert _pump(app, 5, lambda: app.replay_secs is None)
    # nach der Frist verfällt er: Knopf wieder normal, Regler zurück, neues Material
    assert _pump(app, 3, lambda: app.btn_replay["text"] == gui._LBL_REPLAY)
    assert app.replay_rate_now == 1.0
    app.toggle_replay()
    assert app.hold.clip is not first
    app.toggle_replay()
    assert _pump(app, 5, lambda: app.replay_secs is None)
    # Ausgabegerät: fehlt es, spielt die Standard-Ausgabe und die Statuszeile sagt es
    app.hold.release()
    app.set_ring_settings(output_device="Gibt es nicht")
    app.toggle_replay()
    assert _pump(app, 5, lambda: app.replay_secs is None)
    assert "Standard" in app.status.get() or "Ausgabegerät" in app.status.get()
    assert sounddevice.played[-1].device is None
    app._toggle()


@requires_display
@pytest.mark.gui
def test_rufzeichen_entfernen(app):
    """#25: „×“, Rechtsklick „Entfernen“, „Alle löschen“; Markierung bleibt,
    wieder gehört -> wieder da."""
    from cwdecoder import gui
    g = app.gen
    _feed_word(app, g, "DL1ABC", spans=[("DL1ABC", 0, 6)])
    _feed_word(app, g, "OY1CT", spans=[("OY1CT", 6, 11)], start=6)
    for c in ("DL1ABC", "OY1CT", "IK2ULV"):
        app.msgs.put(("call", g, c))
    app._poll()
    app.update()
    rm = app.call_rows["DL1ABC"]["remove"]
    assert rm["text"] == "×" and rm._cw_tooltip.text == gui._TT_CALL_REMOVE
    rm.event_generate("<ButtonRelease-1>")
    assert "DL1ABC" not in app.calls and app.text.tag_ranges(gui.CALL_TAG_PREFIX + "DL1ABC")
    menu = app.call_menu_for("OY1CT")
    labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]
    assert labels[-1] == gui._LBL_CALL_REMOVE
    menu.invoke(menu.index("end"))
    assert app.calls == ["IK2ULV"]
    # wieder gehört (Spotter meldet nur die Spanne, kein on_call) -> wieder da
    _feed_word(app, g, "DL1ABC", spans=[("DL1ABC", 11, 17)], start=11)
    app._poll()
    assert app.calls[0] == "DL1ABC"
    assert app.btn_calls_clear._cw_tooltip.text == gui._TT_CALLS_CLEAR
    app.btn_calls_clear.invoke()
    assert app.calls == [] and app.call_rows == {}
    assert app.text.tag_ranges(gui.CALL_TAG)            # Text unverändert markiert
