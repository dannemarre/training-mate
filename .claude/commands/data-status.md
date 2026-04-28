---
description: Show what's in the local cache (activities, PMC, wellness, segments) and what needs filling. Use when Martin asks "what data do you have?", "is the history complete?", or before any session where data quality matters.
---

# /data-status

Single-screen view of cache state + actionable gaps. Run this when:
- Starting a fresh session (sanity-check before reasoning).
- Martin asks how much history is loaded.
- A coaching call seems off and you want to check if data is the cause.

## Steps

1. **Run the aggregator:**
   ```
   uv run python tools/data_status.py
   ```

2. **Translate** the JSON for Martin in 4-6 short bullets:
   - Activities: count + window. Flag if <60 days (CTL bootstrap-low).
   - PMC: days covered + current CTL/ATL/TSB.
   - Wellness: which fields are populated, how many gaps in the window. Note that HRV/Readiness will show 0 — this is expected on Martin's Garmin (watch limitation), not a bug.
   - Segments: count starred. Zero = `/kom` won't work.
   - Auth: green/red per provider.

3. **Surface the recommendations** verbatim. They're already prioritized; pick the top 1-3 to actually act on if Martin wants.

## Constraints

- Don't sound alarming about HRV being 0 — it's a correct read on Martin's setup. Cite `docs/wellness.md` reliability ranking: sleep + RHR drift + stress are the working signals.
- When the recommendation says "run X", offer to do it. Don't just suggest.
- If schema_version != 2, flag — there's a migration pending.
- This skill is read-only. Don't sync inside it; sync is `/sync`.
