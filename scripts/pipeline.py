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
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
