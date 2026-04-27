---
description: Martin's morning coaching briefing — readiness, form, today's session, knee status, group rides. Use when Martin asks for the daily plan, "what's today?", "what should I do?", or "how am I doing?".
---

# /today

Compose Martin's daily briefing in 4–6 short bullets. Always cite the relevant doc when explaining a call.

## Steps

1. **(Optional) refresh PMC** if recent activities haven't been folded in yet:
   ```
   uv run python tools/compute_pmc.py
   ```

2. **Run the briefing aggregator:**
   ```
   uv run python tools/daily_briefing.py
   ```

   Parse the JSON. The agent's job is to translate it into prose, not to dump fields.

3. **Output format** — 4–6 bullets in this order:

   **Readiness.** TSB band + form_state. Cite `docs/training-science.md#tsb-interpretation-thresholds`. Quote the number. If `ramp_warning` or `ramp_critical` is true, lead with that.

   **Wellness gates.** If `wellness.hrv.state` is anything other than `normal`/`no_baseline`, surface it (cite `docs/wellness.md#the-hrv-gating-rule`). Same for sleep `no_z4_plus` / `easy_only` / `recovery_only`. RHR drift is a soft note.

   **Today's session.** From `today_session.row` if present (tomorrow's plan-row from `journal/YYYY-WW-plan.md`). Combine with form + wellness gates: does the plan still fit? If form is overreached/risky and the plan is Z4+, recommend a swap with one specific alternative drawn from `docs/workout-library.md`.

   **Knee.** Quote `knee_alert` (green/yellow/red) and the most recent journal snippet if any. If yellow/red, name a specific aggravator to avoid (per `docs/knee-rehab.md`). Always remind cadence ≥80 rpm under load.

   **Group rides today.** From `group_rides`. Sunday Ängby söndag is the anchor; Wednesday Onsdagsgrus is the gravel option. Don't redesign Martin's social schedule (CLAUDE.md rule #3) — note them and move on.

   **One concrete recommendation.** Single sentence. Don't hedge. Example: *"Go SST 3×12' @ 90% FTP today. Eat 60 g carbs in the warmup, 750 ml/h on the bike. Optional 15-min knee rehab block (TKE + clamshells) before bed."*

4. **If the briefing has gaps** (e.g. `form` is null because PMC empty, or `wellness.hrv.state == "no_baseline"`):
   - Surface the gap as a one-liner at the bottom.
   - Suggest the fix: `compute_pmc.py --backfill` or `sync_activities.py --include-wellness --since 30d`.
   - Don't try to coach without those data points — say so.

## Constraints

- Never prescribe a workout that conflicts with `wellness.hrv.state` or knee yellow/red. The gates exist for a reason.
- Always cite a doc per CLAUDE.md operating rule #1.
- Tone: honest, specific, grounded. No "you're crushing it" — Martin is hiring you for honest read-outs.
- If `knee_alert == "red"`, recommend pure rehab + Z1/Z2; do NOT propose any Z3+ session even if the plan said so.
