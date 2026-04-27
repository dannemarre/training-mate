# Training science — Coggan PMC, TSS, ramp, interpretation

This is the canonical reference Claude cites when giving training-load advice. Code in `analysis/tss.py` and `tools/compute_pmc.py` implements these formulas; this doc explains *what* they mean and *when* the numbers cross threshold.

## TSS / NP / IF — Coggan formulas (canon)

**Power TSS** is the gold standard when a power meter is on the bike:

```
NP   = (mean(rolling_mean(power, 30s)**4))**0.25
IF   = NP / FTP
TSS  = duration_h * IF**2 * 100
kJ   = sum(power) / 1000  (when power is per-second)
```

A 1-hour ride at FTP exactly = 100 TSS. The IF² in the formula means TSS scales non-linearly with intensity — doubling IF quadruples TSS.

Sources: [TrainingPeaks — Performance Manager science article](https://www.trainingpeaks.com/learn/articles/the-science-of-the-performance-manager/), [Coggan/Allen formulas (Medium)](https://medium.com/critical-powers/formulas-from-training-and-racing-with-a-power-meter-2a295c661b46).

### NP edge cases — two-tier confidence flag

NP needs the 30-s rolling window to be a small fraction of total ride time. Practitioner consensus:

| Ride duration | Flag | Recommendation |
|---|---|---|
| < 10 min | `np_unreliable=true` in `analysis/tss.py` | Don't report NP/TSS-from-power. Fall back to hrTSS. |
| 10–20 min | `np_low_confidence=true` | Report TSS but warn "short ride, NP estimate is rough." |
| ≥ 20 min | (no flag) | Trustworthy. |

Source: TrainingPeaks coach training (10 min floor) tightened to 20 min by practitioner sources for safer use.

## hrTSS (TRIMP-based) — when no power

Uses heart-rate reserve scaled by Banister's exponential weighting:

```
hrr_i  = (hr_i - rhr) / (max_hr - rhr)
trimp  = sum(dt * hrr_i * 0.64 * exp(1.92 * hrr_i))
hrTSS  = trimp / trimp_at_threshold_for_1h * 100
```

Where `trimp_at_threshold_for_1h` is the TRIMP value for one hour spent at LTHR (computed once per athlete from `athlete_profile.lthr`, `max_hr`, `rhr`).

Fallback when only avg HR is known (e.g. summary-only Strava activity):

```
hrTSS = duration_h * (avg_hr / lthr)**2 * 100
```

This is rougher and should set `tss_kind='hr'` so downstream code knows.

## rTSS — running

Use Minetti grade-adjusted pace (NGS — normalized graded speed):

```
IF    = NGS / threshold_pace
rTSS  = duration_h * IF**2 * 100
```

Threshold pace is from `athlete_profile.run_threshold_pace_s_per_km`.

## PMC — Banister exponential model

Daily roll-up of TSS into three numbers:

```
CTL[d] = CTL[d-1] + (daily_tss[d] - CTL[d-1]) / 42      # 42-day τ — fitness
ATL[d] = ATL[d-1] + (daily_tss[d] - ATL[d-1]) / 7       #  7-day τ — fatigue
TSB[d] = CTL[d-1] - ATL[d-1]                            #          form
```

**Rules of the road in `tools/compute_pmc.py`:**
- Backfill 6 months on first run (`days=180`).
- Recompute the **last 14 days** on every subsequent run, in case activities arrived late or got edited.
- Days with no activity get `daily_tss=0` and still update CTL/ATL (decay).

Sources: [TrainingPeaks PMC article](https://www.trainingpeaks.com/learn/articles/the-science-of-the-performance-manager/), [Joe Friel — TSB So What?](https://joefrieltraining.com/part-3-training-stress-balanceso-what/).

## TSB interpretation thresholds

What today's TSB number means for what the agent should advise:

| TSB band | Label | What it means | What to advise |
|---|---|---|---|
| > +25 | Detrained / over-tapered | Fitness slipping if held >2 weeks | Resume normal load; ramp gently |
| **+5 to +20** | **Race-ready** | Fresh enough to race | A-races land here; +10 to +20 is the sweet spot |
| -10 to +10 | Neutral | Not particularly fresh, not particularly tired | Normal training |
| **-10 to -30** | **Productive overload** | Healthy build territory | Where weeks of consistent training live |
| < -30 | Functional overreach | Tolerable short-term, raises breakdown risk | Plan a recovery block within a few days |
| < -40 | Risk territory | Sustained only by very high-CTL athletes | Recovery week now |

**Project default for Martin:**
- "Race-ready" band: +10 to +20 for A-races.
- "Back off" trigger: TSB < -25 sustained ≥4 days → swap planned hard sessions for Z2 or recovery.

Sources span +5..+25 across TrainingPeaks / Friel / Coggan; we picked +10..+20 as the practical mid-point.

## Ramp rate — overreach detection

Coggan's rule of thumb: ramp >+5–7 TSS/d/wk for four-plus weeks is "often a recipe for disaster." Friel: 5–8 points per week.

**Project rules in `tools/current_form.py`:**

```
ramp_7d = CTL[today] - CTL[today - 7]
```

| ramp_7d | State | Action |
|---|---|---|
| ≤ +5 | Comfortable | None |
| +5 to +8 | Building | None — this is the sustainable build zone |
| +8 to +10 | **Warning** | Output `ramp_warning=true`. Plan should not increase load further this week. |
| > +10 sustained ≥7 d | **Crash territory** | Mandatory recovery week. Output `ramp_critical=true`. |

Sources: [Joe Friel — CTL Ramp Rate](https://joefrieltraining.com/the-ctl-ramp-rate/).

## Form-state buckets (the canonical mapping)

Used by `tools/current_form.py` and the `coach` subagent:

```python
def form_state(tsb: float, ramp_7d: float) -> str:
    if ramp_7d > 10: return "crashing"      # mandatory recovery
    if tsb < -40:    return "risky"
    if tsb < -30:    return "overreached"
    if tsb < -10:    return "productive"    # build territory
    if tsb < +5:     return "neutral"
    if tsb <= +20:   return "race-ready"
    return "detrained"
```

The `coach` subagent uses this to gate session selection. E.g. if `state == "overreached"`, no Z4+ work without a stated reason.

## What "session counts" — group rides and TSS

Group rides (Ängby söndag, Onsdagsgrus, etc.) are messy: bursts of Z5, long Z2 stretches, drafting confusion. Two valid accounting methods exist; we use both for different purposes:

- **Time-in-zone** (Coggan-influenced, our default for individual ride TSS) — literal seconds in each power zone. This is what `analysis/tss.py` produces from streams. Honest about total stress.
- **Session-classification** (Seiler) — if ≥75% of ride time was Z1/Z2 by power, classify the whole session as Z1 for the weekly distribution ledger. Used by `tools/weekly_review.py` for the 80/20 polarized check.

Both numbers can disagree for the same ride. That's fine — they answer different questions. Document the disagreement when it surfaces.

See `docs/training-distribution.md` for the polarized vs pyramidal layer.

## Practical defaults for the agent

When generating a weekly plan, the `coach` subagent:

1. Reads current CTL/ATL/TSB and `ramp_7d` from `tools/current_form.py`.
2. Maps to a `form_state` (above).
3. Chooses the week's intensity budget:
   - `race-ready` → race or peak-week intensity OK
   - `productive` → standard build (1 Z5, 1 Z4, 2-3 Z2, 1 Z3 SST, rest)
   - `overreached` → recovery-leaning (no Z5, ≤1 Z4, mostly Z2)
   - `crashing` / `risky` → recovery week, no Z4+ at all
4. Always cites this doc when explaining the call. Example: "TSB at -32 puts us in functional-overreach territory per `docs/training-science.md#tsb-interpretation-thresholds` — swapping Tuesday's threshold for Z2."

## What's *not* in this doc

- **Power/HR zone definitions** → `docs/zones.md`.
- **Workout structure (SST, VO2, etc.)** → `docs/workout-library.md`.
- **80/20 distribution** → `docs/training-distribution.md`.
- **HRV/wellness gating** → `docs/wellness.md`.
- **Fueling math** → `docs/fueling.md`.
- **KOM/wind math** → `docs/wind-and-kom.md`.
