# Workout library

Source of truth for `tools/generate_workout.py`. Each section gives the canonical interval prescription, when to prescribe, when to skip (knee + HRV gates), example `.zwo` skeleton, and TSS estimate.

Zones referenced here are defined in `docs/zones.md`. PMC interpretation in `docs/training-science.md`. Distribution rules in `docs/training-distribution.md`.

## Operating principles

1. **No two hard days back-to-back.** Z4+ session today → Z1/Z2 or rest tomorrow.
2. **Knee gates apply.** Skip session if knee score ≥4/10. Reduce intensity if cadence drops below 70 rpm under load.
3. **HRV gates apply.** Per `docs/wellness.md`: rMSSD < (7-day mean − SWC) for ≥2 days → swap hard for Z2.
4. **Cold-start rule.** First 10 min of every session is Z1/Z2 minimum, regardless of the planned set.
5. **Strength → before easy ride or rest day.** Never combine heavy lower-body strength with Z4+ cycling.

---

## Endurance (Z2)

The bread and butter. Highest TSS-yield per recovery cost; the foundation under everything else.

- **Target zone:** Z2 (56–75% FTP, or 81–89% LTHR if power-less).
- **Duration:** 60–240 min. Long ride 3–5 h on Sunday Ängby söndag.
- **Structure:** Steady. Optional: 3–5×30s spin-ups (90+ rpm, ≤Z3) every 15 min to keep neuromuscular fitness ticking over.
- **Cadence:** 85–95 rpm.
- **TSS estimate:** ~50 TSS/h at low Z2, ~75 TSS/h at high Z2.

**When to prescribe:** every endurance day. The default ride.

**When to skip:** never (this is the recovery-compatible session). On a true recovery day, scale duration not intensity.

**Knee:** safe. If knee is yellow, drop to flat-only and avoid out-of-saddle climbing.

---

## Recovery (Z1)

Active recovery between hard days. Easier than endurance.

- **Target zone:** Z1 (<55% FTP, or <81% LTHR).
- **Duration:** 30–60 min.
- **Structure:** Easy spin. RPE ≤3/10. No prolonged out-of-saddle.
- **Cadence:** 85–95 rpm.
- **TSS estimate:** 20–30 TSS.

**When to prescribe:** day after Z4+ session. After races. When HRV-gated.

**When to skip:** if you'd rather a full rest day, take the rest day. Don't force a recovery ride.

**Knee:** safest possible session. Use it if symptoms flared.

---

## Sweet spot training (SST) — the workhorse

Highest training stress per fatigue cost. The interval Martin should see most often in build phases.

- **Target zone:** 88–94% FTP (sweet spot — straddles Z3 high / Z4 low).
- **Work:rest ratio:** roughly 4:1 (e.g. 20' on, 5' off).
- **Templates:**
  - **2×20' @ 90% FTP, 5' Z2 rest** — gold standard, 1 h work
  - **3×15' @ 90–92% FTP, 4' Z2 rest** — fresh-legs day, 45 min work
  - **4×10' @ 92–94% FTP, 3' Z2 rest** — when FTP recently bumped, 40 min work
- **Cadence:** 85–95 rpm. Drop intervals if cadence falls below 80.
- **TSS estimate:** 90–110 TSS for the standard 2×20'.

**When to prescribe:** 2–3× per week in build phases (per pyramidal default). Pair with one weekly Z4 for variety.

**When to skip:** TSB < -30; HRV-gated; knee yellow.

**Knee:** moderate risk if cadence drops. Cap at 85 rpm minimum on intervals.

Source: [TrainerRoad — Sweet Spot Training](https://www.trainerroad.com/blog/sweet-spot-training-everything-you-need-to-know/).

---

## Threshold (Z4)

Lactate threshold — the longest you can sustain.

- **Target zone:** 95–105% FTP.
- **Work:rest ratio:** 2:1 to 3:1 (longer rests than SST).
- **Templates:**
  - **2×20' @ 95–100% FTP, 5' Z2 rest** — the gold standard, ~40 min work
  - **3×15' @ 100–105% FTP, 5' rest** — sharper, 45 min work
  - **4×10' @ 100–105% FTP, 4' rest** — punchier, 40 min work
  - **Over-unders: 30s @ 105% / 30s @ 95%, 6×3 min on, 3 min Z2 between sets** — race-specific
- **Cadence:** 85–95 rpm. Some riders prefer slightly higher (90+) for threshold.
- **TSS estimate:** 90–105 TSS for 2×20'.

**When to prescribe:** once per week in build phases. Replace SST with threshold occasionally for variety; don't double up in the same week without a recovery week chaser.

**When to skip:** TSB < -25; HRV-gated; ≥3/10 knee.

**Knee:** moderate-high risk on out-of-saddle. Stay seated unless the gradient demands otherwise.

---

## VO2max (Z5)

Aerobic ceiling. High cost, high reward — but used sparingly.

- **Target zone:** 106–120% FTP.
- **Work:rest ratio:** 1:1 to 1:1.5 (rest is short to keep systems loaded).
- **Templates:**
  - **5×4' @ 110–115% FTP, 4' Z2 rest** — classic, 40 min work
  - **4×4' Norwegian @ 110–120% FTP, 3' Z2 rest** — Seiler-flavored, 28 min work
  - **6×3' @ 115–120% FTP, 3' Z2 rest** — punchier
  - **30/15s: 30s @ 120%, 15s @ 60%, 13× = ~10 min, repeat 2-3×** — micro-intervals
- **Cadence:** 95–105 rpm (high).
- **TSS estimate:** 90–110 TSS for 5×4'.

**When to prescribe:** once weekly maximum. Pair the next day with Z2 or recovery. Use during pre-A-race polarization (6–8 wks out) and as the "intensity dose" in build weeks.

**When to skip:** TSB < -20; HRV-gated; knee score ≥3/10. **Never two days after another Z5 session.**

**Knee:** higher risk because of the high cadence + power. Stop the set if knee creeps up to 3/10.

Source: [FasCat — VO2max Intervals](https://fascatcoaching.com/blogs/training-tips/vo2-max-intervals/).

---

## Anaerobic / Neuromuscular (Z6/Z7)

Sprint and short-burst capacity. Not a focus for Martin's endurance / group-ride / occasional-KOM goals.

- **Target zone:** Z6 (121–150% FTP) for 30s–2min; Z7 (max sprint) for 5–15s.
- **Templates:** sprint sets, e.g. 6×30s all-out with 4 min Z1 rest.
- **TSS estimate:** 30–50 TSS for a sprint workout (low aerobic load, but high neuromuscular fatigue).

**When to prescribe:** rarely. Maybe once every 3–4 weeks in pre-race phase if there's a specific punchy crit or lead-out to prepare for. Otherwise skip — the SST/Threshold/VO2 trio covers Martin's needs.

**Knee:** higher risk because of out-of-saddle sprint mechanics. Unless specifically targeted, skip.

---

## Race / event

Variable-zone, real-world. Group rides (Ängby söndag, Onsdagsgrus), races, sportives.

- **Estimate TSS** via NP if ride was ≥30 min (per `docs/training-science.md` NP edge cases). Otherwise hrTSS.
- **Classify session-type** for distribution accounting via Seiler rule: ≥75% time in Z1/Z2 → call it "endurance" for the weekly count, even if there were Z5 surges (per `docs/training-distribution.md`).
- **Recovery after:** if total TSS > 150, the next day is Z2 ≤90 min or rest. If > 250, recovery + check knee.

---

## Knee rehab "session"

Not a workout in the traditional sense, but `tools/generate_workout.py` can emit a 15–25 min rehab block as a structured event. Source: `docs/knee-rehab.md`.

- **TSS:** 0 (no aerobic load worth counting).
- **When to prescribe:** Mon + Fri minimum during build. Daily-mobility OK any day.
- **Calendar treatment:** separate event from the bike workout, or appended to a recovery / Z2 day.

---

## Picking the week's mix

The `coach` subagent uses `docs/training-distribution.md` rules to choose how many sessions of each type per week. As a rough guide for Martin (single-A-race build phase, pyramidal):

| Day | Default |
|---|---|
| Mon | Rest or short recovery + knee rehab |
| Tue | Mid-week intensity (group ride or solo SST/Threshold) |
| Wed | Onsdagsgrus (Z2/Z3 gravel) or solo endurance |
| Thu | The "other" intensity slot — VO2 or threshold |
| Fri | Rest + knee rehab + light strength |
| Sat | Pre-Sunday: easy spin / activation |
| Sun | **Ängby söndag 07:30** — long ride, anchor |

The actual mix shifts by phase: pyramidal in build, polarized 6–8 wks pre-A-race, recovery weeks every 3–4 weeks.

## `.zwo` skeleton (for `tools/export_workout.py`)

Example: 2×20' SST. The exporter wraps this with a `<warmup>` and `<cooldown>`.

```xml
<workout_file>
  <author>Training-Mate</author>
  <name>SST 2x20</name>
  <description>Sweet spot 2x20 @ 90% FTP, 5' Z2 between</description>
  <sportType>bike</sportType>
  <workout>
    <Warmup Duration="900" PowerLow="0.45" PowerHigh="0.65"/>
    <SteadyState Duration="1200" Power="0.90"/>
    <SteadyState Duration="300" Power="0.55"/>
    <SteadyState Duration="1200" Power="0.90"/>
    <Cooldown Duration="600" PowerLow="0.55" PowerHigh="0.40"/>
  </workout>
</workout_file>
```

Powers are FTP fractions. `Duration` is seconds. The exporter computes elapsed time, target TSS, and embeds them in the description.

## TSS budget per week (rough)

By form state, what total weekly TSS is sustainable:

| Form state | Suggested weekly TSS budget |
|---|---|
| Detrained | 200–400 (re-entry) |
| Race-ready (peak) | 400–600 (taper) |
| Productive (build) | 500–800 |
| Overreached | 300–500 (recovery-leaning) |
| Crashing / risky | < 300 (recovery week) |

The `coach` subagent uses this as a soft check: if the proposed plan's total TSS is outside the budget for Martin's current state, flag it and re-plan.
