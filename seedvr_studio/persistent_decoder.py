"""Persistent TensorRT decoder process integration for the JS Studio."""

from __future__ import annotations

import re
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Callable

from .media import MediaError
from .paths import ROOT, VENV_PYTHON


RUNNER = ROOT / "tools" / "run_tensorrt_persistent.py"
ProgressCallback = Callable[[float, str], None]


def _safe_print(value: str) -> None:
    try:
        print(value, flush=True)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(value.encode(encoding, errors="replace").decode(encoding, errors="replace"), flush=True)


def run_persistent_decoder(
    manifest_path: Path,
    total: int,
    child_env: dict[str, str],
    progress_callback: ProgressCallback | None,
) -> None:
    """Run one decoder process and stream its per-batch progress."""
    command = [str(VENV_PYTHON), "-u", str(RUNNER), str(manifest_path)]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=child_env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output_tail: deque[str] = deque(maxlen=80)
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip()
        output_tail.append(line)
        _safe_print(line)
        match = re.search(r"PERSISTENT_PROGRESS (\d+)/(\d+)", line)
        if match and progress_callback:
            current = int(match.group(1))
            progress_callback(
                0.78 + 0.12 * current / max(1, total),
                f"Optimized TensorRT VAE decoding batch {current} of {total}",
            )
    return_code = process.wait()
    if return_code:
        raise MediaError(f"Optimized TensorRT VAE decode failed:\n{'\n'.join(output_tail)}")
