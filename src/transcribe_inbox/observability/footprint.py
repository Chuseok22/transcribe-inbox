from __future__ import annotations
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

FOOTPRINT_BINARY = "/usr/bin/footprint"


def sample_process_footprint(
    pid: int,
    *,
    run_fn: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> int | None:
    """Best-effort (spec §9-5) — a failure here must never fail the job."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
            run_fn(
                [FOOTPRINT_BINARY, "--pid", str(pid), "-j", tmp.name],
                check=True, capture_output=True, timeout=10,
            )
            data = json.loads(Path(tmp.name).read_text())
        processes = data.get("processes") or []
        if not processes:
            return None
        return int(processes[0]["footprint"])
    except Exception:
        return None
