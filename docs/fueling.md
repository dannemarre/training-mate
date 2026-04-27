# Fueling — carbs, fluids, sodium

Source for `tools/fuel_plan.py` and the `fueling-advisor` subagent. Math comes from sports-nutrition consensus (ACSM, Burke, Jeukendrup). Tables are tuned for Stockholm climate + Martin's road / gravel / occasional KOM context.

## In-ride carbs per hour

The single most important number. Maps intensity to carb requirement:

```
carbs_g_per_h = clamp(60 + 30 × IF, 60, 120)
```

Where `IF` is the ride's intensity factor (NP/FTP) — see `docs/training-science.md`.

| IF | Carbs/h | Notes |
|---|---|---|
| 0.55 (recovery / Z1) | 60 g | Floor — lower is fine but not necessary |
| 0.65 (Z2 endurance) | 80 g | Sunday Ängby söndag default |
| 0.80 (Z3 / SST) | 100 g | Race-pace efforts |
| 0.90+ (race / hard group) | 120 g | Ceiling — 120 g/h is the upper bound for trained guts |

**Practical sources of carbs/h:**

| Item | Approximate carbs |
|---|---|
| Standard energy gel | 20–25 g |
| Energy bar | 30–40 g |
| Banana | 25 g |
| 750 ml bottle of 6% sports drink | 45 g |
| Maurten 320 mix (1 bottle) | 79 g |
| SiS Beta Fuel 80 sachet | 80 g |

Two gels + one bottle of 6% drink = ~95 g/h. Double-bottle Beta Fuel = 160 g over a 90-min ride at high intensity (~110 g/h sustained).

Sources: [Jeukendrup carb intake review](https://pubmed.ncbi.nlm.nih.gov/24791914/), [ACSM nutrition position stand](https://journals.lww.com/acsm-msse/Fulltext/2016/03000/Nutrition_and_Athletic_Performance.25.aspx).

## Pre-ride

```
pre_ride_carbs_g = 1.5 × weight_kg
```

Eat 1–3 hours before the ride start. For a 75 kg rider that's ~110 g — equivalent to a bowl of oatmeal + banana + small honey toast.

For early starts (e.g. Ängby söndag 07:30): 1 g/kg simple carbs 30–45 min before (banana + drink mix) is the practical compromise.

## Post-ride recovery

```
post_ride_carbs_g   = 1.0 × weight_kg
post_ride_protein_g = 0.3 × weight_kg
```

For a 75 kg rider: ~75 g carbs + 22 g protein within 60 min of finishing. A bowl of oats with milk + recovery shake hits both. Two slices of bread + 200 g greek yogurt + banana also works.

The 60-min window matters more after long / hard rides than after Z1 recovery spins.

## Fluids

```
fluids_ml_per_h = 500 + 250 × (1 if temp_c > 22 else 0)
```

| Temperature | Fluid /h |
|---|---|
| < 22 °C | 500 ml | Stockholm spring/autumn default |
| ≥ 22 °C | 750 ml | Hot summer days |
| ≥ 28 °C | 1000 ml | Heat-warning territory (rare in Stockholm) |

Two bottles per 2-hour ride is the rule of thumb in Sweden's climate. Three bottles or refill points if hot.

## Sodium

```
sodium_mg_per_h = 500–700  (base)
                + 300 if temp_c > 25
                + 200 if very heavy sweater (athlete_profile.heavy_sweater = true)
```

Most sports drinks contain 200–400 mg sodium per 500 ml. Salt tablets or hot-day mixes (e.g. Skratch hyperhydration) bump this for hot days.

For Martin's typical ride (Stockholm, <22 °C, normal sweat rate): 500–700 mg/h is the target — covered by drinking electrolyte mix throughout.

## Race-day pacing of nutrition

For an A-race or long event (Vätternrundan, Engelbrektsloppet etc.), the per-hour budget is the rough planning number, but **timing matters**:

- Hour 1: 60–80 g (don't overeat early).
- Hour 2 onward: ramp to target. If target is 100 g/h, hit it from h2.
- Last hour: maintain or scale slightly down (avoid GI cramps in the final stretch).
- Caffeine: 1–3 mg/kg taken 45–60 min before the hard finish (timing depends on event length). Skip if caffeine-sensitive.

`tools/fuel_plan.py --duration_h 5 --IF 0.72 --temp_c 18` produces an hourly table.

## Hot day rules

When forecast says >25 °C:

- Pre-cool: cold shower or ice slurry 30 min before start.
- Bottles: at least 1 frozen for the back pocket.
- Sodium: use a high-sodium mix (e.g. Skratch high-sodium, Precision PH 1500).
- Slow the pace: heat shifts the IF↔HR relationship; don't chase old power numbers.

## Cold day rules

When forecast says <5 °C:

- Calorie need *increases* — body uses energy to stay warm. Don't undercut on carbs.
- Hot drink in one bottle (warm tea + dilute drink mix).
- Sodium need is lower — drop to 400 mg/h base.
- Watch fluid loss anyway — cold air dehydrates through breathing.

## What `fuel_plan.py` returns

```json
{
  "duration_h": 4.0,
  "IF": 0.72,
  "temp_c": 18,
  "carbs_g_per_h": 81,
  "carbs_g_total": 324,
  "fluids_ml_per_h": 500,
  "fluids_ml_total": 2000,
  "sodium_mg_per_h": 600,
  "sodium_mg_total": 2400,
  "pre_ride_carbs_g": 113,
  "post_ride_carbs_g": 75,
  "post_ride_protein_g": 22,
  "hourly_table": [
    {"hour": 1, "carbs_g": 65, "fluids_ml": 500, "sodium_mg": 600, "note": "build up gradually"},
    {"hour": 2, "carbs_g": 81, "fluids_ml": 500, "sodium_mg": 600, "note": "target rate"},
    {"hour": 3, "carbs_g": 81, "fluids_ml": 500, "sodium_mg": 600, "note": "target rate"},
    {"hour": 4, "carbs_g": 81, "fluids_ml": 500, "sodium_mg": 600, "note": "final hour, maintain"}
  ]
}
```

## What's not in this doc

- Specific brand recommendations — Martin's preferred brands go in `journal/` notes.
- Race-day playbook (mental + logistics) — separate doc, defer to M7.
- Weight-loss / body-comp goals — out of scope; this is a coaching tool, not a diet tool.
