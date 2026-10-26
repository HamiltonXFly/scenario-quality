"""Per-scenario metrics from an esmini CSV log (straight road along +x).

The ego vehicle drives at constant speed (no controller). Criticality is therefore a
property of the scenario itself, not of a particular driving function: we ask how hard
the ego *would have to brake* at the moment the target enters its path.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ROAD_Y = (-6.0, 0.0)     # drivable area of the two-lane road (lanes -1 and -2, 3 m each)
REACTION_TIME = 0.5      # s, delay before the ego can start braking


def load_log(path: str) -> dict[str, pd.DataFrame]:
    raw = pd.read_csv(path, skiprows=6, skipinitialspace=True)
    raw.columns = [c.strip() for c in raw.columns]
    out = {}
    for i in (1, 2):
        cols = {c: c.split(" ", 1)[1].split(" [")[0] for c in raw.columns if c.startswith(f"#{i} ")}
        d = raw[["TimeStamp [s]", *cols]].rename(columns={"TimeStamp [s]": "t", **cols})
        name = str(d["Entity_Name"].iloc[0]).strip()
        h = d["World_Heading_Angle"]
        out[name] = pd.DataFrame({
            "t": d["t"].to_numpy(float),
            "x": (d["World_Position_X"] + d["bb_x"] * np.cos(h)).to_numpy(float),
            "y": (d["World_Position_Y"] + d["bb_x"] * np.sin(h)).to_numpy(float),
            "v": d["Current_Speed"].to_numpy(float),
            "L": d["bb_length"].to_numpy(float),
            "W": d["bb_width"].to_numpy(float),
        })
    return out


def smooth(a: np.ndarray, k: int = 5) -> np.ndarray:
    if len(a) < k:
        return a
    pad = np.pad(a, k // 2, mode="edge")
    return np.convolve(pad, np.ones(k) / k, mode="valid")


def compute(path: str) -> dict:
    d = load_log(path)
    e, g = d["Ego"], d["Target"]
    t = e["t"].to_numpy()
    dt = float(np.median(np.diff(t)))

    dx = g["x"].to_numpy() - e["x"].to_numpy()
    half_len = (e["L"].to_numpy() + g["L"].to_numpy()) / 2
    lat_overlap = np.abs(g["y"].to_numpy() - e["y"].to_numpy()) < (e["W"].to_numpy() + g["W"].to_numpy()) / 2
    gap = dx - half_len                          # bumper-to-bumper distance
    in_path = lat_overlap & (dx > 0)

    # motion plausibility of the target
    v_t = g["v"].to_numpy()
    long_acc = np.abs(np.gradient(smooth(v_t), dt))
    lat_acc = np.abs(np.gradient(np.gradient(smooth(g["y"].to_numpy()), dt), dt))
    step = np.hypot(np.diff(g["x"]), np.diff(g["y"])) / dt
    jump = float(np.max(np.abs(step - v_t[1:]))) if len(step) else 0.0

    lo, hi = ROAD_Y
    def off(df):
        return bool(((df["y"] - df["W"] / 2 < lo - 0.05) | (df["y"] + df["W"] / 2 > hi + 0.05)).any())

    m = {
        "init_overlap": bool(lat_overlap[0] and abs(dx[0]) < half_len[0]),
        "off_road": off(e) or off(g),
        "max_target_speed": float(v_t.max()),
        "max_target_long_acc": float(long_acc.max()),
        "max_target_lat_acc": float(lat_acc.max()),
        "max_position_jump": jump,
        "cutin_done": bool(in_path.any()),
        "side_contact": bool((lat_overlap & (np.abs(dx) < half_len) & ~in_path).any()),
    }
    if not in_path.any():
        return {**m, "t_entry": None, "gap_entry": None, "ttc_entry": None, "thw_entry": None, "a_req": 0.0}

    i = int(np.argmax(in_path))                  # first step the target is in the ego path
    rel_v = e["v"].iloc[i] - v_t[i]
    gap_i = float(gap[i])
    gap_eff = gap_i - max(rel_v, 0.0) * REACTION_TIME
    if gap_i <= 0 or (rel_v > 0 and gap_eff <= 0):
        a_req = float("inf")                     # already touching, or contact before braking starts
    elif rel_v > 0:
        a_req = rel_v ** 2 / (2 * gap_eff)
    else:
        a_req = 0.0
    return {
        **m,
        "t_entry": float(t[i]),
        "gap_entry": gap_i,
        "ttc_entry": gap_i / rel_v if rel_v > 0 and gap_i > 0 else float("inf"),
        "thw_entry": gap_i / max(e["v"].iloc[i], 0.1),
        "a_req": a_req,
    }
