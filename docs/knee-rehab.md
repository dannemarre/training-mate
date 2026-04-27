# Knee rehab — Martin's right knee

> **Status: PROVISIONAL.** This is a generic patellofemoral / anterior-knee strengthening template, not a physio prescription. Replace with the actual protocol from Martin's physio when available, and annotate over time. Until then, Claude proposes from this list and Martin gates each session on how the knee feels.

## Operating principles

1. **Ask, don't assume.** Before any rehab session, ask Martin's current knee state on a 0-10 scale (0 = pain-free, 10 = stop-everything). Adjust load and selection accordingly.
2. **Pain rule:** any movement that hits ≥4/10 during the rep is a stop. Swap or skip.
3. **Bilateral first, then unilateral.** Build a base before single-leg work.
4. **Slow eccentrics, controlled tempo.** No fast/jerky reps.
5. **Frequency:** 2-3× per week minimum during build/base. 1-2× during peak/race weeks. Daily mobility is fine.
6. **Don't combine** a hard cycling intensity day with a heavy-load lower-body strength day. Strength → before easy ride or on rest day.
7. **Cycling caveats:** big out-of-the-saddle efforts on steep climbs early in a ride are a known aggravator — warn Martin if the day's plan starts with hills.
8. **Running caveats:** long downhill running is high risk. If running is in the plan, prefer flat-to-rolling.

## The exercise pool

### A. Activation / mobility (warm-up, 5-8 min, do every session and before rides)

- **Quad sets** — supine, push knee into floor, 10s hold × 10. Wakes up VMO without load.
- **Straight-leg raise** — supine, opposite knee bent, lift to 30° over 2s, hold 2s, lower 4s. 2-3×10/leg.
- **Glute bridge** — feet flat, hips up, squeeze 2s. 2×12.
- **Clamshells** — side-lying, knees bent, open without rotating hips. 2×12-15/side.
- **Ankle pumps + heel raises bilateral** — 2×15. Keeps calves strong, takes load off the knee.
- **90/90 hip mobility** — 5/side, controlled.

### B. Strengthening (the core of rehab; 2-3× / week)

| Exercise | Default sets×reps | Tempo | Notes |
|---|---|---|---|
| **Terminal knee extension (TKE)** with band | 3×12-15 | 2s out, 3s back | Foundational. Band around back of knee, anchored ahead; extend leg fully. |
| **Wall sit** | 3× 30-45s | hold | Knees ≤90°. Stop if pain. Progress hold time, not depth. |
| **Spanish squat** (band-loaded) | 3×10 | 3s down, 2s up | Excellent for knee tendinopathies; load via band looped behind knees and anchored ahead. |
| **Step-up** (low box, then progress) | 3×8/leg | 2s up, 3s down | Drive through whole foot. Box height up only when pain-free at current. |
| **Reverse lunge** (bodyweight first) | 3×8/leg | controlled | Front foot stays flat; trail knee taps the floor lightly. |
| **Single-leg glute bridge** | 3×10/leg | 2s hold | Tracks the asymmetry over time. |
| **Side-lying hip abduction** (or band walks) | 3×12/side | controlled | Glute med — directly relevant to knee tracking. |
| **Calf raise — single-leg** | 3×12/side | 2s up, 3s down | Soleus + gastrocs; long-known cycling assistor. |
| **Bulgarian split squat** (bodyweight → DB) | 3×8/leg | controlled | Add only after 4 weeks of pain-free reverse lunges. |

**Progressing load:** add 2.5-5 kg per session only if the previous session was pain-free at all reps. Never both add load and add reps in the same week.

### C. Cool-down / mobility (5 min)

- **Quad stretch** — standing, gentle. 30s × 2/side.
- **Hip flexor stretch** (couch stretch lite) — 30s × 2/side.
- **Hamstring** — supine with strap. 30s × 2/side.
- **Calf** — wall lean, both straight and bent knee. 30s × 2/side.
- **Foam roll** — quads, ITB area, glutes (light). 1-2 min total.

## Default weekly templates (Claude picks one based on the week)

### Build week (2-3× rehab/strength)

- **Mon (gym at work):** Activation + full B list, lower load on TKE/wall sit/Spanish squat (3 main lifts).
- **Wed (post-Onsdagsgrus or skipped):** short version — activation + TKE + glute bridge variants + calves. 20 min total.
- **Fri (gym at work, pre-rest):** Activation + B list, slightly higher load if Mon was pain-free.

### Race week / peak week (1-2× minimal)

- **Mon:** Activation + TKE + glute bridge + clamshells. 15 min. No heavy load.
- **Thu (no other gym):** Same template. Maintain, don't build.

### Symptom flare week (skip cycling intensity, all rehab is recovery)

- **Daily:** Activation + isometrics only (quad sets, wall sit short hold, glute bridge isometric). No step-ups, no Spanish squats, no lunges until pain ≤2/10.
- Cycling: Z2 only on flat.
- Running: pause until pain ≤1/10 walking.

## What Claude tracks

After each rehab session, prompt Martin (or via `/log`) for:

```
Session: 2026-04-27
Knee score before (0-10): _
Knee score after  (0-10): _
What felt off: _
Exercises that bothered it: _
Load progressed: yes / no
```

Append to `journal/YYYY-WW-log.md` under the `### Knee` heading. Trends across weeks are inputs to weekly planning — if the knee got worse two weeks running, scale rehab back and ask Martin to see the physio.

## What to ask the physio (next visit)

- Specific exercises to prioritise vs avoid?
- Load progression rules?
- Cycling: sit-stand ratio limits?
- Running: distance / surface / hill restrictions?
- Imaging findings to be aware of?
- Symptom thresholds for cycling vs running vs strength?

When Martin returns from the physio, paste the answers here and replace the generic template with his prescription.
