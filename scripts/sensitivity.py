#!/usr/bin/env python
"""Do the conclusions survive different thresholds?

Re-assesses the logged grid (no new simulation) with one assumption changed at a time
and reports the funnel for each variant.

    python scripts/sensitivity.py --out outputs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sq import assess, generate, metrics  # noqa: E402

VARIANTS = [
    ("baseline", {}, 0.5),
    ("reaction time 0.3 s", {}, 0.3),
    ("reaction time 1.0 s", {}, 1.0),
    ("lateral limit 3 m/s²", {"MAX_LAT_ACC": 3.0}, 0.5),
    ("lateral limit 7 m/s²", {"MAX_LAT_ACC": 7.0}, 0.5),
    ("relevant if headway < 0.5 s or braking > 0.25 m/s²", {"RELEVANT_THW": 0.5, "RELEVANT_A_REQ": 0.25}, 0.5),
    ("relevant if headway < 2.0 s or braking > 1.0 m/s²", {"RELEVANT_THW": 2.0, "RELEVANT_A_REQ": 1.0}, 0.5),
    ("max ego braking 6 m/s²", {"EGO_MAX_DECEL": 6.0}, 0.5),
    ("max ego braking 10 m/s²", {"EGO_MAX_DECEL": 10.0}, 0.5),
]


def funnel(rows: list[dict]) -> dict:
    df = pd.DataFrame(rows)
    valid = df[df.verdict != "invalid"]
    useful = df[df.verdict == "useful"]
    passable = useful[useful.criticality != "unavoidable"]
    return {"valid": len(valid), "relevant": len(useful), "passable": len(passable),
            "distinct": passable.groupby(["dv_kmh", "gap_m", "t_lc_s"]).ngroups,
            "distinct_with_ego_speed": passable.groupby(["v_ego_kmh", "dv_kmh", "gap_m", "t_lc_s"]).ngroups}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    args = ap.parse_args()
    runs = {r["name"]: r for r in json.loads((args.out / "grid" / "logs" / "runs.json").read_text())}
    defaults = {k: getattr(assess, k) for k in ("MAX_LAT_ACC", "RELEVANT_THW", "RELEVANT_A_REQ", "EGO_MAX_DECEL")}
    cache: dict[float, dict] = {}
    table = []
    for label, overrides, rt in VARIANTS:
        if rt not in cache:
            cache[rt] = {n: (metrics.compute(r["log"], reaction_time=rt) if r["log"] else None) for n, r in runs.items()}
        for k, v in {**defaults, **overrides}.items():
            setattr(assess, k, v)
        rows = []
        for c in generate.grid():
            v = assess.verdict(runs[c.name], cache[rt][c.name])
            rows.append({"v_ego_kmh": c.v_ego_kmh, "dv_kmh": c.dv_kmh, "gap_m": c.gap_m, "t_lc_s": c.t_lc_s, **v})
        table.append({"variant": label, **funnel(rows)})
    for k, v in defaults.items():
        setattr(assess, k, v)
    df = pd.DataFrame(table)
    df.to_csv(args.out / "sensitivity.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
