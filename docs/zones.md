# Power & HR zones, FTP test protocols

Source of truth for zone arithmetic. `tools/current_form.py`, `tools/generate_workout.py` and the `coach` subagent compute zones from `athlete_profile.ftp_w` and `athlete_profile.lthr`.

## Coggan 7-zone power model (canonical)

| Zone | Name | % FTP | Typical session | RPE |
|---|---|---|---|---|
| Z1 | Active recovery | < 55% | < 60 min easy spin, post-hard-day | 1-2/10 |
| Z2 | Endurance | 56–75% | 60–240 min steady, the daily-dose | 2-3/10 |
| Z3 | Tempo | 76–90% | 30–90 min at a pace you can sustain but feel | 3-5/10 |
| Z4 | Threshold (LT2) | 91–105% | 2×20', 3×15', 4×10' intervals | 6-7/10 |
| Z5 | VO2max | 106–120% | 5×4', 4×4' Norwegian, 30/15s | 8-9/10 |
| Z6 | Anaerobic | 121–150% | 30s–2min sprints | 9-10/10 |
| Z7 | Neuromuscular | max sprint | 5–15s peak power | max |

**Sweet spot** straddles Z3 high → Z4 low: **88–94% FTP**. Treat as its own band — `analysis/tss.py` uses the standard 7-zone breakdown but `docs/workout-library.md` calls it out explicitly because it's the highest-yield-per-fatigue intensity.

Source: [Roadmancycling — Coggan 7-zone (2026)](https://roadmancycling.com/blog/ftp-training-zones-cycling-complete-guide).

## HR zones (Friel-style, LTHR-anchored)

For activities without power, or as a sanity check:

| Zone | % LTHR | Notes |
|---|---|---|
| Z1 | < 81% | Recovery |
| Z2 | 81–89% | Endurance |
| Z3 | 90–93% | Tempo |
| Z4 | 94–99% | Sub-threshold |
| Z4u | 100–102% | Threshold (LTHR ± a hair) |
| Z5a | 103–105% | VO2 onset |
| Z5b | 106–108% | VO2 |
| Z5c | > 108% | Max |

HR lags power by 30-90 seconds and drifts with heat / fatigue. Don't gate single-interval feedback on HR alone if power is available. Use HR for *aerobic* intervals (Z2/Z3/Z4) and power for *anaerobic* (Z5+).

## FTP — what it is, when to update

FTP = Functional Threshold Power = the power output you could sustain for 1 hour at maximal sustainable effort. The number anchors every zone, every TSS calculation, and every workout prescription.

**Updates:** FTP changes through the year. Update via:
- A formal test (below) — most reliable
- An "all-out" 20-min effort in a race or hard group ride, applying the standard 0.95 multiplier
- Critical-power model from sustained efforts of varying durations (less common; needs a power-curve tool)

`tools/estimate_ftp.py` proposes; the human commits via `--commit`. Updates land in `ftp_history` with `effective_date`. PMC computations use the FTP active on each ride's date, not the current FTP.

## FTP test protocols

### 20-minute test (the standard)

1. Warm up: 15 min Z2 + 3×1 min @ ≥110% (rest 1 min between) + 5 min Z2.
2. Effort: **20 min all-out, even pacing.** Heart rate climbs steadily; you should be regretting it by minute 12.
3. Cool down: 10 min Z1.
4. **FTP = 0.95 × average power of the 20-min effort.**

Best done indoors on a trainer for clean data. Outdoor is fine on a long flat stretch with no traffic interruptions.

### Ramp test (Zwift / TrainerRoad style)

1. Warm up: 5 min ramp from 100W to ~100W below test start.
2. Test: power steps up by ~25W every minute (or as defined by the platform). Continue until you can no longer hold cadence.
3. **FTP = 0.75 × peak 1-min power achieved.**

Quicker (~25 min total) and less mentally taxing. Slightly conservative vs 20-min for endurance-trained riders; bumps higher for explosive riders.

### Critical-power model (advanced)

Best-effort durations of 3, 5, 12, 20 min over 2-3 weeks → fit a 2-parameter (CP, W') model. `tools/estimate_ftp.py` may support this with `--method critical-power` once enough data exists.

## Default test cadence

- **Pre-season** (Jan / Feb) — establish base FTP after off-season.
- **Mid-season** (May / Jun) — confirm or bump after spring build.
- **Pre-A-race** (4–6 weeks out) — refine for race-day power targets.

Don't test if HRV is below baseline or knee score ≥3/10 — invalid result and risk of aggravation.

## Working without an FTP

When `athlete_profile.ftp_w` is NULL, `tools/generate_workout.py` and `current_form.py` should error rather than guess. The agent's correct response is "I don't know your FTP yet — let's run a 20-min test, or estimate from a recent hard ride."

`tools/estimate_ftp.py --method 20min --from-recent` looks for any 20+ min effort in the last 90 days where average power is suspiciously high relative to the current FTP guess; it proposes an updated FTP for the human to commit.

## What HR / power looks like for Martin specifically

Martin's actual `ftp_w`, `lthr`, `max_hr`, and `rhr` live in `athlete_profile`. They are blank until he confirms (see `CLAUDE.md` athlete profile section). Until then, every workout the agent prescribes carries an explicit "I'm using FTP=N as a placeholder, please confirm" caveat.
