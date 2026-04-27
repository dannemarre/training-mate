---
description: Propose Martin's weekly training plan, write journal/YYYY-WW-plan.md, offer Google Calendar diff. Delegates to the coach subagent for the actual reasoning.
---

# /plan-week

Plan Martin's next training week. Heavy lifting is done by the `coach` subagent — this skill drives the workflow.

## Steps

1. **Refresh data** if anything's recent:
   ```
   uv run python tools/sync_activities.py --since "$(date -u -v-7d +%Y-%m-%d)" --include-wellness
   uv run python tools/compute_pmc.py
   ```

2. **Pick the week** — default is next Monday (Europe/Stockholm). If Martin specifies a different start, honour it. Validate it's a Monday.

3. **Ask Martin once, up front**:
   - Knee score today (0-10)?
   - Any travel / commitments outside Calendar?
   - Race in the next 8 weeks? (If yes, `coach` may shift to polarized.)

4. **Delegate to the `coach` subagent** with the week-start and Martin's answers. The subagent will:
   - Read state (current_form, list_activities, daily_briefing).
   - Read docs (training-science, zones, workout-library, training-distribution, wellness, knee-rehab, group-rides).
   - Run `tools/plan_week.py --week-start YYYY-MM-DD --no-write` to get a proposal.
   - Apply form-state and wellness/knee gates.
   - Return a 3-part response: state summary, plan table, decision points.

5. **Iterate with Martin** on any decision points (session swaps, intensity choices, race calendar). Once he's satisfied, the subagent runs `plan_week.py` *without* `--no-write` to produce `journal/YYYY-WW-plan.md`.

6. **Calendar diff** (only if Martin opts in):
   ```
   uv run python tools/calendar_list.py --from <Monday> --to <next Monday>
   ```
   Show Martin a diff of: existing calendar events ⇆ proposed sessions. **Do NOT auto-apply.** Wait for explicit "yes". Calendar upsert tool isn't built yet — for now, after Martin says yes, use the `google-calendar` MCP server's create-event / update-event / delete-event tools per the diff. Update the journal's "Calendar" section with a timestamp.

## Constraints

- Never silently overwrite an existing `journal/YYYY-WW-plan.md`. The tool already appends `-revB` automatically.
- Never write to Google Calendar without showing the diff first (CLAUDE.md rule #5).
- Always cite docs for non-obvious calls (CLAUDE.md rule #1).
- Always include ≥2 knee rehab sessions (CLAUDE.md rule #2).
- Sunday anchored on Ängby söndag unless Martin says otherwise (CLAUDE.md rule #3).
