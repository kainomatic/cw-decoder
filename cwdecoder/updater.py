# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Update-Prüfung und -Installation (ADR-0013). Ohne tk, direkt testbar.

check_for_update(version, channel) -> UpdateCheckResult
    Fragt die GitHub-Releases-API (HTTPS, Timeout 8 s) ab und sucht das
    neueste Release des Kanals. Wirft nie: Netz- und API-Fehler ergeben
    status ERROR mit Klartext in error_message.
download_update(asset, on_progress) -> Path
    Lädt den Installer nach %TEMP%. Nur von github.com bzw.
    objects.githubusercontent.com, Größe muss zu assets[].size passen,
    SHA256 wird nur geloggt (GitHub liefert keinen Referenz-Hash).
    Wirft UpdateError.
launch_installer_and_exit(path, exit_fn)
    Startet "<installer> /SILENT /RESTARTCWDECODER" und ruft exit_fn().

Kanäle: stable = prerelease false und Tag vX.Y.Z,
        beta   = prerelease true  und Tag vX.Y.Z-betaN.
Reihenfolge: vX.Y.Z-betaN < vX.Y.Z bei gleicher Basis, betaN numerisch
(beta10 > beta2).
"""
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .__version__ import REPO_URL

log = logging.getLogger(__name__)

API_URL = "https://api.github.com/repos/kainomatic/cw-decoder/releases"
API_TIMEOUT_S = 8
DOWNLOAD_TIMEOUT_S = 60
CHUNK_BYTES = 64 * 1024
USER_AGENT = "CWDecoder-Updater/1"
ALLOWED_DOWNLOAD_PREFIXES = (
    "https://github.com/",
    "https://objects.githubusercontent.com/",
)
RESTART_FLAG = "/RESTARTCWDECODER"

# Beta-Assets tragen die Ziel-Stable-Nummer, nicht das -betaN-Suffix.
# Das Stable-Muster passt nicht auf Beta-Assets ("CWDecoder-Beta-Setup-...").
ASSET_PATTERNS = {
    "stable": re.compile(r"^CWDecoder-Setup-v\d+\.\d+\.\d+\.exe$"),
    "beta": re.compile(r"^CWDecoder-Beta-Setup-v\d+\.\d+\.\d+\.exe$"),
}

_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-beta(\d+))?$")

# -- Meldungen (Vorbereitung i18n) ------------------------------------------
_MSG_NETWORK = "Keine Verbindung zu GitHub ({err})."
_MSG_RATE_LIMIT = "GitHub begrenzt gerade die Anfragen. Bitte später erneut versuchen."
_MSG_HTTP = "GitHub antwortet mit Fehler {status}."
_MSG_PARSE = "Die Antwort von GitHub ließ sich nicht auswerten."
_MSG_NO_ASSET = "Im Release {tag} fehlt die passende Setup-Datei."
_MSG_BAD_URL = "Die Setup-Datei liegt nicht auf GitHub ({url}); Download abgelehnt."
_MSG_SIZE = ("Die Setup-Datei ist unvollständig ({actual} statt {expected} Bytes) "
             "und wird nicht ausgeführt.")
_MSG_DOWNLOAD = "Download fehlgeschlagen ({err})."


class UpdateError(Exception):
    """Erwartbarer Fehler bei Update-Prüfung oder Download (Klartext)."""


class UpdateStatus(Enum):
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    ERROR = "error"


@dataclass(frozen=True)
class AssetInfo:
    name: str
    url: str
    size: int


@dataclass(frozen=True)
class UpdateCheckResult:
    status: UpdateStatus
    new_version: str = None     # ohne "v", z. B. "0.2.0" oder "0.2.0-beta3"
    asset: AssetInfo = None
    release_url: str = None     # Release-Seite (Release-Notes)
    error_message: str = None


# -- Versionen ---------------------------------------------------------------
def parse_version(text):
    """"v0.2.0" / "0.2.0-beta3" -> (0, 2, 0, beta) mit beta None für Stable.

    None bei unbekanntem Format (z. B. "-rc1")."""
    m = _TAG_RE.match(text.strip()) if isinstance(text, str) else None
    if not m:
        return None
    major, minor, patch, beta = m.groups()
    return int(major), int(minor), int(patch), (int(beta) if beta is not None else None)


def version_key(text):
    """Sortierschlüssel: Basis, dann Stable über jeder Beta, Betas numerisch."""
    v = parse_version(text)
    if v is None:
        return None
    major, minor, patch, beta = v
    return (major, minor, patch, 1 if beta is None else 0, beta or 0)


def is_newer(candidate, current) -> bool:
    """True, wenn candidate eine neuere Version als current ist."""
    a, b = version_key(candidate), version_key(current)
    return a is not None and b is not None and a > b


def _channel_of(release):
    """"stable", "beta" oder None (Tag und prerelease-Flag passen nicht)."""
    v = parse_version(release.get("tag_name") or "")
    if v is None or not (release.get("tag_name") or "").startswith("v"):
        return None
    is_beta_tag = v[3] is not None
    pre = bool(release.get("prerelease"))
    if pre and is_beta_tag:
        return "beta"
    if not pre and not is_beta_tag:
        return "stable"
    return None


def find_latest_release(releases, channel):
    """Neuestes veröffentlichtes Release des Kanals oder None."""
    best, best_key = None, None
    for r in releases:
        if not isinstance(r, dict) or r.get("draft") or _channel_of(r) != channel:
            continue
        key = version_key(r["tag_name"])
        if best_key is None or key > best_key:
            best, best_key = r, key
    return best


def pick_asset(release, channel):
    """Passendes Setup-Asset des Kanals oder None."""
    pattern = ASSET_PATTERNS[channel]
    for a in release.get("assets") or []:
        name = a.get("name") or ""
        if pattern.match(name):
            return AssetInfo(name=name, url=a.get("browser_download_url") or "",
                             size=int(a.get("size") or 0))
    return None


def is_allowed_url(url) -> bool:
    return isinstance(url, str) and url.startswith(ALLOWED_DOWNLOAD_PREFIXES)


# -- Netz ----------------------------------------------------------------------
class _HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    """Weiterleitungen nur auf HTTPS-Ziele (GitHub leitet Downloads auf
    sein CDN um)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            raise urllib.error.URLError(f"Weiterleitung auf {newurl} abgelehnt")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener():
    return urllib.request.build_opener(_HttpsOnlyRedirect)


def fetch_releases(timeout=API_TIMEOUT_S):
    """Release-Liste von GitHub. Wirft UpdateError."""
    req = urllib.request.Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    })
    try:
        with _opener().open(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise UpdateError(_MSG_RATE_LIMIT) from e
        raise UpdateError(_MSG_HTTP.format(status=e.code)) from e
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", None) or e
        raise UpdateError(_MSG_NETWORK.format(err=reason)) from e
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise UpdateError(_MSG_PARSE) from e
    if not isinstance(data, list):
        raise UpdateError(_MSG_PARSE)
    return data


def check_for_update(current_version, channel, fetch=fetch_releases) -> UpdateCheckResult:
    """Gibt es im Kanal eine neuere Version? Wirft nicht."""
    log.info("Update-Prüfung: Version %s, Kanal %s", current_version, channel)
    try:
        releases = fetch()
        best = find_latest_release(releases, channel)
        if best is None or not is_newer(best["tag_name"], current_version):
            log.info("Update-Prüfung: aktuell")
            return UpdateCheckResult(UpdateStatus.UP_TO_DATE)
        tag = best["tag_name"]
        asset = pick_asset(best, channel)
        if asset is None:
            raise UpdateError(_MSG_NO_ASSET.format(tag=tag))
    except UpdateError as e:
        log.warning("Update-Prüfung fehlgeschlagen: %s", e)
        return UpdateCheckResult(UpdateStatus.ERROR, error_message=str(e))
    except Exception as e:  # noqa: BLE001 - Update-Prüfung darf nie abstürzen
        log.warning("Update-Prüfung fehlgeschlagen: %r", e)
        return UpdateCheckResult(UpdateStatus.ERROR, error_message=_MSG_PARSE)
    release_url = best.get("html_url") or f"{REPO_URL}/releases/tag/{tag}"
    log.info("Update verfügbar: %s (%s, %d Bytes)", tag, asset.name, asset.size)
    return UpdateCheckResult(UpdateStatus.UPDATE_AVAILABLE, new_version=tag[1:],
                             asset=asset, release_url=release_url)


def download_update(asset, on_progress=None, dest_dir=None,
                    timeout=DOWNLOAD_TIMEOUT_S, opener=None) -> Path:
    """Installer herunterladen und prüfen; liefert den Pfad. Wirft UpdateError.

    on_progress(done_bytes, total_bytes) wird im aufrufenden Thread gerufen."""
    if not is_allowed_url(asset.url):
        raise UpdateError(_MSG_BAD_URL.format(url=asset.url))
    dest_dir = Path(dest_dir) if dest_dir is not None else Path(tempfile.gettempdir())
    fd, tmp = tempfile.mkstemp(prefix="CWDecoder-Update-", suffix=".exe", dir=dest_dir)
    path = Path(tmp)
    sha = hashlib.sha256()
    done = 0
    req = urllib.request.Request(asset.url, headers={"User-Agent": USER_AGENT})
    log.info("Update-Download: %s", asset.url)
    try:
        with os.fdopen(fd, "wb") as f, (opener or _opener()).open(req, timeout=timeout) as resp:
            while True:
                chunk = resp.read(CHUNK_BYTES)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if on_progress is not None:
                    on_progress(done, asset.size)
    except (urllib.error.URLError, OSError) as e:
        path.unlink(missing_ok=True)
        reason = getattr(e, "reason", None) or e
        log.warning("Update-Download fehlgeschlagen: %s", reason)
        raise UpdateError(_MSG_DOWNLOAD.format(err=reason)) from e
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    actual = path.stat().st_size
    if actual != asset.size:
        path.unlink(missing_ok=True)
        log.warning("Update-Download: Größe %d statt %d Bytes", actual, asset.size)
        raise UpdateError(_MSG_SIZE.format(actual=actual, expected=asset.size))
    log.info("Update heruntergeladen: %s, %d Bytes, SHA256 %s", path, actual, sha.hexdigest())
    return path


def installer_command(installer_path):
    return [str(installer_path), "/SILENT", RESTART_FLAG]


def launch_installer_and_exit(installer_path, exit_fn, popen=subprocess.Popen) -> None:
    """Installer starten, danach exit_fn() (beendet die App).

    Erst starten, dann beenden: Der Installer wartet über AppMutex und
    CloseApplications, bis die laufende EXE frei ist."""
    cmd = installer_command(installer_path)
    log.info("Starte Installer: %s", " ".join(cmd))
    popen(cmd, close_fds=True)
    exit_fn()
