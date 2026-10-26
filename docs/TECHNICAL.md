# Quality assessment of parametric driving scenarios: technical report

## Abstract

A parameter sweep over a highway cut-in produces 144 OpenSCENARIO files. Each file is simulated in esmini and assessed with a three-stage checker: validity, relevance and criticality. 87 scenarios are invalid, 18 require no reaction, 12 are unavoidable, and the remaining 27 collapse into 9 distinct situations once near-duplicates are merged. The checker was tested by injecting six defect types into the 57 accepted scenarios. It rejected 340 of 342 mutants.

## 1. Questions

- **RQ1.** How many scenarios from a naive parameter sweep are usable as tests?
- **RQ2.** Which design choices make scenarios invalid, irrelevant or redundant?
- **RQ3.** Does the checker catch typical scenario bugs, and what does it miss?

## 2. Setup

| | |
|---|---|
| Road | straight, 2 000 m, two lanes of 3 m in one direction (OpenDRIVE, generated) |
| Ego | lane −1, constant speed, no controller |
| Target | starts 50 m ahead in lane −2; changes into lane −1 when the longitudinal free-space gap drops below the trigger gap (sinusoidal lateral profile) |
| Simulator | esmini v3.10.2, headless, fixed step 0.05 s, 20 s |
| Files | generated with scenariogeneration 0.16.7 |

Parameter grid (3 × 4 × 4 × 3 = 144):

| Parameter | Values |
|---|---|
| Ego speed | 80, 100, 120 km/h |
| Target speed − ego speed | −40, −20, 0, +20 km/h |
| Trigger gap | 10, 20, 35, 60 m |
| Lane-change duration | 1, 2, 4 s |

The grid is deliberately naive, like a first sweep set up without looking at the dynamics.

## 3. Method

### 3.1 Validity

A scenario is invalid if any of the following holds:

| Check | Rule |
|---|---|
| Not executable | esmini returns non-zero or writes no log |
| Inconsistent start | bounding boxes overlap at t = 0 |
| Off road | a vehicle box leaves the drivable area |
| Implausible motion | target speed > 200 km/h, \|longitudinal acceleration\| > 10 m/s², \|lateral acceleration\| > 5 m/s², or position change inconsistent with reported speed by > 5 m/s |
| Manoeuvre missing | the target never enters the ego path ahead of the ego |

Accelerations are computed from the logged trajectory (5-sample moving average, finite differences).

### 3.2 Relevance

Let *t*ₑ be the first time step at which the target overlaps the ego lane laterally and is ahead of the ego. The scenario is relevant if the time headway at *t*ₑ is below 1.0 s or the required deceleration (3.3) exceeds 0.5 m/s².

### 3.3 Criticality

The ego does not react in the simulation, so criticality is a property of the scenario rather than of a driving function. At *t*ₑ, with bumper gap *g*, closing speed Δ*v* > 0 and reaction time τ = 0.5 s:

  *a*_req = Δ*v*² / (2 (*g* − Δ*v* τ))

and *a*_req = ∞ if *g* − Δ*v* τ ≤ 0. Classes: low ≤ 2, medium ≤ 4, high ≤ 8, unavoidable > 8 m/s² (beyond the braking capability of a passenger car).

### 3.4 Redundancy

Useful scenarios that share target speed difference, trigger gap and lane-change duration are counted as one situation. Within each group the class is identical and *a*_req differs by at most 1.1 m/s² across ego speeds; most groups differ by less than 0.1 m/s².

### 3.5 Testing the checker

Mutation test: each of six defects is injected into every scenario the checker accepted (57 valid scenarios), giving 342 mutants. A mutant counts as detected if it is rejected as invalid.

## 4. Results

### 4.1 RQ1: usable scenarios

| Stage | Scenarios |
|---|---|
| Generated | 144 |
| Valid | 57 |
| Relevant | 39 |
| Passable (not unavoidable) | 27 |
| Distinct situations | 9 |

Useful scenarios by criticality: 15 low, 6 medium, 6 high, 12 unavoidable. The counts are identical for the three ego speeds.

### 4.2 RQ2: causes

| Cause | Scenarios | Design reason |
|---|---|---|
| Cut-in never triggered | 54 | target as fast or faster than ego, gap never shrinks below the trigger value |
| Implausible lateral motion | 30 | 1 s lane change, 14–18 m/s² lateral acceleration |
| Ego already alongside | 3 | 10 m trigger, −40 km/h, 4 s lane change: the ego passes before the target reaches its lane |
| No reaction needed | 18 | cut-in at ~40 m or more with small or no closing speed |
| Unavoidable | 12 | short gap and high closing speed; or slow lane change that lets the gap close |

Two observations are not obvious from the parameters:

1. **Ego speed adds no information under this metric.** *a*_req depends on closing speed and gap, so the three ego speeds produce the same classes. This triples the set without adding a distinct test.
2. **Slower lane changes raise criticality.** Holding speed difference and gap fixed, moving from 2 s to 4 s increases *a*_req in all six pairs where both scenarios are valid, and raises the class in three of them (−40 km/h, 35 m: medium → high; −40 km/h, 60 m: low → medium; −20 km/h, 10 m: high → unavoidable). The target enters the ego path later, when the gap has already closed.

### 4.3 RQ3: checker

| Defect | Detected | Detected via |
|---|---|---|
| Spawn overlap | 57 / 57 | inconsistent start |
| Off road | 57 / 57 | off road (sometimes also implausible motion) |
| Teleport (+30 m) | 57 / 57 | implausible motion |
| Snap lane change (0.3 s) | 57 / 57 | implausible motion |
| Dead trigger | 57 / 57 | manoeuvre missing |
| Unit error (km/h written as m/s) | 55 / 57 | implausible motion, or indirectly via manoeuvre missing (5 cases) |

The two missed mutants have a target speed of 40 m/s (144 km/h) after the error, which is plausible on a highway. In those cases the defect only changes relevance, and no physics-based check can catch it.

Sanity check in the other direction: of 60 scenarios that were valid by design (lane change ≥ 2 s and a trigger that can fire), 3 were rejected. All 3 are true problems (the ego is already alongside the target), not false alarms.

### 4.4 Sensitivity

The logged runs were re-assessed with one assumption changed at a time (`scripts/sensitivity.py`, no new simulation):

| Variant | Valid | Relevant | Passable | Distinct |
|---|---|---|---|---|
| Baseline | 57 | 39 | 27 | 9 |
| Reaction time 0.3 s | 57 | 39 | 28 | 10 |
| Reaction time 1.0 s | 57 | 40 | 22 | 8 |
| Lateral limit 3 m/s² | 27 | 18 | 12 | 4 |
| Lateral limit 7 m/s² | 57 | 39 | 27 | 9 |
| Relevant if headway < 0.5 s or braking > 0.25 m/s² | 57 | 45 | 33 | 11 |
| Relevant if headway < 2.0 s or braking > 1.0 m/s² | 57 | 53 | 41 | 15 |
| Max ego braking 6 m/s² | 57 | 39 | 26 | 9 |
| Max ego braking 10 m/s² | 57 | 39 | 27 | 9 |

The number of distinct, passable tests ranges from 4 to 15 of 144. The qualitative conclusion (most of a naive sweep is not useful) holds in every variant. The exact count depends most on the lateral-acceleration limit, which decides whether 2 s lane changes (peak about 4 m/s²) are plausible, and on the definition of relevance. Reaction time and braking capability matter little.

## 5. Limitations

- One manoeuvre on a straight road, one simulator. Curved roads and junctions need lane-relative instead of world-x distances.
- Thresholds are literature-style defaults, not calibrated on naturalistic driving data.
- Criticality uses a constant-speed ego with a fixed reaction time. It ranks scenarios, but it does not predict how a specific driving function performs.
- The redundancy rule is defined by parameters. A behaviour-based rule (for example clustering trajectories or system responses) would be more general.

## 6. Next steps

1. Cross-simulator consistency: run the same files in CARLA ScenarioRunner and compare verdicts and metrics with esmini.
2. Extend to more manoeuvres and real OpenDRIVE maps, using lane-relative coordinates.
3. Use the checker as a filter and as feedback for LLM-generated scenarios, and measure how often generated files are valid and relevant.
4. Replace the parameter-based redundancy rule with a behaviour-based one.

## Reproduce

```bash
pip install -r requirements.txt
bash scripts/get_esmini.sh
ESMINI_BIN=esmini/bin/esmini python scripts/pipeline.py --out outputs
python scripts/report.py --out outputs --docs docs
python scripts/sensitivity.py --out outputs
pytest -q
```

Per-scenario results: `reports/grid_results.csv`, `reports/defect_results.csv`, summary in `reports/summary.json`, sensitivity in `reports/sensitivity.csv`. Thresholds are in `sq/assess.py`.
