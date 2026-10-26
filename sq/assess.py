"""Turn per-scenario metrics into quality verdicts.

Three questions, asked in order:

1. Validity   - is this a legitimate test at all? (executes, consistent start, physically
                plausible, intended manoeuvre actually happens)
2. Relevance  - does the system under test have to react?
3. Criticality - how hard is the test? (deceleration the ego would need at the cut-in)

Thresholds are explicit constants so they can be reviewed and changed in one place.
"""

from __future__ import annotations

import math

MAX_SPEED = 200 / 3.6        # m/s, implausible on a public highway above this
MAX_LONG_ACC = 10.0          # m/s^2, beyond tyre limits of a passenger car
MAX_LAT_ACC = 5.0            # m/s^2, far beyond normal lane-change behaviour (~1-3 m/s^2)
MAX_JUMP = 5.0               # m/s, mismatch between position change and reported speed

RELEVANT_THW = 1.0           # s, ego must handle a short headway right after the cut-in ...
RELEVANT_A_REQ = 0.5         # m/s^2, ... or has to brake at least noticeably

# required deceleration at cut-in (with 0.5 s reaction time)
MED_A_REQ, HIGH_A_REQ = 2.0, 4.0
EGO_MAX_DECEL = 8.0          # m/s^2, above this no passenger car can avoid the collision

VALIDITY_CHECKS = {
    "not_executable": "esmini failed or produced no log",
    "inconsistent_start": "vehicles overlap at t=0",
    "off_road": "a vehicle leaves the drivable area",
    "implausible_motion": "speed, acceleration or position jump beyond physical limits",
    "manoeuvre_missing": "the cut-in never happens in front of the ego",
}


def validity_issues(run: dict, m: dict | None) -> list[str]:
    if run["returncode"] != 0 or m is None:
        return ["not_executable"]
    issues = []
    if m["init_overlap"]:
        issues.append("inconsistent_start")
    if m["off_road"]:
        issues.append("off_road")
    if (m["max_target_speed"] > MAX_SPEED or m["max_target_long_acc"] > MAX_LONG_ACC
            or m["max_target_lat_acc"] > MAX_LAT_ACC or m["max_position_jump"] > MAX_JUMP):
        issues.append("implausible_motion")
    if not m["cutin_done"]:
        issues.append("manoeuvre_missing")
    return issues


def criticality(m: dict) -> str:
    a = m["a_req"]
    if a > EGO_MAX_DECEL:
        return "unavoidable"
    if a > HIGH_A_REQ:
        return "high"
    if a > MED_A_REQ:
        return "medium"
    return "low"


def verdict(run: dict, m: dict | None) -> dict:
    issues = validity_issues(run, m)
    if issues:
        return {"verdict": "invalid", "issues": issues, "criticality": None}
    relevant = m["thw_entry"] < RELEVANT_THW or m["a_req"] > RELEVANT_A_REQ
    if not relevant:
        return {"verdict": "no_interaction", "issues": [], "criticality": None}
    return {"verdict": "useful", "issues": [], "criticality": criticality(m)}


def finite(x: float) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isinf(x)) else x
