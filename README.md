# scenario-quality

Checks whether generated driving scenarios are actually useful as simulation tests.

I wrote a parameter sweep for a simple highway cut-in (a car merges into the ego lane), exported every combination as an OpenSCENARIO file, ran them in [esmini](https://github.com/esmini/esmini) and checked each run for three things:

1. Is the scenario valid? It has to run, start in a consistent state, move in a physically plausible way, and the cut-in has to actually happen.
2. Does the ego have to react at all?
3. How critical is it? Measured as how hard the ego would have to brake after a 0.5 s reaction time.

![Three of the scenarios in esmini](docs/cutin_examples.gif)

Top: a useful test. Middle: the car merges so close that a crash is unavoidable. Bottom: a 1 s lane change, which no real car does.

## Results

Of 144 generated scenarios, 57 are valid, 39 require a reaction, and 27 are still passable. Many of those are near-duplicates (same speed difference, gap and lane-change time, only the ego speed differs), which leaves 9 distinct tests.

![Funnel](docs/fig1_funnel.png)

![Verdict per scenario](docs/fig2_grid.png)

Some things I did not expect:

- 54 scenarios never trigger the cut-in. The trigger is "gap below X m", and if the other car is not slower than the ego, the gap never shrinks.
- All 1 s lane changes are implausible (14 to 18 m/s² lateral acceleration).
- The ego speed makes no difference to the criticality class here, because the required braking only depends on relative speed and gap.
- A slower lane change makes the cut-in more critical, not less: the car enters the lane later, when the gap is already smaller.

![Example trajectories](docs/fig3_examples.png)

## Does the checker catch bugs?

I took the 57 scenarios that passed and broke each of them in six ways:

| Bug | Caught |
|---|---|
| cars spawned inside each other | 57 / 57 |
| car spawned off the road | 57 / 57 |
| car teleports 30 m | 57 / 57 |
| lane change in 0.3 s | 57 / 57 |
| trigger that can never fire | 57 / 57 |
| speed written in km/h instead of m/s | 55 / 57 |

The two misses are unit errors where 40 km/h became 144 km/h. That is still a normal highway speed, so a physics check cannot see it.

## How sensitive is this to my thresholds?

Changing one threshold at a time (reaction time, lateral acceleration limit, relevance criterion, max braking) gives between 4 and 15 distinct tests instead of 9. The lateral acceleration limit matters most, because it decides whether 2 s lane changes (about 4 m/s²) count as plausible. Full table in [docs/TECHNICAL.md](docs/TECHNICAL.md#44-sensitivity).

## Notes

- My first version drove the ego with esmini's built-in ACC controller. It braked from 100 km/h to under 10 km/h in about one second, which is not physically possible, so the criticality numbers were meaningless. I switched to a constant-speed ego and compute the required braking instead. This measures the scenario, not a particular driving function.
- Three scenarios I expected to be fine were rejected. In those, the ego is already next to the other car when it starts to merge, so the checker was right.

## Limitations

- Only one manoeuvre, on a straight road, in one simulator.
- Thresholds are reasonable defaults, not calibrated on real driving data.
- "Near-duplicate" is defined by parameters. A real driving function might behave differently at 80 and 120 km/h.

Next things I want to try: running the same files in CARLA ScenarioRunner to see whether the verdicts agree, and checking scenarios written by an LLM from text descriptions.

## Usage

```bash
pip install -r requirements.txt
bash scripts/get_esmini.sh          # downloads esmini (Linux x86-64)
ESMINI_BIN=esmini/bin/esmini python scripts/pipeline.py --out outputs
python scripts/report.py --out outputs --docs docs
python scripts/sensitivity.py --out outputs
pytest -q
```

The GIF is made with `xvfb-run -a -s "-screen 0 1280x720x24" python scripts/record_gif.py`. Per-scenario results are in `reports/`, details in [docs/TECHNICAL.md](docs/TECHNICAL.md).
