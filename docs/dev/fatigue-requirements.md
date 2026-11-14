# Fatigue analysis: data requirements (2026-11-14)

Context: the user's professor suggested deriving a fatigue formula from the training data
(when, which exercise order, which weight -> how much performance drops). A first analysis
(`analysis/fatigue.py`, outputs in `data/reports/fatigue_sets.csv` and `motion_sets.csv`) found:

- Rep counts alone show no fatigue signal: between consecutive sets at the same weight, reps were
  equal 48 %, lower 25 %, higher 27 % (112 pairs, 15 workouts). Most sets stop well before failure.
- Rep speed does show it in clean sets (e.g. 0577 set 1 on 2026-11-13: rep gaps 3.2 s -> 5.5 s),
  but only 4 of 27 set files have a watch count equal to the logged reps, so per-rep timing and
  `vel` are not trustworthy yet.
- Set 1 is a poor baseline: in 65 of 188 set-to-set steps the weight went up (ramping).

This file lists what the analysis needs from the app and the watch. It does not repeat what is
already built (see `rep-counter.md`). Priorities: P1 blocks the analysis, P2 makes it much better,
P3 is for the longer-term models.

## 1. Data to record (new)

| # | Pri | What | Where | Why |
|---|-----|------|-------|-----|
| 1.1 | P1 | Per-rep features in the set file: for every counted rep `{t_start, t_end, size, period, source}` (size = the swing size RepCounter already computes; t_start/t_end = the swing's bounds, not only the moment it was counted) | `helpers` in the CSV header, e.g. `helpers.reps: [...]` | Today only the count time (`log: [s, "rep N speed"]`) and the set summary `vel {best,last,loss}` are saved. Fatigue needs the speed and duration of each rep. Tilt-only reps have no size, so `vel` is null for e.g. assisted pull-up. |
| 1.2 | P1 | RIR (reps in reserve) or RPE per set | Watch: a quick crown pick after Done (0 / 1 / 2 / 3 / 4+). The set object already supports `rir` / `rpe` (`coach-context.js` SET_KEYS); the `effort` setting is off. | The label that turns "slower reps" into "how close to failure". Without it a velocity-loss formula cannot be calibrated. |
| 1.3 | P2 | A "reps confirmed" flag per set: true when the user changed the reps with the crown or explicitly accepted the count | Set file metadata + server set | `Done with 0 counted logs the goal`, and an untouched count looks the same as a checked one. The analysis must know which labels are ground truth. |
| 1.4 | P2 | Set start time on the server set (not only `at` = done) | Server set: `startAt` | Real rest = this set's start - the previous set's end. Today rest is approximated by done-to-done, which includes the set's own duration. |
| 1.5 | P3 | Bar / machine base weight, so `w = 0` (Smith bar only) becomes a real load | `barWeights` (empty today) or a per-exercise base load | Load-velocity profiles need the real load. |
| 1.6 | P3 | Sleep duration of the night before (Apple Health) next to the existing `daily` RHR / HRV | Workout HR file `daily` | A covariate for session-level readiness. |

## 2. Accuracy to improve (existing data)

| # | Pri | Problem | Measured | Target |
|---|-----|---------|----------|--------|
| 2.1 | P1 | Rep counter: watch count vs reps at Done | 2026-11-13: 30 % exact, 39 % within 1, bias +1.9 (max of the two counters adds both overcounts) | >= 80 % exact on wrist-moving exercises. Fuse the speed and tilt signals (already planned as "v3"); drop setup moves at the start. |
| 2.2 | P1 | Rep boundaries: double counts show as 0-1.3 s gaps inside a set (e.g. 6392 set 3: 15 counted, 8 done) | see `motion_sets.csv` `intervals_s` | No rep gap under ~40 % of the set's median gap. |
| 2.3 | P1 | `vel.loss` clipped to 0 when the last reps are "faster" than the best of the first 3; this happens when the first reps were missed or mis-sized | 4 of 17 sets with `vel` on 2026-11-13 have loss 0 | Per-rep sizes (1.1) let the analysis compute its own loss; keep the summary as is. |
| 2.4 | P2 | Speed is relative (integrated wrist acceleration, both directions of the swing) | n/a | Document the unit and keep the method fixed, so values are comparable across weeks. If possible, a concentric-only size (the lifting half) as a second field. |
| 2.5 | P2 | Missing set files: no Start set, sets shorter than 2 s, data gaps when the watch app is suspended | 2026-11-13: 22 set files for 20 logged sets, some duplicated (1350 s2, 0192 s2) | A set file for every done set; duplicates marked (`superseded: true`) instead of two files with the same set number. |

## 3. Behaviour the user needs (no code)

- Correct the reps with the crown before Done, every set.
- Keep working sets at the same weight where possible (ramp in warm-up sets, then fixed).
- Take one or two machine exercises per session close to failure (safely), so the slow-down is visible.
- Body scan: same time, morning, fasted, before training. Weekly.

## 4. Other models and what each needs

| Model | Idea | Needs | Time to first result |
|-------|------|-------|----------------------|
| A. Within-set velocity loss (VBT) | `VL = 1 - v_last / v_best` per set; relate VL to RIR | 1.1, 1.2, 2.1-2.3 | ~2-3 weeks of labelled sets |
| B. Load-velocity profile | Per exercise, a linear fit of first-rep speed vs load; today's speed at a known load vs the profile = readiness / estimated 1RM without testing | 1.1, 1.5, sets at 3+ different loads per exercise | ~3-4 weeks |
| C. Between-set fatigue (the professor's idea, refined) | `slowdown(set n) ~ rest time + set number + prior sets on the same muscle` | 1.1, 1.4, 2.1 | ~4-6 weeks |
| D. Fitness-fatigue (Banister impulse-response) | `performance(t) = p0 + k1 * fitness(t) - k2 * fatigue(t)`, both exponentially decayed sums of the daily training load | A daily load (volume load or session RPE x minutes, needs 1.2) and one repeated performance measure (B's estimated 1RM, or speed at a fixed load) | ~2-3 months |
| E. HR recovery | Heart-rate drop in the first 60 s of rest vs set number and HR at Done | `hrCurve` (exists since 2026-11-13) | ~2-3 weeks |
| F. Readiness | Session performance vs RHR / HRV / sleep deviation from baseline | `daily` (exists, needs 7 days), 1.6, B | ~1-2 months |

The literature thresholds for VL (e.g. 20 % vs 40 %) and Banister parameters come from research on
barbell lifts with linear position transducers. A wrist-worn IMU is a different instrument, so the
user's own values must be fitted, not copied.

## Data notes for whoever implements

- Match a set file to the server set by `wid` + `exId` + `at == end` (within 1 ms).
- One-arm exercises (0192, 1350, 1454) are Per side; only the watch arm's sides are recorded.
- Keep the CSV header backwards compatible: add keys, do not rename `reps`, `auto`, `vel`, `helpers.log`.
- All personal data stays in `data/` (gitignored). This fork is public.
