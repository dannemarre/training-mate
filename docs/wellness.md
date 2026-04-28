# Wellness — HRV, sleep, readiness, body battery

How Garmin wellness signals feed into Claude's daily prescribe-or-back-off decisions. Schema in `wellness_daily` (see `docs/schema.md`). Sync via `tools/sync_activities.py --include-wellness`.

## Reliability ranking — what to trust

For *daily* prescribe-or-back-off decisions, in order:

1. **HRV Status (overnight rMSSD)** — most reliable when available. PPG-derived rMSSD is validated as a substitute for ECG-derived rMSSD in healthy adults at rest.
2. **Training Readiness** — useful sanity-check, but a Garmin black box. Don't gate decisions on it alone.
3. **Body Battery** — trend-only. No published accuracy spec. Use it to *confirm* a primary signal, never override.
4. **Sleep Score** — algorithmic. Use **sleep duration** directly (well-measured) rather than the score.

### When HRV-Status isn't available

Older Garmin watches don't track overnight HRV. `tools/sync_activities.py --include-wellness` will still call the endpoint (so it starts populating once the watch supports it) but the rows will have `hrv_ms=NULL`. **Fallback signal stack** (used by `tools/daily_briefing.py`):

1. **Sleep duration** — `sleep_minutes` from `wellness_daily`. Already at the top of the gating ladder if HRV is absent.
2. **RHR drift** — `resting_hr` vs 14-day rolling mean (>+5 bpm = soft flag).
3. **Daily stress** — Garmin's `averageStressLevel` (`stress_avg`) and qualifier (`stress_qualifier` ∈ CALM / BALANCED / STRESSFUL / VERY_STRESSFUL). Sustained "STRESSFUL" days are the autonomic-state signal we have when HRV is unavailable.
4. **Body Battery trend** — confirmation only.

The combined call is still conservative: any two of (sleep <6 h, RHR >+5 bpm, stress qualifier ≥ STRESSFUL for ≥2 days) → swap planned hard for Z2.

Sources: [Plews & Buchheit foundational paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3936188/), [Marco Altini — HRV history](https://marcoaltini.substack.com/p/a-brief-history-of-heart-rate-variability), [Scientific Reports 2025 cyclists trial](https://www.nature.com/articles/s41598-025-13540-z).

## The HRV gating rule

**Rolling baseline + smallest worthwhile change**, NOT single-day reactivity.

```
baseline_7d   = mean(rmssd over last 7 days)
swc           = 0.5 × stdev(rmssd over last 7 days)
breach[d]     = rmssd[d] < (baseline_7d − swc)
```

Action table:

| Pattern | Recommendation |
|---|---|
| One day in breach | **Noise. Don't act.** |
| 2 consecutive breaches | Swap planned hard session for Z2. Keep total volume. |
| 3 consecutive breaches | Swap for full Z1/Z2 only. Skip strength session if scheduled. |
| ≥4 consecutive breaches | Recovery + replan the week. Surface to Martin. |

This is the canonical Plews/Buchheit rule. Reject WHOOP/Oura-style "HRV down 10% today → easy day" — single-day rMSSD is too noisy.

The 2025 Scientific Reports trial on cyclists with HRV-guided training showed +5% peak power, +14% power@VT2, +7% 40-min TT power vs traditional periodization. Strongest evidence to date for HRV-gating.

## Implementation in `tools/daily_briefing.py`

```python
def hrv_state(rmssd_today, rmssd_history_7d):
    if not rmssd_history_7d:
        return {"state": "no_baseline", "breach_days": 0}
    baseline = mean(rmssd_history_7d)
    swc = 0.5 * stdev(rmssd_history_7d)
    breaches = consecutive_breaches(rmssd_history_7d, baseline - swc)
    if rmssd_today < baseline - swc:
        breaches += 1
    if breaches >= 4: return {"state": "recovery_required", "breach_days": breaches}
    if breaches == 3: return {"state": "easy_only", "breach_days": breaches}
    if breaches == 2: return {"state": "swap_hard_for_z2", "breach_days": breaches}
    return {"state": "normal", "breach_days": breaches}
```

`tools/daily_briefing.py` outputs the state, and `/today` translates it to advice.

## What about body battery + readiness?

Use them in this order:

- **Confirmation** — if HRV is "normal" but body battery dropped >30 points overnight, surface as a soft yellow flag, not a red one.
- **Soft tiebreakers** — Training Readiness <30 with normal HRV and good sleep → maybe scale duration not intensity.
- **Never sole driver** — never recommend rest-vs-train based on Body Battery alone.

## Sleep duration thresholds

Use sleep duration (minutes), not Garmin's "sleep score":

| Last night | Action |
|---|---|
| ≥7 h | No flag |
| 6–7 h | Soft note: "consider scaling intensity" |
| 5–6 h | Drop Z4+ today |
| <5 h | Recovery only, no Z3+ |

If two consecutive nights <6 h: same as 3-breach HRV — easy only.

## Resting HR drift

If today's RHR is >5 bpm above the 14-day rolling mean, that's a sympathetic-nervous-system stress signal (illness, overreaching, dehydration). Soft flag. Reinforces an HRV-based call but isn't a primary signal.

```python
rhr_drift = rhr_today - mean(rhr last 14 days)
if rhr_drift > 5:
    flag("rhr_elevated")
```

## Cross-checks against training load

If `current_form.tsb < -25` AND HRV in breach for ≥2 days → **double signal, mandatory recovery day**. Don't second-guess.

If `current_form.tsb > +15` (race-ready) AND any HRV breach → still go easy but flag that the breach might be travel/illness, not training fatigue.

## What goes in `wellness_daily`

```sql
date            (local YYYY-MM-DD, PK)
hrv_ms          (overnight rMSSD)
body_battery    (Garmin's 0-100)
readiness       (Training Readiness 0-100)
sleep_score     (Garmin's 0-100 — kept for reference but not used for gating)
sleep_minutes   (the measured number — used for gating)
resting_hr      (overnight RHR)
raw             (json blob for debugging)
```

Sync via `tools/sync_activities.py --include-wellness --since YYYY-MM-DD`. The flag exists so daily-briefing-only runs don't pull all activity streams (cheaper).

## What's not in this doc

- Schema details → `docs/schema.md`.
- Daily briefing flow → `.claude/commands/today.md` (skill).
- Form state interpretation → `docs/training-science.md`.
- Knee score tracking → `docs/knee-rehab.md` (separate signal, journaled not synced).
