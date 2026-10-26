import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sq import assess, generate  # noqa: E402

OK_RUN = {"returncode": 0}
BASE = dict(init_overlap=False, off_road=False, max_target_speed=20.0, max_target_long_acc=0.0,
            max_target_lat_acc=2.0, max_position_jump=0.0, cutin_done=True, side_contact=False,
            t_entry=5.0, gap_entry=15.0, ttc_entry=3.0, thw_entry=0.6, a_req=1.2)


def v(**kw):
    return assess.verdict(OK_RUN, {**BASE, **kw})


def test_useful_low():
    assert v() == {"verdict": "useful", "issues": [], "criticality": "low"}


def test_criticality_levels():
    assert v(a_req=3.0)["criticality"] == "medium"
    assert v(a_req=5.0)["criticality"] == "high"
    assert v(a_req=math.inf)["criticality"] == "unavoidable"


def test_no_interaction():
    assert v(thw_entry=2.0, a_req=0.0)["verdict"] == "no_interaction"


def test_each_validity_issue():
    assert assess.verdict({"returncode": 1}, None)["issues"] == ["not_executable"]
    assert v(init_overlap=True)["issues"] == ["inconsistent_start"]
    assert v(off_road=True)["issues"] == ["off_road"]
    assert v(max_target_lat_acc=9.0)["issues"] == ["implausible_motion"]
    assert v(max_position_jump=30.0)["issues"] == ["implausible_motion"]
    assert v(cutin_done=False)["issues"] == ["manoeuvre_missing"]


def test_grid_and_defects():
    g = generate.grid()
    assert len(g) == 144 and len({c.name for c in g}) == 144
    names = {generate.CutIn(**{**g[0].__dict__, "defect": d}).name for d in generate.DEFECTS}
    assert len(names) == len(generate.DEFECTS)


def test_xosc_written(tmp_path):
    generate.write_set(generate.grid()[:2], tmp_path)
    files = sorted(tmp_path.glob("*.xosc"))
    assert len(files) == 2
    txt = files[0].read_text()
    assert "LaneChangeAction" in txt and "highway.xodr" in txt
