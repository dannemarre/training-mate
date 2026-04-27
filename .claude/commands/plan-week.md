---
description: Propose next week's training plan, write journal/YYYY-WW-plan.md, offer Google Calendar diff.
---

# /plan-week

Propose the next 7-day training plan for Martin, write it as a markdown file under `journal/`, and (if requested) prepare a Google Calendar diff to upsert.

## Steps

1. **Read context.** Always load:
   - `CLAUDE.md` — athlete profile + rules.
   - `docs/group-rides.md` — fixed Stockholm commitments.
   - `docs/training-science.md` — TSS/PMC math + ramp limits (when it lands).
   - `docs/workout-library.md` — session menu (when it lands).
   - `docs/knee-rehab.md` — rehab pool + weekly templates.
   - The most recent `journal/*-plan.md` and `journal/*-log.md` so you don't repeat last week's pattern blindly.

2. **Read state.** Run, in parallel:
   - `uv run python tools/current_form.py` — CTL/ATL/TSB. (When this lands; for now, ask Martin or skip with a flag.)
   - `uv run python tools/list_activities.py --since 14d` — recent load. (When this lands.)
   - Ask Martin: knee status (0-10), planned travel, any commitments not on the calendar yet.

3. **Pick the ISO week.** Default = next week (Monday after today). Use `date '+%G-%V'` for the filename `journal/YYYY-WW-plan.md`. If Martin specifies a different start, honor it.

4. **Draft the plan.** Use `journal/_template-plan.md` as the structure. Specifically:
   - Anchor on Sunday Ängby söndag 07:30 unless Martin says otherwise.
   - Slot one mid-week intensity (Tue or Thu) per `docs/group-rides.md`.
   - Onsdagsgrus is endurance unless legs say no.
   - Knee rehab on Mon + Fri at minimum (gym at work).
   - Respect TSB: don't ramp >+5 CTL/week without a stated reason. >+8 = warn.
   - Flag any session that historically aggravates the knee.

5. **Write the file.** Use Write to create `journal/YYYY-WW-plan.md` from the template, filling the table. Include CTL/ATL/TSB, the goal of the week, and any open questions.

6. **Offer the calendar diff.** Ask Martin: "Apply to Google Calendar `Training`?" If yes:
   - Use the `google-calendar` MCP server's `list-events` tool to read existing events on that calendar in the Mon-Sun window.
   - Compare against the planned sessions; show a diff (add / update / delete / unchanged).
   - **Do not write anything yet.** Wait for Martin's explicit approval.
   - On approval, use `create-event` / `update-event` / `delete-event` per the diff. Surface every change in the response.
   - Update the plan file's "Calendar" section with the timestamp.

7. **Don't push to Garmin.** Out of scope for this command. Workout file export (`.zwo`) is a separate explicit step.

## Constraints

- Never silently overwrite an existing `journal/YYYY-WW-plan.md`. If it exists, ask: replace, append, or open a `-revB.md` variant.
- Never write to Google Calendar without showing the diff first.
- Cite the doc you used for any non-obvious decision (e.g. "skipping Wed because Tue ride pushed CTL +6, per `docs/training-science.md` ramp limit").
