# Training-Mate — plan of record

This file is the durable plan for the project. Edit as decisions land.
Companion files: `CLAUDE.md` (athlete + rules), `docs/*.md` (curated knowledge), `tools/*.py` (CLI tools), `.claude/{agents,commands}/` (subagents + skills), `journal/*.md` (training diary).

---

## Current status (2026-04-27)

**Done:**
- **M1 — project skeleton.** `pyproject.toml`, `.gitignore`, `.env.example`, `.mcp.json` (Strava + Garmin), `tools/_common.py` (db handle, token loaders, JSON helpers), `tools/auth_status.py`, SQLite schema v1 with migrations, `docs/tools.md` + `docs/schema.md` stubs, `CLAUDE.md` v0.
- **M1.5 — personal context + Calendar wiring + journal scaffolding.**
  - `CLAUDE.md` filled in with Martin's profile (Ängby CC, Stockholm, right-knee rehab, gym at work, Sunday Ängby söndag as the weekly anchor). Single-device assumption explicitly noted.
  - `docs/group-rides.md` — Stockholm regular rides (Ängby söndag, Onsdagsgrus, CK Valhall Tue/Thu, Morgonspins).
  - `docs/knee-rehab.md` — provisional generic patellofemoral template (activation/strength/cool-down pools, three weekly templates, what to ask the physio). Replace with Martin's actual prescription when available.
  - Google Calendar wired into `.mcp.json` (`@cocal/google-calendar-mcp`); `tools/auth_status.py` extended to report Calendar token state. `TM_CALENDAR_NAME` env var (Martin's calendar is `Training Mate`).
  - `journal/` scaffolded: `README.md`, `_template-plan.md`, `_template-log.md`.
  - `.claude/commands/plan-week.md`, `.claude/commands/log.md` — first two slash commands.

**Pending user setup (must be done on Martin's Mac before M5):**
1. Move `~/Downloads/client_secret_*.json` → `~/.config/google-calendar-mcp/gcp-oauth.keys.json`, `chmod 600`.
2. `cp .env.example .env`; set `GOOGLE_OAUTH_CREDENTIALS=/Users/martin/.config/google-calendar-mcp/gcp-oauth.keys.json` and `TM_CALENDAR_NAME="Training Mate"`.
3. First run `npx -y @cocal/google-calendar-mcp` → browser OAuth dance.
4. Verify with `uv run python tools/auth_status.py` → `google_calendar.ok = true`.
5. Strava OAuth: `npx -y @r-huijts/strava-mcp-server` (after creating Strava API app at strava.com/settings/api).
6. Garmin SSO: `npx -y @nicolasvegam/garmin-connect-mcp` (will prompt for MFA on first run).

**Next milestone: M2 — ingest + TSS.** See sequencing below.

---

## Context

A personal AI trainer that plans, schedules, and tracks workouts (mostly cycling, some running, some strength), pulling activity data from Garmin and Strava, factoring weather/wind for KOM hunting, and grounding suggestions in actual training science (TSS / CTL / ATL / TSB, polarized/pyramidal distribution, fueling per kJ).

**Key architectural choice:** Claude Code itself *is* the trainer. There is no custom MCP server, no separate chat backend, no UI. We give Claude:
- a curated knowledge base (`docs/`) it reads on demand,
- a set of small Python CLI tools (`tools/`) it invokes via Bash and parses as JSON,
- specialized subagents (`.claude/agents/`) for narrow jobs (KOM ranking, weekly review, knee rehab),
- slash-command skills (`.claude/commands/`) for common workflows,
- a SQLite cache (`data/`) shared by all the tools,
- a `journal/` directory of weekly `.md` files Claude writes and updates — the rolling training diary, version-controlled,
- and a project `CLAUDE.md` pinning athlete profile + rules + an index of everything above.

**Three upstream MCP servers** stay loaded for ad-hoc API access:
- Strava: `@r-huijts/strava-mcp-server` (OAuth, read-only API).
- Garmin: `@nicolasvegam/garmin-connect-mcp` (mobile SSO, read-only). Garmin's official Connect Developer Program is business-only and rejects personal apps; this server is the standard community workaround.
- Google Calendar: `@cocal/google-calendar-mcp` (Google Cloud OAuth, read + write events).

Local Python tools read the same on-disk token caches the upstream MCP servers wrote (`~/.config/strava-mcp/config.json`, `~/.garmin-mcp/`, `~/.config/google-calendar-mcp/`) via `stravalib` / `garminconnect`. Direct lib calls (not MCP-to-MCP) because activity streams are big numeric arrays and routing them through MCP JSON would be wasteful.

## Architecture

```
Claude Code (the trainer)
  │
  ├── Reads on demand:
  │     CLAUDE.md                       athlete profile + rules + index
  │     docs/*.md                       training science, fueling, wind math, schema
  │
  ├── Invokes via Bash:
  │     tools/*.py                      small CLI scripts → JSON to stdout
  │       └── shared SQLite at data/training-mate.sqlite
  │
  ├── Delegates to subagents:
  │     .claude/agents/*.md             coach, kom-hunter, weekly-reviewer, fueling, knee-rehab
  │
  ├── User-triggered skills:
  │     .claude/commands/*.md           /plan-week, /today, /log, /kom, /brief, /sync, /review
  │
  ├── Writes diary:
  │     journal/YYYY-WW-{plan,log}.md   rolling training journal, committed to git
  │
  └── Three upstream MCP servers (loaded via .mcp.json) for ad-hoc API calls:
        strava-mcp        (npx)         OAuth + read-only Strava API
        garmin-mcp        (npx)         mobile SSO + read-only Garmin API
        google-calendar   (npx)         OAuth + read/write events
```

## Tool contract (shared across all `tools/*.py`)

- Single Python file, run as `uv run python tools/<name>.py [args...]`.
- Args via `argparse`; stdout is one JSON object; stderr is human-readable log lines.
- Exit 0 on success, non-zero with `{"error": "..."}` on failure.
- All DB access via `tools/_common.py:open_db()` (WAL, single connection per process).
- All Strava/Garmin auth via `tools/_common.py:strava_client()` / `garmin_client()` which read upstream MCP token caches.
- Rate-limit accounting persisted to `rate_limit_log` table.

## Core math (in `tools/`, documented in `docs/training-science.md` + `docs/wind-and-kom.md`)

**Power TSS (Coggan):**
```
NP   = (mean(rolling_mean(p, 30s)**4))**0.25
IF   = NP / FTP
TSS  = duration_h * IF**2 * 100
kJ   = sum(p)/1000
```

**hrTSS (TRIMP-based):**
```
hrr_i = (hr_i - rhr) / (max_hr - rhr)
trimp = sum( dt * hrr_i * 0.64 * exp(1.92 * hrr_i) )
hrTSS = trimp / trimp_at_threshold_for_1h * 100
```
Fallback when only avg HR known: `hrTSS = duration_h * (avg_hr/LTHR)**2 * 100`.

**rTSS:** Minetti grade-adjusted pace → `IF = NGS / threshold_pace`; `rTSS = duration_h * IF**2 * 100`.

**PMC (Banister exp-weighted, daily):**
```
CTL[d] = CTL[d-1] + (daily_tss[d] - CTL[d-1]) / 42
ATL[d] = ATL[d-1] + (daily_tss[d] - ATL[d-1]) / 7
TSB[d] = CTL[d-1] - ATL[d-1]
```
Backfill 6 months on seed. Recompute last 14 days on every ingest. Ramp target +3..+5 CTL/week; >+8 flags overreach.

**Wind/yaw (KOM ranking).** Open-Meteo gives "from" direction; convert to "to" bearing `W_to = (W_dir + 180) mod 360`.
```
delta = ((W_to - B_seg + 540) mod 360) - 180          # -180..+180
tail_kmh  = W_kmh * cos(radians(delta))
cross_kmh = W_kmh * sin(radians(delta))
score     = tail_kmh - 0.4*abs(cross_kmh) + (8<=temp<=18 ? +1 : 0) - (precip>0.5 ? 3 : 0)
```
Long curving segments: sample 20 polyline points and length-weight per-piece tail. Threat flag: `P_user(T_kom) ≥ 0.97 * kom_avg_w` AND `tail_kmh > 4`.

**Fueling:**
```
carbs_g_per_h      = clamp(60 + 30*IF, 60, 120)
pre_ride_carbs_g   = 1.5 * weight_kg
post_ride_carbs_g  = 1.0 * weight_kg
post_ride_protein  = 0.3 * weight_kg
fluids_ml_per_h    = 500 + 250*(temp_c>22)
sodium_mg_per_h    = 500..700 base, +300 if temp_c>25
```

## Sequencing (milestones)

1. **M1 — Skeleton. DONE.**
2. **M1.5 — Personal context + Calendar wiring. DONE.** (User setup steps still pending — see top of file.)
3. **M2 — Ingest + TSS.** `tools/sync_activities.py` (Strava + Garmin into SQLite), `tools/list_activities.py`, `tools/get_activity.py`, `analysis/tss.py` core, golden TSS test against a Golden Cheetah fixture FIT, `docs/training-science.md`.
4. **M3 — PMC + form.** `tools/compute_pmc.py`, `tools/current_form.py`. PMC self-check test (60 days of constant 50 TSS → CTL/ATL → 50, TSB → 0).
5. **M4 — Garmin wellness.** Extend `sync_activities.py` to pull HRV / body battery / readiness / sleep into `wellness_daily`. First version of `daily_briefing.py`.
6. **M5 — Planner + workout export + journal + calendar write.** `tools/generate_workout.py`, `tools/export_workout.py`, `tools/plan_week.py`, `tools/calendar_list.py`, `tools/calendar_upsert_week.py`, `docs/workout-library.md`. `/plan-week` writes `journal/YYYY-WW-plan.md` and offers a Calendar diff. `/log` and `/today` skills wired. Subagents `coach.md` + `knee-rehab.md`. Fill in `docs/knee-rehab.md` if Martin has a physio protocol by then.
7. **M6 — Segments + wind.** `tools/sync_segments.py`, `tools/kom_today.py`, `tools/kom_threat.py`, `docs/wind-and-kom.md`. Skill `/kom`, subagent `kom-hunter.md`.
8. **M7 — Routes + nutrition + briefing.** `tools/route_weather.py`, `tools/fuel_plan.py`, full `tools/daily_briefing.py`. Skill `/brief`, subagent `fueling-advisor.md`.
9. **M8 — Weekly review + polish.** `tools/weekly_review.py`, skill `/review` finalises `journal/YYYY-WW-log.md`, subagent `weekly-reviewer.md`. Rate-limit dashboard. CLAUDE.md doc pass.

## Risks & gotchas

- **Strava 200/15min, 2000/day** — stream pulls dominate; persist `X-RateLimit-Usage` to `rate_limit_log`, throttle nightly sync, never re-pull a stream. Use `activity:read_all` scope for private rides.
- **Garmin ToS gray area** — keep ≤1 req/s; never automate workout push without explicit confirmation; `TM_GARMIN_DRYRUN=true` enforced in `tools/_common.py`.
- **Garmin token refresh** — handle `GarthHTTPError` 401 by re-running `garth.login`; surface MFA as a structured stderr error.
- **NP for short rides** — flag `np_low_confidence=true` for activities <20 min.
- **Time zones** — store UTC; convert to local only for display and PMC daily roll-up.
- **Polyline precision** — Strava is precision 5 (`polyline.decode(s, 5)`).
- **Google OAuth in Testing mode** — refresh tokens expire after 7 days; re-run `npx -y @cocal/google-calendar-mcp` weekly. Acceptable for v1.
- **Calendar is a dedicated `Training Mate` calendar** — never write to other calendars.
- **Single-device assumption** — token caches live on Martin's laptop only. Phone/web sandbox sessions need a session-start hook + secret store; out of scope for now.
- **Don't commit secrets** — `.mcp.json` only references `${VAR}`; real values in `.env` (gitignored). `data/` gitignored.
- **Tool sprawl** — every new tool MUST be added to `docs/tools.md` with arg list and example JSON, or Claude won't know it exists.

## Out of scope for v1

- Push-to-watch / Garmin workout sync — risky write surface; emit `.zwo`/`.erg` files instead, sync manually.
- Web/mobile UI — Claude Code CLI is the trainer.
- Multi-user — auth and CTL state assume one athlete.
- Strava webhooks — would need a public endpoint; nightly polling is fine.
- ML form prediction — CTL/ATL is the standard model; ML adds nothing at this data scale.
- A custom training-mate MCP server — explicitly rejected; tools-as-CLI + docs is simpler.
- Cross-device session-start hook + secret store for tokens — punted to "when phone sessions become a real need".

## Resolved decisions

- Calendar event style: **one event per planned session** (not weekly summary).
- Calendar destination: **dedicated `Training Mate` calendar**.
- Knee rehab seed content: **generic patellofemoral template** (provisional, replace with physio protocol later).
- Strava package: `@r-huijts/strava-mcp-server` (token cache `~/.config/strava-mcp/config.json`).
- Garmin package: `@nicolasvegam/garmin-connect-mcp` (token cache `~/.garmin-mcp/`).
- Google Calendar package: `@cocal/google-calendar-mcp` (token cache `~/.config/google-calendar-mcp/`).
