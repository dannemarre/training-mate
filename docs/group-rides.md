# Stockholm regular group rides

Reference for weekly planning. Treat these as **fixed commitments** Martin can opt into — design the rest of the week around them, not vice versa.

When deciding "should Martin go to this one?", weigh:
- **TSB** (current form, from `tools/current_form.py`): tired → recovery instead.
- **Knee status:** any flare → skip hard intervals, swap for endurance or rehab.
- **Weather:** wind direction matters for KOM days; cold rain matters for everyone (per `docs/fueling.md` sodium/clothing notes).
- **Plan position in the week:** don't stack two hard days back-to-back unless the plan calls for it.

## Weekly fixtures

### Sunday — Ängby söndag *(default A-priority)*
- **Time:** 07:30 start.
- **Club:** [Ängby CC](https://www.angby.cc/) — Martin's club.
- **Type:** harder training ride, longer.
- **Default treatment:** the week's anchor session. Plan rest/intensity to peak Saturday so Martin shows up fresh.

### Wednesday — Onsdagsgrus
- **Time:** 18:00 start.
- **Organiser:** CykelCity.
- **Type:** gravel ride.
- **Default treatment:** a flexible Z2/Z3 ride. Good for endurance volume in season; skip if legs are cooked from a Tuesday hard session.

### Tuesday & Thursday evenings — multiple options
- **Source:** [CK Valhall training schedule](https://ckvalhall.com/pages/training-schedule) (and others).
- **Type:** varies — group rides, intervals, easier social.
- **Default treatment:** pick one of the two evenings as the **mid-week intensity slot**, based on what the schedule offers and what Sunday demands. The other evening is endurance or rest.

### Weekday mornings — Morgonspins *(optional HIIT)*
- **Time:** 06:15.
- **Where:** Djurgården — three heavy laps.
- **Type:** short, very intense.
- **Default treatment:** sparingly. Once a week max during build phases; never the day before Ängby söndag, never the day after a hard Tuesday/Thursday.

## Weekly default skeleton

A reasonable starting template (Claude will adapt based on form, knee, weather, and races):

| Day | Slot | Default |
|---|---|---|
| Mon | Rest or recovery | Easy spin or full rest; gym knee rehab. |
| Tue | Evening | One of the Tue group rides — usually intensity. |
| Wed | Evening | Onsdagsgrus (Z2/Z3 gravel). |
| Thu | Morning OR evening | Either Morgonspins or a Thu group ride — not both. |
| Fri | — | Rest or short recovery + gym strength. |
| Sat | Pre-Sunday | Easy spin / activation; gym light. |
| Sun | 07:30 | **Ängby söndag** (anchor session). |

Strength + knee rehab fit Mon, Fri, plus a top-up after one easy ride day.

## Notes for Claude

- **Don't propose moving Sunday.** Ängby söndag is non-negotiable unless Martin says otherwise.
- **Onsdagsgrus on a thrashing Wednesday after a Tuesday hard ride is a trap** — propose dropping it without making it sound like a punishment.
- When weather data shows a great wind setup for a starred KOM, surface it in `/today` even if the planned slot was just "Z2" — Martin can choose.
- Always link rides to the actual Strava activity once recorded (`activities.source = 'strava'`), so weekly review can compare planned vs done.
