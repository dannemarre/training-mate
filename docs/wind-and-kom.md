# Wind, yaw, and KOM scoring

Source for `tools/kom_today.py`, `tools/kom_threat.py`, `tools/route_weather.py`. Math comes from cycling-aerodynamics fundamentals + Open-Meteo's wind data.

## Wind data — Open-Meteo

Free, keyless, JSON. We use it directly via `httpx` (no MCP — too thin to wrap).

Endpoint: `https://api.open-meteo.com/v1/forecast`

Key params:
- `latitude`, `longitude`
- `hourly=temperature_2m,wind_speed_10m,wind_direction_10m,precipitation`
- `forecast_days=7`
- `timezone=Europe/Stockholm`

`wind_direction_10m` is the **"from" bearing** (meteorological convention — where the wind is coming from). To get the "to" direction (which way it's blowing toward, for tailwind math):

```
wind_to_bearing = (wind_from_deg + 180) % 360
```

Cache responses in `weather_forecast` table keyed by `(lat, lon, hour_utc)`. Don't refetch if cached < 1 hour old.

## Yaw / wind component math

Given a segment's bearing `B_seg` (start → end heading) and the wind's "to" bearing `W_to`, the angle between rider and wind:

```python
delta = ((W_to - B_seg + 540) % 360) - 180   # range -180 to +180
tail_kmh  = wind_kmh * cos(radians(delta))    # +ve = tailwind, -ve = headwind
cross_kmh = wind_kmh * sin(radians(delta))    # always magnitude useful
```

A tailwind helps; a headwind hurts; a crosswind is mostly drag and adds rider stability cost.

## Scoring a segment for "should I attack today?"

```python
score = tail_kmh
       - 0.4 * abs(cross_kmh)          # crosswind penalty (drag + handling)
       + (1 if 8 <= temp_c <= 18 else 0)   # ideal temperature bonus
       - (3 if precip_mm > 0.5 else 0)    # rain penalty (grip + visibility)
```

Higher = better. Score is a relative ranking; absolute number isn't physically meaningful.

`tools/kom_today.py` ranks today's starred segments by this score, fetches Martin's recent power capacity, and outputs the top 5.

## Long curving segments — sample 20 points

A 5 km segment that curves 90° has a different effective bearing from start to mid to end. For segments longer than ~1 km, sample 20 points along the polyline (Strava precision-5 encoding):

```python
import polyline
points = polyline.decode(seg.polyline, 5)  # [(lat, lon), ...]
sampled = points[::max(1, len(points)//20)]
piece_bearings = [bearing(a, b) for a, b in zip(sampled, sampled[1:])]
piece_lengths  = [haversine(a, b) for a, b in zip(sampled, sampled[1:])]
weighted_tail  = sum(
    L * wind_kmh * cos(radians(((W_to - B + 540) % 360) - 180))
    for L, B in zip(piece_lengths, piece_bearings)
) / sum(piece_lengths)
```

`weighted_tail` is the length-weighted tail-wind component along the segment. Use it instead of single-point `tail_kmh` for long segments.

## Threat threshold — when to alert

A "threat" = a segment where Martin has a realistic shot at the KOM today.

```
realistic_threat = (
    P_user(T_kom) >= 0.97 * kom_avg_w
    AND tail_kmh > 4
    AND precip_mm <= 0.5
    AND segment_length > 200m   # below this, sprints not endurance — different math
)
```

Where:
- `T_kom` = current KOM time (seconds).
- `P_user(T_kom)` = Martin's best average power for that duration over the last 90 days. Estimated from his power-curve (computed in `tools/kom_threat.py` from `activity_streams`).
- `0.97` = the "you'd need to be within 3% of KOM avg power" cushion. Slightly conservative.
- `tail_kmh > 4` = need a real tailwind, not just neutral.

If realistic_threat is true: surface in `/today` and `/kom`. If form state allows (TSB ≥ 0), recommend the attempt. If form state is overreached, suggest deferring to a better day.

## Bearings — initial bearing formula

```python
import math
def bearing(p1, p2):
    lat1, lon1 = map(math.radians, p1)
    lat2, lon2 = map(math.radians, p2)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360  # 0..359
```

Bearings are pre-computed and stored in `segments.bearing_deg` so KOM tools don't recompute on every wind query.

## Stockholm-specific wind notes

- Prevailing wind direction: **southwesterly** in spring/summer, **northwesterly** in autumn/winter.
- Coastal segments get more sustained wind; inland (Hagaparken, Solna) is gustier but lower mean.
- Crosswind handling on Solnavägen / Drottningholmsvägen with a strong west wind: be prepared, lots of trucks.

These are observational; not formal meteorological notes.

## What `kom_today.py` returns

```json
{
  "date": "2026-04-27",
  "lat": 59.342,
  "lon": 18.005,
  "ranked": [
    {
      "segment_id": 12345,
      "name": "Hagaparken north",
      "distance_m": 1850,
      "bearing_deg": 12,
      "kom_time_s": 168,
      "kom_avg_w": 442,
      "wind_to_deg": 195,
      "wind_kmh": 22,
      "tail_kmh": 19.4,
      "cross_kmh": 4.7,
      "temp_c": 14,
      "precip_mm": 0.0,
      "score": 22.5,
      "p_user_at_t_kom": 410,
      "realistic_threat": false,
      "reason": "tailwind strong but power gap 7% short of KOM avg"
    },
    ...
  ]
}
```

## What's not in this doc

- Power-curve estimation for `P_user(T_kom)` → `tools/estimate_ftp.py` (extended) or a dedicated `tools/power_curve.py` (M5+).
- Open-Meteo schema details → reference https://open-meteo.com/en/docs.
- Strava segment data model → `docs/schema.md` `segments` table.
