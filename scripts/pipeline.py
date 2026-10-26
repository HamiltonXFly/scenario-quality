#!/usr/bin/env python
"""Generate -> simulate -> assess, for the clean grid and the seeded-defect set.

    python scripts/pipeline.py --out outputs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sq import assess, generate, metrics, run  # noqa: E402


# the check that is supposed to catch each defect
INTENDED = {"spawn_overlap": "inconsistent_start", "off_road": "off_road", "teleport": "implausible_motion",
            "snap_lane_change": "implausible_motion", "unit_error": "implausible_motion",
            "dead_trigger": "manoeuvre_missing"}

SWEEP = {
    "spawn_overlap": [0.1, 0.5, 1.0, 2.0, 3.6],        # m of overlap
    "off_road": [0.02, 0.1, 0.3, 1.0, 7.0],            # m beyond the road edge
    "teleport": [0.1, 0.2, 0.3, 0.5, 1.0, 30.0],       # m jump
    "snap_lane_change": [0.3, 1.0, 1.5, 1.7, 1.9],     # s for the lane change
    "unit_error": [1.2, 1.5, 2.0, 3.6],                # speed factor
}


def evaluate(cases, out: Path) -> pd.DataFrame:
    scen, logs = out / "scenarios", out / "logs"
    generate.write_set(cases, scen)
    runs = {r["name"]: r for r in run.run_set(scen, logs)}
    rows = []
    for c in cases:
        r = runs[c.name]
        try:
            m = metrics.compute(r["log"]) if r["log"] else None
        except Exception as ex:  # unreadable log counts as not executable
            m, r = None, {**r, "returncode": 1, "errors": [str(ex)]}
        v = assess.verdict(r, m)
        rows.append({"name": c.name, "v_ego_kmh": c.v_ego_kmh, "dv_kmh": c.dv_kmh, "gap_m": c.gap_m,
                     "t_lc_s": c.t_lc_s, "defect": c.defect, **(m or {}), **v,
                     "issues": ";".join(v["issues"])})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    args = ap.parse_args()

    clean = generate.grid()
    df = evaluate(clean, args.out / "grid")
    df.to_csv(args.out / "grid_results.csv", index=False)
    print(df["verdict"].value_counts().to_string())

    # Sanity check: scenarios we expected to be fine when designing the grid
    by_design = df[(df.t_lc_s >= 2) & ((df.dv_kmh < 0) | (df.gap_m >= generate.TARGET_DX0))]

    # Mutation test of the checker: inject each defect into every scenario it accepted
    accepted = [c for c in clean if df.set_index("name").loc[c.name, "verdict"] != "invalid"]
    mutated = [generate.CutIn(**{**c.__dict__, "defect": d}) for d in generate.DEFECTS for c in accepted]
    dm = evaluate(mutated, args.out / "defects")
    dm.to_csv(args.out / "defect_results.csv", index=False)
    summary = {
        "grid_size": len(df),
        "verdicts": df["verdict"].value_counts().to_dict(),
        "criticality": df["criticality"].value_counts().to_dict(),
        "by_design_valid": len(by_design),
        "by_design_valid_but_flagged": by_design.loc[by_design.verdict == "invalid", "name"].tolist(),
        "mutation_base": len(accepted),
        "detected": dm.groupby("defect")["verdict"].apply(lambda s: int((s == "invalid").sum())).to_dict(),
        "missed": dm.loc[dm.verdict != "invalid", "name"].tolist(),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1))

    # Severity sweep: how small can each bug be and still be caught?
    sweep = [generate.CutIn(**{**c.__dict__, "defect": d, "level": lv})
             for d, levels in SWEEP.items() for lv in levels for c in accepted]
    ds = evaluate(sweep, args.out / "defect_sweep")
    ds["level"] = [c.lvl for c in sweep]
    ds["caught"] = ds.verdict == "invalid"
    ds["caught_by_intended_check"] = [INTENDED[d] in str(i).split(";") for d, i in zip(ds.defect, ds.issues)]
    tab = (ds.groupby(["defect", "level"])
             .agg(n=("caught", "size"), caught=("caught", "sum"),
                  caught_by_intended_check=("caught_by_intended_check", "sum")).reset_index())
    tab.to_csv(args.out / "defect_sweep.csv", index=False)
    print(tab.to_string(index=False))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
