import os
import sys
import shutil
import subprocess
import tempfile
import zipfile
from typing import Optional

import requests
from PySide6.QtCore import QThread, Signal

from ..version import APP_VERSION, GITHUB_OWNER, GITHUB_REPO

API_BASE = "https://api.github.com"


def _parse_version(v: str) -> tuple:
    v = (v or "").strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        num = ""
        for ch in p:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


class UpdateCheckWorker(QThread):
    """Checks the GitHub Releases API for a newer tagged release than the running
    build. The repo is private, so a token (fine-grained PAT, read-only 'Contents'
    scope on this one repo) is required — pass "" to skip silently if the user
    hasn't configured one yet. Never surfaces errors as popups on its own; the
    caller decides whether a failed background check is worth mentioning."""
    found = Signal(dict)
    none_found = Signal()
    failed = Signal(str)

    def __init__(self, token: str = ""):
        super().__init__()
        self.token = token

    def run(self):
        try:
            headers = {"Accept": "application/vnd.github+json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            res = requests.get(
                f"{API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest",
                headers=headers, timeout=15
            )
            if res.status_code == 404:
                self.failed.emit("No releases found, or the update token can't see this private repo.")
                return
            if res.status_code == 401:
                self.failed.emit("Update token is invalid or expired.")
                return
            res.raise_for_status()
            data = res.json()

            tag = data.get("tag_name", "")
            if not tag or not is_newer(tag, APP_VERSION):
                self.none_found.emit()
                return

            assets = data.get("assets", [])
            zip_asset = next((a for a in assets if a.get("name", "").lower().endswith(".zip")), None)
            if not zip_asset:
                self.failed.emit(f"Release {tag} has no .zip build attached.")
                return

            self.found.emit({
                "tag": tag,
                "title": data.get("name") or tag,
                "notes": data.get("body") or "",
                "asset_id": zip_asset["id"],
                "asset_name": zip_asset["name"],
                "asset_size": zip_asset.get("size", 0),
            })
        except Exception as e:
            self.failed.emit(str(e))


class UpdateDownloadWorker(QThread):
    """Downloads + extracts the release zip asset to a staging folder in %TEMP%.
    Private-repo release assets must be fetched through the API asset endpoint
    (Accept: application/octet-stream) rather than browser_download_url, which
    needs a browser session for private repos."""
    progress = Signal(int, str)
    finished = Signal(str)  # path to the extracted build's root folder
    failed = Signal(str)

    def __init__(self, asset_id: int, asset_size: int, token: str = ""):
        super().__init__()
        self.asset_id = asset_id
        self.asset_size = asset_size
        self.token = token

    def run(self):
        try:
            headers = {"Accept": "application/octet-stream"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            url = f"{API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/assets/{self.asset_id}"

            staging_root = os.path.join(tempfile.gettempdir(), "DubifyAI_Update")
            shutil.rmtree(staging_root, ignore_errors=True)
            os.makedirs(staging_root, exist_ok=True)
            zip_path = os.path.join(staging_root, "update.zip")

            self.progress.emit(0, "Connecting to GitHub...")
            with requests.get(url, headers=headers, stream=True, timeout=60) as res:
                res.raise_for_status()
                total = int(res.headers.get("Content-Length") or self.asset_size or 0)
                downloaded = 0
                with open(zip_path, "wb") as f:
                    for chunk in res.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = min(90, int(downloaded / total * 90))
                            mb = downloaded // (1024 * 1024)
                            total_mb = total // (1024 * 1024)
                            self.progress.emit(pct, f"Downloading update... {mb}MB / {total_mb}MB")

            self.progress.emit(92, "Extracting update...")
            extract_dir = os.path.join(staging_root, "extracted")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            os.remove(zip_path)

            # Release zip may wrap the build in one top-level folder (e.g. from
            # "Compress-Archive" on the dist dir) — unwrap it so payload_dir always
            # points at the folder that actually contains DubifyAI.exe.
            payload_dir = extract_dir
            entries = os.listdir(extract_dir)
            if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
                payload_dir = os.path.join(extract_dir, entries[0])

            self.progress.emit(100, "Update ready.")
            self.finished.emit(payload_dir)
        except Exception as e:
            self.failed.emit(str(e))


def apply_update_and_restart(payload_dir: str):
    """Stages a batch script that waits for this process to exit, copies the new
    build over the install directory (WITHOUT deleting extra files — user data
    like project.db/temp/cache lives next to the exe and must survive an update),
    relaunches the app, then deletes itself. Call this right before quitting."""
    is_frozen = getattr(sys, "frozen", False)
    exe_path = sys.executable if is_frozen else os.path.abspath(sys.argv[0])
    install_dir = os.path.dirname(exe_path)
    exe_name = os.path.basename(exe_path)
    pid = os.getpid()

    staging_root = os.path.join(tempfile.gettempdir(), "DubifyAI_Update")
    os.makedirs(staging_root, exist_ok=True)
    bat_path = os.path.join(staging_root, "apply_update.bat")

    launch_cmd = f'start "" "{exe_path}"' if is_frozen else f'start "" "{sys.executable}" "{exe_path}"'

    bat_contents = f"""@echo off
:wait
tasklist /fi "PID eq {pid}" | find "{pid}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait
)
robocopy "{payload_dir}" "{install_dir}" /E /R:3 /W:1 /NFL /NDL /NJH /NJS /XF project.db *.sqlite *.sqlite3
{launch_cmd}
del "%~f0"
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_contents)

    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        close_fds=True,
        cwd=install_dir,
    )
