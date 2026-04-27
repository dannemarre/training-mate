# Training-Mate — Buildout plan

This is the detailed execution plan from "auth-complete" (where we are 2026-04-27) to "Martin uses it as a coach". `PLAN.md` has the high-level milestones M2–M8; this file specifies *how*. Edit as decisions land.

## Why this doc

The agent (Claude Code) is the coach. It needs four well-developed surfaces to operate at its best:
1. **Rules** in `CLAUDE.md` — the constitution that survives compaction.
2. **Knowledge** in `docs/*.md` — Coggan / Friel / Plews / Barton training science it cites when advising.
3. **Workflows** in `.claude/commands/*.md` (skills) — repeatable procedures (`/today`, `/plan-week`, `/review`).
4. **Specialists** in `.claude/agents/*.md` (subagents) — when Claude delegates planning, reviewing, KOM-hunting.

Plus the data layer (`tools/*.py` + SQLite cache) that makes coaching grounded in Martin's actual rides.

The build sequence below interleaves all five so each session ships something the agent can use.

## Architecture recap

```
Claude Code (the coach)
  │
  ├── CLAUDE.md                        operating rules + athlete profile + index
  ├── docs/*.md                        training science, fueling, zones, knee, …
  ├── .claude/commands/*.md            slash commands / skills (workflows)
  ├── .claude/agents/*.md              subagents (coach, kom-hunter, …)
  │
  ├── tools/*.py                       JSON-emitting CLI scripts via Bash
  │     └── data/training-mate.sqlite  shared cache
  │
  └── 2 MCP servers in .mcp.json autostart (ad-hoc only):
        Strava   @r-huijts/strava-mcp-server
        Calendar @cocal/google-calendar-mcp
      + Garmin MCP installed but not autostarted (manual `npx` for ad-hoc)
```

Locked decisions (don't redesign): Claude IS the coach (no custom MCP server / UI), tools-as-CLI primary, MCP secondary, single-device, single-athlete. Direnv for env propagation. python-garminconnect ≥ 0.3.3 (post-garth).

---

## Sequencing overview

Each phase ≈ one Claude Code session (1–2 h). Sessions are gated; don't move on until the previous gate is met.

| Phase | Sessions | Outcome (one sentence) |
|---|---|---|
| 0 — Knowledge baseline | 1 | Claude has authoritative training-science docs to cite. |
| 1 — M2: Ingest + TSS | 1–2 | "Show me my last 4 weeks of TSS" works against the local cache. |
| 2 — M3: PMC + form | 1 | "What's my CTL/ATL/TSB?" works; ramp warning fires at >+8/wk. |
| 3 — M4: Wellness + daily surface | 1 | `/today` returns a real morning briefing with HRV-gated advice. |
| 4 — M5: Planner + Calendar + first subagent | 2 | `/plan-week` writes `journal/YYYY-WW-plan.md` + diffs into Google Calendar. |
| 5 — M6: KOM + wind | 1 | `/kom` ranks today's segments by wind/form. |
| 6 — M7: Routes + nutrition + briefing polish | 1 | `/brief` fuses ride + weather + fuel for tomorrow's session. |
| 7 — M8: Weekly review + polish | 1 | `/review` finalises `journal/YYYY-WW-log.md` with honest retrospective. |

Total: 9–10 focused sessions to "Martin uses it as a coach end-to-end".

---

## Phase 0 — Knowledge baseline

**Goal.** Before generating data, give the agent the reference material it cites. Skipping this means Claude advises from intuition — exactly what `CLAUDE.md` rule #1 forbids.

**Done when** every doc listed below has at least its v0 content; `tools/auth_status.py` doesn't change; the agent can answer "what's the TSB threshold for race-ready?" with a citation.

### Docs to write (research-backed; all citations from this session's research agents)

| File | Content | Source pointers |
|---|---|---|
| `docs/training-science.md` | Coggan TSS/IF/NP formulas (already in PLAN.md), PMC math (CTL τ=42, ATL τ=7, TSB=CTL−ATL), interpretation thresholds (TSB >+25 detrained, +5..+20 race-ready, -10..-30 productive overload, <-30 functional overreach, <-40 risky), ramp ceiling (+8 CTL/wk; >+10 for 7d = "crash territory"), NP edge cases (two-tier flag: <10min unreliable, 10–20min low-confidence, ≥20min reliable). | TrainingPeaks Performance Manager article, Joe Friel CTL Ramp Rate, Coggan/Allen formulas |
| `docs/zones.md` | Coggan 7-zone (Z1 <55%, Z2 56–75%, Z3 76–90%, Z4 91–105%, Z5 106–120%, Z6 121–150%, Z7 max), HR zones (LTHR-anchored), FTP test protocols (20-min, ramp test), how to update FTP in `data/training-mate.sqlite` `ftp_history` table. | Roadmancycling 2026 zones guide, TrainingPeaks |
| `docs/workout-library.md` | One section per workout type with: target zone, sample sets, work:rest, when-to-prescribe, when-to-skip (knee + HRV gates), example `.zwo` skeleton, TSS estimate. Types: Endurance Z2, Recovery Z1, SST 88–94%, Threshold 95–105%, VO2max 106–120% (incl. Norwegian 4×4), Anaerobic, Race/Event. | TrainerRoad SST guide, FasCat VO2, TrainingPeaks workouts-to-raise-FTP |
| `docs/training-distribution.md` | Polarized vs pyramidal, Seiler 80/20 (session-based, not time-in-zone), recommendation for Martin: pyramidal in build, polarized 6–8 wks pre-A-race. Document the **Seiler-session-based count** as the project default for weekly distribution + **time-in-zone** for stress accounting. Note disagreement between schools. | Frontiers 2025 TID review, FastTalk Labs Seiler pathway |
| `docs/wellness.md` | HRV Status (overnight rMSSD), Body Battery, Training Readiness, Sleep — what's reliable. Multi-day baseline + SWC (0.5×SD of 7-day mean) gating rule: if today's rMSSD < baseline−SWC for ≥2 consecutive days → swap hard for Z2; ≥4 days → recovery + replan. Reject single-day reactivity. | Plews & Buchheit foundational paper, Marco Altini, Scientific Reports 2025 |
| `docs/fueling.md` | Carbs/h = clamp(60+30·IF, 60, 120), pre/post tables, fluids, sodium, hot-day adjustments. (Math already in PLAN.md — write the prose + tables here.) | TrainingPeaks fueling, ACSM guidelines |
| `docs/wind-and-kom.md` | Wind/yaw math (already in PLAN.md), polyline sampling, threat threshold (`P_user(T_kom) ≥ 0.97·kom_avg_w` AND `tail_kmh > 4`), Open-Meteo endpoint reference. | Existing PLAN.md content + Open-Meteo docs |
| `docs/schema.md` | SQLite schema reference (already in `_common.py`), example queries for: "rides last 14 days", "TSS by week", "wellness joined to activities". | Read directly from `_common.py` MIGRATIONS |
| `docs/tools.md` | Tool catalog: name, args, JSON output schema, example invocation. **Every new tool must land here in the same commit** (already a CLAUDE.md rule). Stub for now. | — |

### Knee rehab doc updates (not a new doc, an extension)

`docs/knee-rehab.md` is provisional. Add (from Barton et al. 2024 + JOSPT 2025):
- **Bike-fit causes** as a new section: saddle height (knee 25–35° at bottom), saddle fore-aft (knee over pedal axle), cleat fore-aft (ball of foot over axle), float ≥4.5°, crank length vs femur. *"If knee pain recurs despite rehab progression, before adjusting training: get a professional bike fit."*
- **Cycling-specific movement flags** (additions to existing list): low cadence (<70 rpm) under load on climbs, cold-start hard efforts (<10 min Z1/Z2 minimum), single-leg eccentric loading on cleats.
- **Recovery-timeline expectations**: PFP often 6–12 weeks of consistent rehab; ~40% still symptomatic at 1 year without comprehensive intervention. Flag in journal if no progression at 8 weeks → physio.
- **Evidence note**: hip-targeted + knee-targeted exercise outperforms either alone (Barton 2024). Already implicit in our pool — make it explicit.

### CLAUDE.md updates (operating rules pass)

Tighten / canonicalise the operating rules. Use these eight (revising the current set):

1. **Always cite a doc when giving training advice.** "Per `docs/training-science.md`, ramp >+8 CTL/wk is overreach territory."
2. **Knee first.** Every weekly plan has ≥2 rehab sessions. Warn before high-risk sessions (long descents, low-cadence climbs, cold-start hard, big out-of-saddle on early climbs). See `docs/knee-rehab.md`.
3. **Group rides are commitments, not flexible slots.** Sunday Ängby söndag is the anchor — plan the week around it.
4. **Never push to Garmin without explicit confirmation.** `TM_GARMIN_DRYRUN=true` default. Show the workout file format first.
5. **Never write to Google Calendar without preview + confirmation.** Bulk operations diff first.
6. **Don't re-pull data we already have.** Check the SQLite cache first; streams especially.
7. **Strava 200/15min, 2000/day.** Heavy syncs throttle via `tools/sync_activities.py`.
8. **When uncertain, ask** — especially FTP changes, race-day fueling, knee-safe exercise selection.

(These mostly exist; the rewrite is to make them numbered, self-contained, and cite the supporting doc.)

### What NOT to do in Phase 0

- Don't build any `tools/*.py` beyond what already exists.
- Don't create subagents yet — `.claude/agents/` stays empty until Phase 4.
- Don't write `.claude/commands/today.md` etc. yet — without data tools they'd be empty shells.

---

## Phase 1 — M2: Ingest + TSS

**Goal.** Sync Strava + Garmin into the local SQLite cache; compute TSS / NP / IF for cycling and running activities; verify against a golden fixture.

**Done when** `uv run python tools/list_activities.py --last 30` returns Martin's last 30 days of activities with TSS populated, AND the golden test passes within ±2% of Golden Cheetah's reference TSS for a known FIT file.

### Tools to build

| Tool | Args | Output | Notes |
|---|---|---|---|
| `tools/sync_activities.py` | `--source {strava,garmin,both}`, `--since YYYY-MM-DD`, `--limit N` | JSON `{synced: N, skipped: M, errors: [...], rate_limit: {...}}` | stravalib for Strava, python-garminconnect for Garmin. Throttle Strava to ≤1 req/2s. Persist `X-RateLimit-Usage` to `rate_limit_log` table. Skip activities already in cache (UNIQUE on `(source, source_id)`). Streams compressed via `numpy.savez_compressed` → zstd if dep is available, else gzip. |
| `tools/list_activities.py` | `--last N` (days), `--sport {cycling,running,all}`, `--min-tss N` | JSON array of `{id, source, sport, start_local, duration_h, distance_km, tss, np, kj, …}` | Pure DB query. No API calls. |
| `tools/get_activity.py` | `--id N`, `--include-streams {power,hr,…}` | Full activity blob + decompressed streams | Streams as base64 numpy bytes when `--include-streams` set. |
| `tools/estimate_ftp.py` | `--method {20min,ramp,critical-power}` | `{ftp_w: int, source: str, basis: str, low_confidence: bool}` | Read recent activities; emit suggestion + write to `ftp_history` only on `--commit`. |

### Module: `analysis/`

New top-level package alongside `tools/`. The math lives here so the CLI tools stay thin.

- `analysis/tss.py` — `power_tss(streams, ftp) → {tss, np, if, kj, np_low_confidence, np_unreliable}` (two-tier flag at <10min and <20min per `docs/training-science.md`); `hr_tss(streams, lthr, max_hr, rhr) → {tss}`; `pace_tss(streams, threshold_pace) → {tss}`. Pure functions, no DB.
- `analysis/__init__.py` — re-exports.

### Tests

- `tests/test_tss_golden.py` — load a known FIT fixture (Golden Cheetah test fixtures via `fitparse`), compute power_tss, assert within ±2% of the reference TSS pre-computed in the fixture filename / sidecar.
- `tests/test_tss_synthetic.py` — constant 200W for 1h with FTP=200 → TSS=100, IF=1.0, NP=200.
- `tests/test_np_short_ride.py` — 5-min ride flags `np_unreliable=true`; 15-min ride flags `np_low_confidence=true`; 30-min ride flags neither.

### Docs to update

- `docs/tools.md` — add four new tool entries (args, output, examples).
- `docs/training-science.md` — backfill the actual code references (link to `analysis/tss.py:power_tss`).

### What we deliberately defer

- Activity-stream visualisation (no value pre-M5).
- FTP auto-update (manual via `--commit` for now).
- Multi-bike / multi-FTP support (assume single FTP that varies by date in `ftp_history`).

---

## Phase 2 — M3: PMC + form

**Goal.** Daily roll-up of TSS into CTL/ATL/TSB; expose form state and ramp warnings.

**Done when** `tools/current_form.py` returns Martin's current CTL/ATL/TSB, the ramp-warning logic fires correctly on a synthetic spike, and the `pmc_daily` table reconciles to within 0.1 CTL of a hand-computed reference for a 60-day window.

### Tools

| Tool | Output | Notes |
|---|---|---|
| `tools/compute_pmc.py` | `{computed_through: date, ctl: …, atl: …, tsb: …}` | Banister exp-weighted, recompute last 14 days on every run; full backfill 6 months on first run. Writes `pmc_daily` table. |
| `tools/current_form.py` | `{ctl, atl, tsb, form_state: 'race-ready'\|'fresh'\|'productive'\|'overreached'\|'risky', ramp_7d, ramp_warning: bool, citation: 'docs/training-science.md#tsb-thresholds'}` | Pure read of `pmc_daily`. Form-state buckets per the doc. |

### Tests

- 60 days of constant 50 TSS → CTL → 50, ATL → 50, TSB → 0 (asymptote check).
- Spike: 14 days at 80 TSS after 30 days at 40 TSS → ramp_warning fires when ramp_7d > +8.
- Boundary: TSB exactly +5, +20, -10, -30, -40 → correct `form_state` mapping.

### Docs to update

- `docs/training-science.md` — link to `tools/current_form.py` output schema; add "How to interpret your form state today" decision tree.

### Skill (first one with real data)

`.claude/commands/form.md`:
```
---
name: form
description: Show Martin's current training form (CTL/ATL/TSB) and what it means. Use when Martin asks about readiness, form, fitness, or fatigue.
allowed-tools: Bash(uv run python tools/current_form.py)
---

Run `uv run python tools/current_form.py`, parse the JSON, then explain:
- His current `form_state` and what's typical at this phase of the season
- The 7-day ramp and whether it's in safe territory (per docs/training-science.md)
- A concrete "today recommendation" hint (don't prescribe a session yet — that's /today's job in Phase 3)
```

---

## Phase 3 — M4: Wellness + daily surface

**Goal.** Pull Garmin wellness (HRV, sleep, RHR, body battery, readiness) into `wellness_daily`; build the first daily surface (`/today`).

**Done when** `/today` returns a real morning briefing that fuses form + wellness + planned session + knee status + group-ride context, and HRV-gated advice fires correctly on a manufactured 4-day rMSSD dip.

### Tools

| Tool | Output | Notes |
|---|---|---|
| `tools/sync_activities.py` (extended) | adds `wellness_synced: N` to JSON | Pulls overnight HRV (rMSSD + 7-day mean + SWC), sleep, RHR, body battery, training readiness, sleep score → `wellness_daily`. |
| `tools/daily_briefing.py` | `{date, form: {…}, wellness: {hrv_status, hrv_swc_breach_days, sleep_h, …}, today_session: {…}, knee_alert: 'green'\|'yellow'\|'red', group_rides_today: [...], recommendation: …}` | The aggregator. Reads `pmc_daily` + `wellness_daily` + `journal/YYYY-WW-plan.md` (if present) + `docs/group-rides.md`. |

### Skill: `/today`

`.claude/commands/today.md` (use the structure from research; key bits):
- description: "Martin's daily coaching briefing. Use when he asks for the plan, readiness, or what to do today."
- pre-approved: `Bash(uv run python tools/daily_briefing.py)` and `Read(/.../journal/**)`.
- body: orchestrate fetch → reason → output. Honest, specific, cites docs/training-science.md and docs/wellness.md.

### Skill: `/sync`

`.claude/commands/sync.md`:
- description: "Sync Strava + Garmin to local cache. Use after a ride, or daily."
- pre-approved: `Bash(uv run python tools/sync_activities.py *)`.
- body: run sync, summarise what landed, flag any rate-limit pressure.

### Skill: `/log`

`.claude/commands/log.md` (already a stub; flesh it out):
- Append today's note to `journal/YYYY-WW-log.md` under standard headings (Done / Notes / Knee / Sleep / Form).
- If knee score ≥4/10 was reported, alert in the entry that the next planned hard session might need swapping.

### Docs to update

- `docs/wellness.md` — concrete `wellness_daily` schema mapping; example queries.
- `docs/tools.md` — add `daily_briefing.py` row.

### What we deliberately defer

- Subagent for daily briefing — `/today` calling Bash directly is enough; only delegate when `/today` repeatedly demands multi-step research.

---

## Phase 4 — M5: Planner + workouts + Calendar + first subagent

**Goal.** `/plan-week` produces a real weekly plan grounded in form + wellness + knee + group rides + race calendar; writes to `journal/YYYY-WW-plan.md`; offers a Google Calendar diff.

**Done when** Martin runs `/plan-week`, gets a 7-day proposal he'd actually follow, the journal file is written, and a calendar preview is shown for confirmation.

### Tools

| Tool | Output | Notes |
|---|---|---|
| `tools/generate_workout.py` | `{workout: {kind, duration_min, target_tss, structure: [...]}}` | Pure function: kind + target TSS + form state → interval structure from `docs/workout-library.md`. No I/O. |
| `tools/export_workout.py` | `{paths: {zwo, fit?}, calendar_description}` | Write `.zwo` always (Zwift indoor); `.fit` only with `--push-to-garmin` flag (still gated by `TM_GARMIN_DRYRUN`). Use `fit-tool` PyPI for FIT writing. Drop `.erg`. |
| `tools/plan_week.py` | `{week_start, plan: [...], calendar_diff: [...]}` | Orchestrator. Calls `current_form`, reads docs, calls `generate_workout` per day, writes `journal/YYYY-WW-plan.md`. |
| `tools/calendar_list.py` | JSON of events in window | Read-only; uses `google-api-python-client` reading `~/.config/google-calendar-mcp/tokens.json`. |
| `tools/calendar_upsert_week.py` | `{added: N, updated: N, deleted: N, dry_run: bool}` | Default `--dry-run`; commit only with `--commit`. Always show diff first per CLAUDE.md rule #5. |

### Subagent: `coach`

First subagent. Its job: take Martin's current state + constraints + race calendar and propose a week.

`.claude/agents/coach.md`:
- name: `coach`
- description: "Multi-day planner. Use for /plan-week, mid-week adjustments, or 'should this session change given my form?'"
- allowed-tools: `Bash(uv run python tools/current_form.py)`, `Bash(uv run python tools/list_activities.py *)`, `Bash(uv run python tools/calendar_list.py *)`, `Read(docs/**)`, `Read(journal/**)`, `Write(journal/*.md)`
- model: inherit
- body: planning protocol (read state → read constraints → reason zones → cite science → flag knee → write journal → propose calendar diff). The actual prompt is roughly the example in this session's research output.
- agent memory: `.claude/agent-memory/coach/MEMORY.md` — accumulates "what works for Martin" over weeks (e.g. "threshold work when CTL >65 tends to overstress him; cap at FTP+0% on those weeks").

### Skill: `/plan-week`

`.claude/commands/plan-week.md` (already a stub):
- description: "Propose Martin's weekly training plan. Calls the coach subagent."
- body: invokes the `coach` subagent with `--task plan-week --week-start <next Monday>`. Receives the plan + diff. Writes `journal/`. Asks Martin to confirm Calendar upsert.

### Docs to update

- `docs/workout-library.md` — finalise all 7 sessions with `.zwo` skeletons (this is the source of truth for `generate_workout.py`).
- `docs/tools.md` — five new entries.
- `PLAN.md` — revise the line that says "Push-to-watch out of scope": now "behind explicit `--push-to-garmin` flag, off by default."

### Tests

- Synthetic week: form `productive`, knee green, no race in 8 weeks → plan has ≥2 hard days, ≥2 rehab, ≥1 long ride pinned to Sunday Ängby söndag.
- Form `risky` (TSB <-40) → plan is recovery-week only, no Z4+, calendar diff flags pre-existing hard sessions for removal.
- Calendar upsert dry-run shows the exact diff; commit-mode requires explicit confirmation flag.

---

## Phase 5 — M6: KOM + segments + wind

**Goal.** `/kom` ranks today's starred segments by wind alignment and Martin's current power capacity; flags realistic threats.

**Done when** Martin runs `/kom` in the morning and gets a ranked list of segments to attack today.

### Tools

| Tool | Output | Notes |
|---|---|---|
| `tools/sync_segments.py` | `{synced: N}` | Pull starred segments + KOM/QOM stats via Strava. |
| `tools/route_weather.py` | `{forecast: [...]}` | Open-Meteo direct via `httpx` (no MCP). Cache to `weather_forecast` table. |
| `tools/kom_today.py` | Ranked segment list with `score`, `tail_kmh`, `cross_kmh`, `precip_mm`, `realistic_threat: bool` | Use the wind/yaw math from `docs/wind-and-kom.md`. Sample 20 polyline points; length-weight per piece. |
| `tools/kom_threat.py` | Per-segment detail | Threshold: `P_user(T_kom) ≥ 0.97·kom_avg_w` AND `tail_kmh > 4`. |

### Subagent: `kom-hunter`

`.claude/agents/kom-hunter.md`:
- description: "Pick today's KOM-attack segments given wind + form. Use when Martin says '/kom', 'KOM today?', or 'which segment should I hit?'"
- allowed-tools: `Bash(uv run python tools/{kom_today,kom_threat,current_form,route_weather}.py *)`, `Read(docs/wind-and-kom.md)`
- body: rank segments, explain *why* (tail-wind, your power vs KOM, weather window), warn if today's TSB is bad for max efforts.

### Skill: `/kom`

Thin wrapper that invokes the kom-hunter subagent.

### Tests

- Pure-tail-wind on flat segment with Martin's P5min ≥0.97·KOM avg → marked `realistic_threat: true`.
- Pure-headwind same segment → score negative, realistic_threat false even if power matches.

### Docs

- `docs/wind-and-kom.md` — finalise (math is already in PLAN.md).

---

## Phase 6 — M7: Routes + nutrition + briefing polish

**Goal.** Plan the actual fueling and weather for tomorrow's planned ride.

**Done when** `/brief` for tomorrow's long ride returns a per-hour fueling table grounded in route weather + IF-adjusted carb math + temp-adjusted fluids/sodium.

### Tools

| Tool | Output | Notes |
|---|---|---|
| `tools/fuel_plan.py` | `{carbs_g_per_h, pre_ride_g, post_ride_carbs, post_ride_protein, fluids_ml_per_h, sodium_mg_per_h, hourly_table: [...]}` | Math from `docs/fueling.md`; clamp(60+30·IF,60,120). |
| `tools/daily_briefing.py` (extend) | adds `fuel_plan`, `route_weather` for tomorrow's planned long ride | When today is Saturday and tomorrow's plan is the Sunday Ängby söndag, surface the full fueling. |

### Subagent: `fueling-advisor`

`.claude/agents/fueling-advisor.md`:
- description: "Per-ride and race-day fueling. Use for /brief on long-ride days, race weeks, or hot-weather sessions."
- body: read `docs/fueling.md`, generate per-hour table, call out hot-day sodium adjustments.

### Skill: `/brief`

Heavier than `/today`. Includes tomorrow's preview + fueling on long-ride days.

### Docs

- `docs/fueling.md` — finalise tables (carbs/h, pre/post, fluids, sodium thresholds).

---

## Phase 7 — M8: Weekly review + polish

**Goal.** Honest retrospective; rate-limit dashboard; doc-pass.

**Done when** Martin runs `/review` on a Sunday evening, gets an honest "here's what you planned, here's what you did, here's what to change" pass, and `journal/YYYY-WW-log.md` is finalised.

### Tools

| Tool | Output | Notes |
|---|---|---|
| `tools/weekly_review.py` | `{plan_vs_actual: [...], tss_total: N, ramp: …, knee_summary: …, lessons: [...]}` | Diff `journal/.../plan.md` against actual activities. Surface what got moved, skipped, or improvised. |

### Subagent: `weekly-reviewer`

`.claude/agents/weekly-reviewer.md`:
- description: "Honest weekly retrospective. Use for /review on Sunday evenings."
- body: read plan, read log, read activities, read pmc trend, ask "what should next week change?". Writes the retrospective into `journal/YYYY-WW-log.md`. Persists lessons to `.claude/agent-memory/coach/MEMORY.md` so the coach subagent learns over time.

### Subagent: `knee-rehab` (last to add)

`.claude/agents/knee-rehab.md`:
- description: "Pick today's knee rehab session and track symptoms. Use after rides that aggravated the knee, or when Martin reports a yellow/red status."
- body: read `docs/knee-rehab.md`, pick from the exercise pool given today's pain score, log to journal under `### Knee`. Flag if no progression in 8 weeks → physio.

### Polish

- Rate-limit dashboard: `tools/rate_limits.py` → JSON of last-24h API usage by provider; surfaced in `/today` if approaching limits.
- CLAUDE.md doc pass: ensure tool/doc/skill index is current.
- `docs/tools.md` final pass with every tool's args + JSON output documented.

---

## Cross-cutting concerns

### Skill catalogue (final state, post-M8)

| Skill | Phase | Pre-approved tools | Subagent? |
|---|---|---|---|
| `/form` | 2 | `tools/current_form.py` | no |
| `/today` | 3 | `tools/daily_briefing.py`, `Read journal/` | no (inline reasoning) |
| `/sync` | 3 | `tools/sync_activities.py` | no |
| `/log` | 3 | `Write journal/` | no |
| `/plan-week` | 4 | various | yes — `coach` |
| `/kom` | 5 | various | yes — `kom-hunter` |
| `/brief` | 6 | various | yes — `fueling-advisor` on long-ride days |
| `/review` | 7 | various | yes — `weekly-reviewer` |

### Subagent catalogue (final state, post-M8)

| Subagent | Built in | Has agent memory? | When to use |
|---|---|---|---|
| `coach` | Phase 4 | yes | weekly planning, mid-week adjustments, "should this change?" |
| `kom-hunter` | Phase 5 | no (stateless ranking) | KOM hunts, segment selection |
| `fueling-advisor` | Phase 6 | no | long rides, races, hot weather |
| `weekly-reviewer` | Phase 7 | yes (writes to coach memory) | end-of-week retrospective |
| `knee-rehab` | Phase 7 | yes (symptom history) | post-flare-up rehab planning |

Five subagents total, each with a clear "when to use" boundary. Resist creating more.

### Testing strategy

- **Unit tests** in `tests/` for math (TSS, PMC, wind/yaw, fueling). Pure-function code, deterministic.
- **Golden tests** for TSS against Golden Cheetah fixtures.
- **Integration smoke tests**: each tool runs end-to-end against a small synthetic SQLite seed.
- **No live API tests** — mock Strava/Garmin/Calendar responses.
- Skip e2e tests on the AI side; the agent's behaviour is judged by Martin's "would I follow this plan?".

### Documentation maintenance

- Every new tool → row in `docs/tools.md` in the same commit (already a CLAUDE.md rule).
- Every science-cited claim in code or chat → must point to a doc heading.
- When a doc disagrees with code, fix the code (the doc is the canon).
- Quarterly: read `docs/training-science.md` and `docs/wellness.md` end-to-end; check for stale science.

### Rate limits & retry safety

- Strava: max 200 req/15min, 2000/day. Persist to `rate_limit_log`. Stop syncs at 80% of quota.
- Garmin: ≤1 req/s. **`retry_attempts=1` everywhere** (don't compound a 429).
- Open-Meteo: keyless but rate-limited per IP. Cache aggressively (`weather_forecast` table, dedup by `(lat, lon, hour_utc)`).
- Calendar: respect Google's 100 req/100s/user. Batch upserts.

### Known anti-patterns to avoid (from research)

1. **Doc bloat** — keep each doc <500 lines, one topic. If it grows, split.
2. **Tool sprawl** — one tool per data source/aggregation. Don't proliferate similar tools.
3. **Skill overlap** — one skill per workflow. Resist "/plan-day" and "/plan-month" as separate skills — they're parameters to `/plan-week`.
4. **Subagent over-engineering** — only create when you've watched Claude do the same multi-step reasoning 5+ times. PLAN.md lists five; build them one at a time as needed.
5. **Journal drift** — `/log` records *actual*; `/review` writes the retro. The coach subagent reads last week's log before planning next week.

---

## Open decisions (need Martin's input before specific phases)

| # | Decision | Phase blocked | Default if unanswered |
|---|---|---|---|
| 1 | A-race calendar 2026 (which races, dates, priorities A/B/C) | Phase 4 (planner needs targets) | Default: no race; assume Vätternrundan-style June endurance event. |
| 2 | Current FTP estimate (or run `tools/estimate_ftp.py` first) | Phase 1 onward | Run a 20-min test ride; until then assume FTP=240W and flag everything as low-confidence. |
| 3 | LTHR / max HR / RHR | Phase 1 (hrTSS), Phase 3 (HRV gating) | Estimate from data over first 14 days of sync; flag as estimated until confirmed. |
| 4 | Weight (kg) | Phase 6 (fueling math) | Default 75 kg until confirmed. |
| 5 | Garmin or Wahoo bike computer (affects `.fit` push viability) | Phase 4 (export) | Assume Garmin. |
| 6 | Is Zwift active in winter? (affects `.zwo` priority) | Phase 4 | Yes — emit `.zwo` by default. |
| 7 | Polarized vs pyramidal default | Phase 4 (planner) | Pyramidal in build, polarized 6–8 wks pre-A-race (per `docs/training-distribution.md`). |
| 8 | Knee — is the generic template OK, or wait for physio protocol? | Phase 0 | Use generic template; replace when physio prescription arrives. |
| 9 | Calendar event style: ride name only, or include workout structure in description? | Phase 4 | Include structure (HR/power targets per interval) — useful on the watch face during the ride. |
| 10 | Push-to-Garmin: Martin opts in per session, or set-and-forget after first time? | Phase 4 | Per-session opt-in (safer; matches CLAUDE.md rule #4). |

These are flagged so the relevant session opens with "decide #N before continuing".

---

## What "shipping looks like"

A typical Martin morning, post-M8:

> **Martin** (06:50, opens Claude Code): `/today`
>
> **Coach**: Good morning. CTL 64 (+3 this week, healthy). TSB +4 (productive). HRV in baseline. Sleep 7h12m (good).
>
> Today's plan from your weekly: SST 90 min — 3×12' @ 90% FTP, 4' rec.
>
> Knee status: green (no notes since last Thursday). This session is fine; just keep cadence ≥80 rpm on the intervals.
>
> Group rides today: none on Tuesday's CK Valhall schedule that line up with your evening — go solo.
>
> **Recommendation**: Go SST as planned. Eat 60g carbs in the warmup, sip 750ml/h. Optional knee rehab (15 min minimal: TKE band + clamshells) before bed.
>
> *(All citations: `docs/training-science.md#tsb-thresholds`, `docs/wellness.md#hrv-status`, `docs/workout-library.md#sst`, `docs/knee-rehab.md#weekly-template`.)*

That's the bar. Phases 0–7 are the path there.
