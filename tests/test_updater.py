# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Update-Prüfung (ADR-0013). Kein Netz: API und Downloads sind gemockt."""
import io
import json
import urllib.error

import pytest

from cwdecoder import updater
from cwdecoder.updater import (AssetInfo, UpdateError, UpdateStatus, check_for_update,
                               download_update, find_latest_release, installer_command,
                               is_allowed_url, is_newer, launch_installer_and_exit,
                               parse_version, pick_asset)


def rel(tag, prerelease=None, assets=None, draft=False):
    if prerelease is None:
        prerelease = "-beta" in tag
    base = tag[1:].split("-")[0]
    if assets is None:
        name = f"CWDecoder-{'Beta-' if prerelease else ''}Setup-v{base}.exe"
        assets = [{"name": name, "size": 1234,
                   "browser_download_url": f"https://github.com/kainomatic/cw-decoder/"
                                           f"releases/download/{tag}/{name}"}]
    return {"tag_name": tag, "prerelease": prerelease, "draft": draft, "assets": assets,
            "html_url": f"https://github.com/kainomatic/cw-decoder/releases/tag/{tag}"}


# -- Versionen -----------------------------------------------------------------
@pytest.mark.parametrize("text, want", [
    ("v0.1.0", (0, 1, 0, None)),
    ("0.1.0", (0, 1, 0, None)),
    ("v1.10.3", (1, 10, 3, None)),
    ("v0.2.0-beta1", (0, 2, 0, 1)),
    ("0.2.0-beta12", (0, 2, 0, 12)),
    ("v0.1", None),
    ("v0.1.0-rc1", None),
    ("vX.Y.Z", None),
    ("", None),
    (None, None),
])
def test_parse_version(text, want):
    assert parse_version(text) == want


@pytest.mark.parametrize("cand, cur, newer", [
    ("v0.2.0", "0.1.0", True),
    ("v0.1.1", "0.1.0", True),
    ("v1.0.0", "0.9.9", True),
    ("v0.10.0", "0.9.0", True),        # numerisch, nicht lexikografisch
    ("v0.1.0", "0.1.0", False),
    ("v0.0.9", "0.1.0", False),
    ("v0.2.0-beta1", "0.1.0", True),   # höhere Basis
    ("v0.1.0-beta1", "0.1.0", False),  # Beta < Stable gleicher Basis
    ("v0.1.0", "0.1.0-beta1", True),
    ("v0.1.0-beta2", "0.1.0-beta1", True),
    ("v0.1.0-beta1", "0.1.0-beta2", False),
    ("v0.1.0-beta10", "0.1.0-beta2", True),  # beta10 > beta2
    ("v0.1.0-beta2", "0.1.0-beta10", False),
    ("v0.1.0-beta3", "0.1.0-beta3", False),
    ("murks", "0.1.0", False),
    ("v0.2.0", "kaputt", False),
])
def test_is_newer(cand, cur, newer):
    assert is_newer(cand, cur) is newer


# -- Kanalfilter -----------------------------------------------------------------
RELEASES = [
    rel("v0.1.0"),
    rel("v0.2.0-beta2"),
    rel("v0.2.0-beta10"),
    rel("v0.1.1"),
    rel("v0.3.0", prerelease=True),          # Stable-Tag als Pre-Release: ignorieren
    rel("v0.4.0-beta1", prerelease=False),   # Beta-Tag als Release: ignorieren
    rel("v0.9.0-beta1", draft=True),         # Entwurf: ignorieren
    rel("nightly", prerelease=True),
]


def test_find_latest_stable():
    assert find_latest_release(RELEASES, "stable")["tag_name"] == "v0.1.1"


def test_find_latest_beta_numeric():
    assert find_latest_release(RELEASES, "beta")["tag_name"] == "v0.2.0-beta10"


def test_find_latest_none():
    assert find_latest_release([], "stable") is None
    assert find_latest_release([rel("v0.1.0-beta1")], "stable") is None


# -- Asset-Wahl ----------------------------------------------------------------
def _assets(*names):
    return [{"name": n, "size": 10, "browser_download_url": f"https://github.com/x/{n}"}
            for n in names]


def test_pick_asset_stable_excludes_beta():
    r = rel("v0.2.0", assets=_assets("CWDecoder-Beta-Setup-v0.2.0.exe",
                                     "CWDecoder-Setup-v0.2.0.exe"))
    assert pick_asset(r, "stable").name == "CWDecoder-Setup-v0.2.0.exe"


def test_pick_asset_beta():
    r = rel("v0.2.0-beta1", assets=_assets("CWDecoder-Setup-v0.2.0.exe",
                                           "CWDecoder-Beta-Setup-v0.2.0.exe"))
    a = pick_asset(r, "beta")
    assert a.name == "CWDecoder-Beta-Setup-v0.2.0.exe" and a.size == 10


@pytest.mark.parametrize("name", [
    "CWDecoder-Beta-Setup-v0.2.0.exe", "CWDecoder-Setup-v0.2.0-beta1.exe",
    "CWDecoder-Setup.exe", "CWDecoder-Setup-v0.2.0.exe.sig", "Source code.zip",
])
def test_pick_asset_stable_rejects(name):
    assert pick_asset(rel("v0.2.0", assets=_assets(name)), "stable") is None


# -- URL-Prüfung ---------------------------------------------------------------
@pytest.mark.parametrize("url, ok", [
    ("https://github.com/kainomatic/cw-decoder/releases/download/v0.1.0/x.exe", True),
    ("https://objects.githubusercontent.com/github-production-release-asset/x", True),
    ("http://github.com/kainomatic/cw-decoder/x.exe", False),
    ("https://github.com.evil.example/x.exe", False),
    ("https://evil.example/https://github.com/x.exe", False),
    ("", False),
    (None, False),
])
def test_is_allowed_url(url, ok):
    assert is_allowed_url(url) is ok


# -- check_for_update --------------------------------------------------------------
def test_check_update_available_stable():
    r = check_for_update("0.1.0", "stable", fetch=lambda: RELEASES)
    assert r.status is UpdateStatus.UPDATE_AVAILABLE
    assert r.new_version == "0.1.1"
    assert r.asset.name == "CWDecoder-Setup-v0.1.1.exe"
    assert r.release_url.endswith("/releases/tag/v0.1.1")


def test_check_update_available_beta():
    r = check_for_update("0.2.0-beta2", "beta", fetch=lambda: RELEASES)
    assert r.status is UpdateStatus.UPDATE_AVAILABLE
    assert r.new_version == "0.2.0-beta10"
    assert r.asset.name == "CWDecoder-Beta-Setup-v0.2.0.exe"


def test_check_up_to_date():
    assert check_for_update("0.1.1", "stable", fetch=lambda: RELEASES).status \
        is UpdateStatus.UP_TO_DATE
    assert check_for_update("0.2.0-beta10", "beta", fetch=lambda: RELEASES).status \
        is UpdateStatus.UP_TO_DATE
    assert check_for_update("0.1.0", "stable", fetch=lambda: []).status \
        is UpdateStatus.UP_TO_DATE


def test_check_missing_asset_is_error():
    r = check_for_update("0.1.0", "stable", fetch=lambda: [rel("v0.2.0", assets=[])])
    assert r.status is UpdateStatus.ERROR and "v0.2.0" in r.error_message


def test_check_garbage_is_error():
    r = check_for_update("0.1.0", "stable", fetch=lambda: [{"tag_name": 5}])
    assert r.status in (UpdateStatus.ERROR, UpdateStatus.UP_TO_DATE)
    r = check_for_update("0.1.0", "stable", fetch=lambda: None)
    assert r.status is UpdateStatus.ERROR


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class _Opener:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def open(self, req, timeout=None):
        self.requests.append((req, timeout))
        if isinstance(self.result, BaseException):
            raise self.result
        return _Resp(self.result)


@pytest.mark.parametrize("exc, part", [
    (urllib.error.URLError("getaddrinfo failed"), "Keine Verbindung"),
    (TimeoutError("timed out"), "Keine Verbindung"),
    (urllib.error.HTTPError(updater.API_URL, 403, "Forbidden", {}, None), "begrenzt"),
    (urllib.error.HTTPError(updater.API_URL, 500, "Server Error", {}, None), "500"),
])
def test_network_errors_give_error_status(monkeypatch, exc, part):
    monkeypatch.setattr(updater, "_opener", lambda: _Opener(exc))
    r = check_for_update("0.1.0", "stable")
    assert r.status is UpdateStatus.ERROR
    assert part in r.error_message


def test_fetch_releases_request(monkeypatch):
    op = _Opener(json.dumps([rel("v0.2.0")]).encode())
    monkeypatch.setattr(updater, "_opener", lambda: op)
    r = check_for_update("0.1.0", "stable")
    assert r.status is UpdateStatus.UPDATE_AVAILABLE
    req, timeout = op.requests[0]
    assert req.full_url == "https://api.github.com/repos/kainomatic/cw-decoder/releases"
    assert timeout == 8
    assert req.get_header("User-agent").startswith("CWDecoder")


def test_fetch_releases_bad_json(monkeypatch):
    monkeypatch.setattr(updater, "_opener", lambda: _Opener(b"<html>"))
    assert check_for_update("0.1.0", "stable").status is UpdateStatus.ERROR


# -- Download ------------------------------------------------------------------
GOOD_URL = "https://github.com/kainomatic/cw-decoder/releases/download/v0.2.0/x.exe"


def test_download_ok(tmp_path):
    data = b"MZ" + b"x" * 200_000
    progress = []
    p = download_update(AssetInfo("x.exe", GOOD_URL, len(data)),
                        on_progress=lambda d, t: progress.append((d, t)),
                        dest_dir=tmp_path, opener=_Opener(data))
    assert p.read_bytes() == data and p.parent == tmp_path and p.suffix == ".exe"
    assert progress[-1] == (len(data), len(data)) and len(progress) > 1


def test_download_size_mismatch_deletes_file(tmp_path):
    with pytest.raises(UpdateError, match="unvollständig"):
        download_update(AssetInfo("x.exe", GOOD_URL, 999), dest_dir=tmp_path,
                        opener=_Opener(b"zu kurz"))
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_foreign_url(tmp_path):
    op = _Opener(b"x")
    with pytest.raises(UpdateError, match="nicht auf GitHub"):
        download_update(AssetInfo("x.exe", "https://evil.example/x.exe", 1),
                        dest_dir=tmp_path, opener=op)
    assert op.requests == [] and list(tmp_path.iterdir()) == []


def test_download_network_error(tmp_path):
    with pytest.raises(UpdateError, match="Download fehlgeschlagen"):
        download_update(AssetInfo("x.exe", GOOD_URL, 1), dest_dir=tmp_path,
                        opener=_Opener(urllib.error.URLError("reset")))
    assert list(tmp_path.iterdir()) == []


def test_redirect_to_http_rejected():
    h = updater._HttpsOnlyRedirect()
    with pytest.raises(urllib.error.URLError):
        h.redirect_request(None, None, 302, "Found", {}, "http://example.com/x.exe")


# -- Installer-Start -----------------------------------------------------------
def test_launch_installer_and_exit(tmp_path):
    calls = []
    exe = tmp_path / "setup.exe"
    launch_installer_and_exit(exe, lambda: calls.append("exit"),
                              popen=lambda cmd, **kw: calls.append(cmd))
    assert calls == [[str(exe), "/SILENT", "/RESTARTCWDECODER"], "exit"]
    assert installer_command(exe)[1:] == ["/SILENT", "/RESTARTCWDECODER"]
