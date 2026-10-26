"""Generate a parametric family of highway cut-in scenarios as OpenSCENARIO files.

Each scenario: the ego car drives at constant speed in lane -1 of a straight two-lane
road (no driving function, so the assessment depends on the scenario only). A target car starts 50 m ahead in lane -2
and cuts into the ego lane once the longitudinal gap drops below ``gap``.

The grid is deliberately "naive", the way a parameter sweep is often set up in practice.
Whether each resulting scenario is a useful test is decided later by ``sq.assess``.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from scenariogeneration import xodr, xosc

LANE_WIDTH = 3.0
ROAD_LENGTH = 2000.0
EGO_S0 = 50.0
TARGET_DX0 = 50.0
SIM_TIME = 20.0


@dataclass(frozen=True)
class CutIn:
    v_ego_kmh: float
    dv_kmh: float          # target speed minus ego speed
    gap_m: float           # trigger: longitudinal free-space gap below this value
    t_lc_s: float          # lane-change duration (sinusoidal)
    defect: str = "none"   # seeded defect, see DEFECTS

    @property
    def name(self) -> str:
        n = f"cutin_v{self.v_ego_kmh:g}_dv{self.dv_kmh:+g}_g{self.gap_m:g}_t{self.t_lc_s:g}"
        return n if self.defect == "none" else f"{n}__{self.defect}"


GRID = dict(
    v_ego_kmh=[80, 100, 120],
    dv_kmh=[-40, -20, 0, 20],
    gap_m=[10, 20, 35, 60],
    t_lc_s=[1, 2, 4],
)

# Defects injected into otherwise valid scenarios to test the checker itself.
DEFECTS = {
    "spawn_overlap": "target spawned inside the ego vehicle",
    "off_road": "target spawned outside the drivable road",
    "teleport": "target jumps 30 m forward mid-scenario",
    "dead_trigger": "cut-in trigger can never fire",
    "unit_error": "target speed written in km/h instead of m/s",
    "snap_lane_change": "lane change in 0.3 s",
}


def grid() -> list[CutIn]:
    keys = list(GRID)
    return [CutIn(**dict(zip(keys, vals))) for vals in itertools.product(*GRID.values())]


def write_road(path: Path) -> None:
    road = xodr.create_road(xodr.Line(ROAD_LENGTH), id=0, left_lanes=0, right_lanes=2, lane_width=LANE_WIDTH)
    odr = xodr.OpenDrive("highway")
    odr.add_road(road)
    odr.adjust_roads_and_lanes()
    odr.write_xml(str(path))


def _vehicle() -> xosc.Vehicle:
    bb = xosc.BoundingBox(1.9, 4.6, 1.5, 1.3, 0, 0.75)
    fa = xosc.Axle(0.52, 0.8, 1.68, 2.98, 0.4)
    ba = xosc.Axle(0.52, 0.8, 1.68, 0, 0.4)
    # max speed 69 m/s, max acceleration 4 m/s^2, max deceleration 8 m/s^2
    return xosc.Vehicle("car", xosc.VehicleCategory.car, bb, fa, ba, 69, 4, 8)


def build(c: CutIn, road_file: str) -> xosc.Scenario:
    ve = c.v_ego_kmh / 3.6
    vt = (c.v_ego_kmh + c.dv_kmh) / 3.6
    car = _vehicle()

    ent = xosc.Entities()
    ent.add_scenario_object("Ego", car)
    ent.add_scenario_object("Target", car)

    step = xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 0)
    tgt_s, tgt_lane, tgt_offset = EGO_S0 + TARGET_DX0, -2, 0.0
    if c.defect == "unit_error":
        vt = c.v_ego_kmh + c.dv_kmh
    if c.defect == "spawn_overlap":
        tgt_s, tgt_lane = EGO_S0 + 1.0, -1
    if c.defect == "off_road":
        tgt_offset = -2.5 * LANE_WIDTH

    init = xosc.Init()
    init.add_init_action("Ego", xosc.TeleportAction(xosc.LanePosition(EGO_S0, 0, -1, 0)))
    init.add_init_action("Ego", xosc.AbsoluteSpeedAction(ve, step))
    init.add_init_action("Target", xosc.TeleportAction(xosc.LanePosition(tgt_s, tgt_offset, tgt_lane, 0)))
    init.add_init_action("Target", xosc.AbsoluteSpeedAction(vt, step))

    gap = 0.01 if c.defect == "dead_trigger" else c.gap_m
    t_lc = 0.3 if c.defect == "snap_lane_change" else c.t_lc_s
    lc = xosc.AbsoluteLaneChangeAction(-1, xosc.TransitionDynamics(
        xosc.DynamicsShapes.sinusoidal, xosc.DynamicsDimension.time, t_lc))
    cond = xosc.RelativeDistanceCondition(gap, xosc.Rule.lessThan, xosc.RelativeDistanceType.longitudinal,
                                          "Ego", freespace=True)
    ev = xosc.Event("cutin", xosc.Priority.override)
    ev.add_action("lane_change", lc)
    ev.add_trigger(xosc.EntityTrigger("gap", 0, xosc.ConditionEdge.none, cond, "Target"))

    man = xosc.Maneuver("cutin_maneuver")
    man.add_event(ev)
    if c.defect == "teleport":
        jump = xosc.Event("jump", xosc.Priority.parallel)
        jump.add_action("teleport", xosc.TeleportAction(xosc.RelativeLanePosition(0, "Target", 0, ds=30)))
        jump.add_trigger(xosc.ValueTrigger("t", 0, xosc.ConditionEdge.rising,
                                           xosc.SimulationTimeCondition(12, xosc.Rule.greaterThan)))
        man.add_event(jump)

    mg = xosc.ManeuverGroup("target_group")
    mg.add_actor("Target")
    mg.add_maneuver(man)
    stop = xosc.ValueTrigger("stop", 0, xosc.ConditionEdge.rising,
                             xosc.SimulationTimeCondition(SIM_TIME, xosc.Rule.greaterThan), "stop")
    act = xosc.Act("act", stoptrigger=stop)
    act.add_maneuver_group(mg)
    sb = xosc.StoryBoard(init, stop)
    sb.add_act(act)
    return xosc.Scenario(c.name, "scenario-quality", xosc.ParameterDeclarations(), ent, sb,
                         xosc.RoadNetwork(road_file), xosc.Catalog())


def write_set(cases: list[CutIn], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    write_road(out / "highway.xodr")
    meta = []
    for c in cases:
        build(c, "highway.xodr").write_xml(str(out / f"{c.name}.xosc"))
        meta.append({"name": c.name, **asdict(c)})
    (out / "scenarios.json").write_text(json.dumps(meta, indent=1))
