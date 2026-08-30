from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess


UPDATE_BRANCH = "main"
UPDATE_REMOTE = "origin"


class UpdateError(RuntimeError):
    pass


def _run_git(root: Path, *arguments: str, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    if not git:
        raise UpdateError("Git is not available in PATH.")
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        [git, "-C", str(root), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        env=environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _git_value(root: Path, *arguments: str) -> str:
    result = _run_git(root, *arguments)
    if result.returncode:
        raise UpdateError("The Git installation could not be inspected.")
    return result.stdout.strip()


def _status(
    *,
    supported: bool,
    update_available: bool = False,
    message: str,
    current: str = "",
    latest: str = "",
) -> dict[str, object]:
    return {
        "supported": supported,
        "update_available": update_available,
        "message": message,
        "current_version": current[:8],
        "latest_version": latest[:8],
        "channel": UPDATE_BRANCH,
    }


def check_for_updates(root: Path) -> dict[str, object]:
    root = root.resolve()
    if not (root / ".git").exists():
        return _status(
            supported=False,
            message="Automatic updates require a Git-cloned installation. This copy was probably downloaded as a ZIP.",
        )
    if not shutil.which("git"):
        return _status(supported=False, message="Git is not available in PATH, so this installation cannot update automatically.")

    try:
        if _git_value(root, "rev-parse", "--is-inside-work-tree") != "true":
            return _status(supported=False, message="This folder is not a Git working tree.")
        current = _git_value(root, "rev-parse", "HEAD")
        branch = _git_value(root, "branch", "--show-current")
        if branch != UPDATE_BRANCH:
            return _status(
                supported=False,
                message=f"Safe updates require the {UPDATE_BRANCH} branch; this installation is on {branch or 'a detached commit'}.",
                current=current,
            )
        dirty = _git_value(root, "status", "--porcelain", "--untracked-files=no")
        if dirty:
            return _status(
                supported=False,
                message="Tracked application files have local changes. Update stopped to protect those changes.",
                current=current,
            )
        fetch = _run_git(root, "fetch", "--quiet", UPDATE_REMOTE, UPDATE_BRANCH)
        if fetch.returncode:
            return _status(
                supported=False,
                message="Could not contact the update source. Check the internet connection and Git credentials.",
                current=current,
            )
        latest = _git_value(root, "rev-parse", "FETCH_HEAD")
        if current == latest:
            return _status(
                supported=True,
                message="SeedVR Studio is up to date.",
                current=current,
                latest=latest,
            )
        ancestor = _run_git(root, "merge-base", "--is-ancestor", current, latest)
        if ancestor.returncode != 0:
            return _status(
                supported=False,
                message="The local main branch has diverged from the update source. Update stopped to protect this installation.",
                current=current,
                latest=latest,
            )
        return _status(
            supported=True,
            update_available=True,
            message="An update is available. Models, TensorRT engines, outputs, and saved settings will be preserved.",
            current=current,
            latest=latest,
        )
    except (OSError, subprocess.TimeoutExpired, UpdateError):
        return _status(
            supported=False,
            message="The update check could not complete. Check the internet connection and Git installation, or update manually.",
        )


def launch_updater(root: Path, server_process_id: int) -> None:
    updater = root.resolve() / "scripts" / "update.ps1"
    powershell = shutil.which("powershell.exe")
    if not updater.is_file():
        raise UpdateError("The updater script is missing.")
    if not powershell:
        raise UpdateError("Windows PowerShell is unavailable.")
    subprocess.Popen(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(updater),
            "-ServerProcessId",
            str(server_process_id),
        ],
        cwd=root,
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )
