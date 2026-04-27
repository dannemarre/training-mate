# Training distribution — polarized vs pyramidal

How to choose the mix of intensities across a week. Used by `tools/plan_week.py` and the `coach` subagent.

## The two (well, three) schools

**Pyramidal.** The classic cyclist's distribution: ~80% Z1/Z2, ~15% Z3 (tempo / SST), ~5% Z4+ (threshold + VO2). Lots of base, moderate sweet spot, dash of intensity.

**Polarized (Seiler 80/20).** ~80% Z1/Z2, ~0% Z3, ~20% Z4+. The middle is empty on purpose — either truly easy or truly hard, no "tempo middle ground."

**Threshold-heavy.** Old-school cycling: lots of Z3/Z4 sweet spot. Higher acute fatigue, faster early gains, harder to sustain.

## What the evidence says

A 2024 systematic review (Selles-Perez et al.) and Frontiers 2025 review found:
- **Polarized's edge is short-block (≤12 wk) VO2peak gains.** For sharpening pre-race, polarized helps.
- **For longer training periods, pyramidal and polarized are roughly equivalent.** No clear winner.
- **Real-world cyclists trend pyramidal**, runners trend polarized — sport demand explains it.

Sources: [PMC 2024 systematic review](https://pmc.ncbi.nlm.nih.gov/articles/PMC11329428/), [Frontiers 2025 TID review](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2025.1657892/full), [FastTalk Labs Seiler pathway](https://www.fasttalklabs.com/pathways/polarized-training/).

## Project default for Martin

- **Build phase (default):** **Pyramidal**. Lots of Z2 (Sunday Ängby söndag, Wednesday Onsdagsgrus, easy commute days), 1–2 SST midweek, 1 threshold or VO2.
- **Pre-A-race (6–8 weeks out):** **Polarized**. Drop SST. Replace with one VO2 + one threshold session weekly; the rest is Z2 endurance.
- **Recovery week** (every 3–4 weeks): scale all volume by 0.6–0.7, no Z4+, knee rehab + Z2 only.

The `coach` subagent picks the mode based on:
1. Days to next A-race (`athlete_profile` race calendar — to be filled in).
2. Current `form_state` from `tools/current_form.py`.
3. Recent week's actual distribution (from `tools/weekly_review.py`).

## Counting zone time — the Seiler rule

Group rides are messy: a "Z2 endurance" ride often has 10 min of Z5 surges. How do we count it for the 80/20 ledger?

**Two methods:**

1. **Time-in-zone** (Coggan-influenced). Literal seconds in each zone. Honest about total stress. **Use for `analysis/tss.py` TSS computation.**
2. **Session classification** (Seiler). If ≥75% of ride time was Z1/Z2 by power, classify the whole session as "endurance" for the 80/20 ledger. **Use for `tools/weekly_review.py` distribution accounting.**

So a single ride can be: TSS = 250 (high — captures the Z5 surges), and "endurance session" (because ≥75% was Z1/Z2). Both are correct; they answer different questions.

Document this in the weekly review when it surfaces. Don't pretend one method captures everything.

## Sample week — pyramidal build

| Day | Session | Approx TSS | Zone notes |
|---|---|---|---|
| Mon | Rest + knee rehab | 0 | — |
| Tue | SST 2×20' @ 90% (90 min total) | 95 | Z3-Z4 |
| Wed | Onsdagsgrus group (Z2/Z3, 90 min) | 75 | endurance session |
| Thu | Threshold 4×10' @ 100% (75 min) | 90 | Z4 |
| Fri | Rest + knee rehab + light strength | 0 | — |
| Sat | Easy 60 min Z2 | 45 | endurance |
| Sun | **Ängby söndag** (3 h, ≥75% Z2) | 200 | endurance session |
| **Total** | | **505** | productive build |

Distribution by session type: 5 endurance / 1 SST / 1 threshold. By time-in-zone: roughly 75% Z1/Z2, 15% Z3, 10% Z4+. Both pyramidal-flavored.

## Sample week — polarized peak

| Day | Session | Approx TSS | Zone notes |
|---|---|---|---|
| Mon | Rest | 0 | — |
| Tue | VO2max 5×4' @ 115% (75 min) | 90 | Z5 |
| Wed | Easy 60 min Z2 | 45 | endurance |
| Thu | Threshold 2×20' @ 100% (75 min) | 90 | Z4 |
| Fri | Rest + minimal knee rehab | 0 | — |
| Sat | Easy 60 min Z2 | 45 | endurance |
| Sun | Ängby söndag long Z2 (3h, controlled) | 180 | endurance |
| **Total** | | **450** | race-ready taper |

Distribution: 4 endurance / 1 VO2 / 1 threshold. By time: ~80% Z1/Z2, almost no Z3, ~15-20% Z4+. Polarized.

## Sample week — recovery

| Day | Session | Approx TSS | Notes |
|---|---|---|---|
| Mon | Rest + full knee rehab block | 0 | — |
| Tue | Z2 60 min | 40 | — |
| Wed | Rest | 0 | — |
| Thu | Z2 60 min | 40 | — |
| Fri | Rest + knee rehab | 0 | — |
| Sat | Z2 60–90 min | 50 | — |
| Sun | Easy social Z2 90 min (skip Ängby pace) | 60 | — |
| **Total** | | **190** | recovery |

No Z4+. Sunday is "easy social ride" not the Ängby pace. The Sunday-anchor rule still applies socially.

## What the `coach` subagent should output

When proposing a week, always state:
- The chosen mode (pyramidal / polarized / recovery).
- Why (form state, race countdown).
- The expected total TSS budget.
- Per-day session + estimated TSS.
- Which days will be "session-classified as endurance" vs "session-classified as intensity" for the weekly ledger.

Then reconcile against `docs/training-science.md` form-state budget — if total TSS exceeds the band, replan or warn.
