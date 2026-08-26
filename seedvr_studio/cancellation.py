from __future__ import annotations

import os

import psutil

from .paths import SEEDVR_CLI


def cancel_current_render() -> str:
    """Terminate only SeedVR2 inference processes launched by this workspace."""
    cli_path = str(SEEDVR_CLI).lower()
    targets: dict[int, psutil.Process] = {}

    for process in psutil.process_iter(["pid", "cmdline"]):
        try:
            command = " ".join(process.info.get("cmdline") or []).lower()
            if process.pid != os.getpid() and cli_path in command:
                targets[process.pid] = process
                for child in process.children(recursive=True):
                    targets[child.pid] = child
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue

    if not targets:
        return "### Nothing to stop\nNo active SeedVR2 inference process was found."

    processes = list(targets.values())
    for process in reversed(processes):
        try:
            process.terminate()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

    _, alive = psutil.wait_procs(processes, timeout=3)
    for process in alive:
        try:
            process.kill()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

    return f"### Render stopped\nStopped {len(targets)} SeedVR2 process{'es' if len(targets) != 1 else ''}."
