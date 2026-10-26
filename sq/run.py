"""Run every .xosc in a folder headless with esmini and store one CSV log per scenario."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

DT = 0.05


def esmini_bin() -> str:
    b = os.environ.get("ESMINI_BIN", "esmini/bin/esmini")
    if not Path(b).exists():
        raise FileNotFoundError(f"esmini not found at {b}; run scripts/get_esmini.sh or set ESMINI_BIN")
    return b


def run_one(xosc: Path, log_dir: Path) -> dict:
    log_dir.mkdir(parents=True, exist_ok=True)
    csv = log_dir / f"{xosc.stem}.csv"
    cmd = [esmini_bin(), "--headless", "--osc", str(xosc), "--fixed_timestep", str(DT),
           "--csv_logger", str(csv), "--collision", "--disable_log"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    out = p.stdout + p.stderr
    return {
        "name": xosc.stem,
        "returncode": p.returncode,
        "log": str(csv) if csv.exists() else None,
        "errors": [l for l in out.splitlines() if "error" in l.lower()][:5],
    }


def run_set(scen_dir: Path, log_dir: Path) -> list[dict]:
    res = [run_one(x, log_dir) for x in sorted(scen_dir.glob("*.xosc"))]
    (log_dir / "runs.json").write_text(json.dumps(res, indent=1))
    return res
