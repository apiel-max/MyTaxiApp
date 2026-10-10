# Team Collaboration Guide — NYC Urban Mobility Data Explorer

## Who owns what

| Member | Role | Files |
|--------|------|-------|
| **Abay Tessema** | Data Engineering | `pipeline/profile_data.py`, `pipeline/clean_data.py`, `pipeline/convert_zones.py`, `pipeline/make_sample.py`, `database/load_database.py` |
| **Alier Akuang** | Database & API | `database/schema.sql`, `database/indexes.sql`, `backend/db.py`, `backend/app.py` (all endpoints except `/api/top-routes` and `/api/zones/<id>`), `README.md`, `requirements.txt` |
| **Kuol Akech** | Frontend | `frontend/index.html`, `frontend/css/style.css`, `frontend/js/api.js`, `frontend/js/main.js` |
| **Chol Mach Kuol** | Algorithms & Visualisation | `backend/algorithms.py`, `frontend/js/charts.js`, `frontend/js/map.js`, `/api/top-routes` and `/api/zones/<id>` in `backend/app.py` |

**Rule: never edit a file you do not own. Ask the owner instead.**

---

## Git workflow — same for everyone

```bash
# 1. Clone the repo on your own machine (do this once)
git clone https://github.com/apiel-max/MyTaxiApp.git
cd MyTaxiApp

# 2. Create your personal branch (do this once)
git checkout -b abay/pipeline      # Abay
git checkout -b alier/database     # Alier
git checkout -b kuol/frontend      # Kuol
git checkout -b chol/algorithms    # Chol

# 3. Every time you finish a piece of work, commit it
git add pipeline/clean_data.py
git commit -m "clean_data: exclude rides with zero trip distance"
git push origin abay/pipeline

# 4. Open a Pull Request on GitHub → main and tag one teammate to review
```

---

# ABAY TESSEMA — Data Engineering

Your job is to turn the three raw TLC files into clean CSVs and a working
SQLite database. Everything else in the project depends on your output.

## Before you start

Make sure you have these three files in `data/raw/`:
```
data/raw/
  yellow_tripdata_2019-01.csv
  taxi_zone_lookup.csv
  taxi_zones/
    taxi_zones.shp
    taxi_zones.dbf
    taxi_zones.prj
```
If you don't have them, download from the NYC TLC website or get the Google
Drive link from the team. Without these files nothing runs.

Install dependencies first:
```bash
pip install -r requirements.txt
```

## Your tasks in order

### Task 1 — Profile the raw data
Run this before touching anything else. It tells you what is broken in the
raw file and gives you the numbers you need for the report.

```bash
python pipeline/profile_data.py
```

This reads `data/raw/yellow_tripdata_2019-01.csv` and prints:
- how many rows are missing values in each column
- how many exact duplicate rows exist
- pickup timestamps outside January 2019
- trips with zero or negative distance
- trips with impossible speeds (> 100 mph)
- fare amounts that are negative or above $500
- what values appear in VendorID, RatecodeID, payment_type

It saves the full output to `docs/data_profile.txt`. **Commit that file** —
it is evidence for your report and the marker will look for it.

```bash
git add docs/data_profile.txt
git commit -m "pipeline: add raw data profile output"
git push origin abay/pipeline
```

### Task 2 — Clean the data
```bash
python pipeline/clean_data.py
```

This script removes bad rides, repairs small problems, and adds derived
columns. When it finishes you will see output like:
```
pickup_outside_jan_2019        4,123
dropoff_not_after_pickup          87
duration_over_6h               1,204
zero_distance                 14,302
...
TOTAL EXCLUDED               ~200,000  (2.7%)
Done in 45s: 7,300,000 clean rides
```

Check that `data/processed/` now contains:
```
trips_clean.csv
excluded_records.csv
suspicious_records.csv
cleaning_summary.json
```

If you see an error like `FileNotFoundError: yellow_tripdata_2019-01.csv`,
the raw file is missing from `data/raw/`. Check Task 0 above.

### Task 3 — Convert the zone shapefile to GeoJSON
```bash
python pipeline/convert_zones.py
```

The TLC shapefile uses a coordinate system measured in feet from a reference
point in New Jersey — not longitude/latitude. This script converts it.
When it finishes you will see:
```
Wrote 262 zones to data/processed/taxi_zones.geojson (1.8 MB)
```

If you see fewer than 260 zones, something went wrong with the shapefile.
Check that `data/raw/taxi_zones/` contains `.shp`, `.dbf`, and `.prj` files.

### Task 4 — Build the database
```bash
# For testing (fast, ~30 seconds, loads 10% of trips):
python database/load_database.py --sample 0.1

# For the final submission (full dataset, ~3-5 minutes):
python database/load_database.py
```

When it finishes you will see:
```
  zone_date_hour_stats: 98,432 rows
  route_date_stats: 487,201 rows
  foreign keys OK, row counts OK, summary tables add up
Done in 180s -> data/mobility.db (2.71 GB)
```

If you see `Foreign key violations`, something went wrong in the pipeline.
Re-run Tasks 2 and 3 first, then try again.

### Task 5 — Verify everything works end to end
```bash
python backend/app.py &
curl http://127.0.0.1:5000/api/health
```

You should see:
```json
{"status": "ok", "trips_in_database": 7300000}
```

If you see `Database not found`, the path in `backend/db.py` does not match
where you saved `mobility.db`. Check the `MOBILITY_DB` environment variable
or the default path in `db.py`.

### Task 6 — Make a small sample for teammates
Not everyone has 16GB of RAM. Run this so teammates can test quickly:
```bash
python pipeline/make_sample.py data/raw/yellow_tripdata_2019-01.csv 0.05
```
This creates `data/raw/yellow_tripdata_sample.csv` (5% of rides, ~20MB).
Upload it to Google Drive along with the other raw files and share the link
in the team WhatsApp/Slack.

## What to commit
```bash
git add docs/data_profile.txt
git add data/processed/cleaning_summary.json
# Do NOT commit trips_clean.csv or mobility.db — they are too large
# They are already in .gitignore
git commit -m "pipeline: add profiler output and cleaning summary"
git push origin abay/pipeline
```

## Your report section — Section 1 (400–500 words)
Write this after running the profiler so you have real numbers.

Answer these four questions in your own words:
1. What is the dataset? (NYC TLC yellow taxi, January 2019, how many rows, what columns)
2. What data problems did you find? Use the exact numbers from `docs/data_profile.txt`
   — e.g. "14,302 rides had zero trip distance", "87 rides had a dropoff before pickup"
3. Why did you choose each cleaning threshold?
   — e.g. "We set the max duration to 6 hours because the distribution showed a
   clear spike at 24 hours, which is a meter left running overnight, not a real trip"
4. One thing that surprised you — e.g. `congestion_surcharge` was NULL for every
   single ride in January 2019 because the surcharge only started in February 2019

---

# ALIER AKUANG — Database & API

Your job is to own the database schema, the DB connection layer, and all API
endpoints except the two that use Chol's algorithms.

## Before you start

You need Abay's pipeline to have run first. Check:
```bash
ls data/processed/
# Should show: trips_clean.csv, excluded_records.csv, taxi_zones.geojson, cleaning_summary.json
ls data/
# Should show: mobility.db
```

If those files are missing, ask Abay to run his pipeline and share the outputs.

Install dependencies:
```bash
pip install -r requirements.txt
```

## Your tasks in order

### Task 1 — Read schema.sql and understand the structure
Open `database/schema.sql` and read it top to bottom. You need to be able to
explain every table in the viva. The structure is:

- `boroughs`, `zones`, `vendors`, `rate_codes`, `payment_types` — small lookup
  tables. A borough name is stored once here, not repeated 7.5 million times.
- `trips` — the fact table. One row per cleaned ride. References the lookup
  tables by integer ID.
- `excluded_records` + `exclusion_reasons` — the transparency log.
- `zone_date_hour_stats` — pre-aggregated totals by date × zone × hour.
  ~100k rows. Most dashboard queries hit this instead of the 7.5M-row trips table.
- `route_date_stats` — pre-aggregated totals by date × pickup zone × dropoff zone.

### Task 2 — Start the server and test your endpoints
```bash
python backend/app.py
```

Open a second terminal and test each endpoint one by one:
```bash
# Health check — should return {"status": "ok", "trips_in_database": ...}
curl -s http://127.0.0.1:5000/api/health | python3 -m json.tool

# Meta — should return boroughs, zones, payment types, date range
curl -s http://127.0.0.1:5000/api/meta | python3 -m json.tool

# Summary with no filters
curl -s "http://127.0.0.1:5000/api/summary" | python3 -m json.tool

# Summary filtered to Manhattan (borough_id=1) morning rush (7-9am)
curl -s "http://127.0.0.1:5000/api/summary?borough_id=1&hour_min=7&hour_max=9" | python3 -m json.tool

# Hourly breakdown
curl -s "http://127.0.0.1:5000/api/by-hour" | python3 -m json.tool

# Heatmap (weekday x hour grid)
curl -s "http://127.0.0.1:5000/api/heatmap" | python3 -m json.tool

# Daily totals
curl -s "http://127.0.0.1:5000/api/by-day" | python3 -m json.tool

# Zone stats (one row per pickup zone, used to colour the map)
curl -s "http://127.0.0.1:5000/api/zone-stats" | python3 -m json.tool

# Trip list, sorted by fare descending
curl -s "http://127.0.0.1:5000/api/trips?sort=fare_amount&order=desc" | python3 -m json.tool

# Data quality log
curl -s "http://127.0.0.1:5000/api/data-quality" | python3 -m json.tool
```

Every endpoint must return a 200 with valid JSON. If you get a 500, the
database is missing — check that `data/mobility.db` exists.

### Task 3 — Draw the architecture diagram
Use Draw.io (free at app.diagrams.net). Draw these boxes connected by arrows:

```
[Raw CSV files]
      ↓
[pipeline/clean_data.py]  [pipeline/convert_zones.py]
      ↓                           ↓
[data/processed/trips_clean.csv]  [taxi_zones.geojson]
      ↓
[database/load_database.py]
      ↓
[data/mobility.db  (SQLite)]
      ↓
[backend/app.py  (Flask API)]
      ↓
[browser: frontend/index.html]
```

Export as PNG, save to `docs/architecture.png`, commit it:
```bash
git add docs/architecture.png
git commit -m "docs: add system architecture diagram"
git push origin alier/database
```

### Task 4 — Fill in the README links
Open `README.md` and replace the two placeholder comments:
```
**Video walkthrough:** <!-- ADD YOUR VIDEO LINK HERE before submitting -->
**Scrum board:** <!-- ADD YOUR SCRUM BOARD LINK HERE -->
```
with the real links once Kuol has uploaded the video and the team has a
scrum board. Commit the change:
```bash
git add README.md
git commit -m "README: add video walkthrough and scrum board links"
git push origin alier/database
```

## Your report section — Section 2 (400–500 words)
Answer these questions in your own words:
1. Include `docs/architecture.png` and describe what each layer does
2. Why SQLite and not PostgreSQL? (single file, no server to install, easy to
   share with teammates, fast enough for a read-only dashboard)
3. Why a star schema? (storing "Manhattan" once in `boroughs` instead of
   repeating it 4 million times in `trips` saves ~200MB and makes joins fast)
4. Why two summary tables? (~50MB extra storage means most queries run in
   milliseconds instead of scanning 7.5M rows)
5. Why are indexes applied after bulk insert? (inserting 7.5M rows with
   indexes active is ~5x slower because every insert updates every index)

---

# KUOL AKECH — Frontend

Your job is to own the HTML structure, all CSS, the API fetch layer, and the
main dashboard orchestrator. Chol owns `charts.js` and `map.js` — never edit
those files.

## Before you start

You can work on layout and styles without the backend running. To see real
data you need Abay's database and the server running:
```bash
python backend/app.py
# Then open http://127.0.0.1:5000
```

## Your tasks in order

### Task 1 — Open the dashboard and understand what each section does
Open `http://127.0.0.1:5000` in your browser. You should see:
- A header with 5 KPI numbers (rides, fare, speed, fare/mile, tip)
- A filter bar at the top
- A zone map of New York
- Two line charts (speed and fare/mile by hour)
- A heatmap (weekday × hour)
- A daily bar chart
- A top routes table
- A paginated trip explorer
- A data quality section at the bottom

Open DevTools (F12) → Network tab. Change a filter and watch the API calls
fire. Every section makes its own request independently.

### Task 2 — Understand how filters work
Open `frontend/js/main.js`. Find `readFilters()`:

```javascript
function readFilters() {
  const data = new FormData(form);
  const f = {};
  for (const [k, v] of data.entries()) f[k] = v.trim();
  f.airport_only = data.has("airport_only");
  return f;
}
```

This reads every `<input>` and `<select>` in the filter form by their `name`
attribute. If you add a new filter to `index.html` with a `name`, it gets
picked up here automatically — no JS change needed.

### Task 3 — Understand how a section loads
Find `loadMeter(f)` in `main.js`. Every section follows this same pattern:

```javascript
async function loadMeter(f) {
  const meter = $(".meter");
  meter.classList.add("is-loading");
  try {
    const { data, ms } = await get("summary", f);   // call the API
    $("#m-trips").textContent = fmt.int(data.trips); // update the DOM
    $("#m-fare").textContent = fmt.money(data.avg_fare);
    // ...
  } catch (err) {
    if (err.name !== "AbortError") $("#m-source").textContent = err.message;
  } finally {
    meter.classList.remove("is-loading");
  }
}
```

`get()` is in `api.js`. It cancels any previous request for the same endpoint
so fast filter changes never show stale data.

### Task 4 — Take the 6 required screenshots
Start the server, open `http://127.0.0.1:5000`, and take these screenshots.
Save them to `docs/screenshots/` with exactly these filenames:

| Filename | How to get it |
|----------|--------------|
| `dashboard_overview.png` | Load the page with no filters. Screenshot the whole page. |
| `map_speed.png` | In the "Shade zones by" dropdown, select "Average speed". Screenshot the map. |
| `heatmap.png` | Scroll to the heatmap section. Screenshot it showing the Thu/Fri evening peak. |
| `top_routes.png` | Scroll to the top routes table. Screenshot it. |
| `zone_detail.png` | Click any zone on the map (try Midtown). Screenshot the side panel that appears. |
| `data_quality.png` | Scroll to the bottom "What we removed" section. Screenshot it. |

```bash
git add docs/screenshots/
git commit -m "docs: add dashboard screenshots for report"
git push origin kuol/frontend
```

### Task 5 — Record the 5-minute video
Use Loom, OBS, or QuickTime. Structure it exactly like this:

- **0:00–0:30** — You speak: "This is the NYC Urban Mobility Data Explorer.
  It lets you explore every yellow taxi ride in January 2019 — 7.5 million
  trips — filtered by borough, time of day, fare range, and more."
- **0:30–2:00** — Live demo. Change the borough filter to Manhattan. Change
  the hour filter to 7am–9am. Show the map updating, the heatmap changing,
  the routes table updating. Click a zone on the map and show the detail panel.
- **2:00–3:30** — Alier shares screen and walks through the architecture
  diagram. He explains each layer in 2–3 sentences.
- **3:30–4:30** — Chol shares screen and shows `algorithms.py`. He explains
  what the MinHeap does and why it is faster than sorting.
- **4:30–5:00** — Each person says one sentence: "I built [X] which does [Y]."

Upload to YouTube (unlisted) or Google Drive. Copy the link and give it to
Alier to put in the README.

## Your report contribution
You do not write a full section but you provide the screenshots that go into
Section 4 (Chol's insights section). Make sure the screenshots are clear,
full-resolution, and saved before the deadline.

---

# CHOL MACH KUOL — Algorithms & Visualisation

Your job is to own the three hand-written algorithms, the two SVG chart files,
the SVG zone map, and the two API endpoints that call your algorithms.

## Before you start

```bash
# Test the algorithms without needing the database
python backend/algorithms.py
# Should print: All algorithm self-tests passed.

# Test your endpoints (needs the database)
python backend/app.py &
curl "http://127.0.0.1:5000/api/top-routes?k=5"
curl "http://127.0.0.1:5000/api/zones/161"
```

## Your tasks in order

### Task 1 — Run the algorithm self-tests and make sure they pass
```bash
python backend/algorithms.py
```

If any assertion fails, read the error message — it tells you which trial
number failed and what the expected vs actual values were. Fix the algorithm
before moving on.

### Task 2 — Test your two endpoints manually
```bash
python backend/app.py &

# Top 5 busiest routes across all of January
curl -s "http://127.0.0.1:5000/api/top-routes?k=5" | python3 -m json.tool

# Top 10 routes on Monday mornings only
curl -s "http://127.0.0.1:5000/api/top-routes?k=10&dow=0&hour_min=7&hour_max=9" | python3 -m json.tool

# Zone detail for Midtown Center (zone 161)
curl -s "http://127.0.0.1:5000/api/zones/161" | python3 -m json.tool

# Zone detail for JFK Airport (zone 132)
curl -s "http://127.0.0.1:5000/api/zones/132" | python3 -m json.tool
```

Check that `/api/top-routes` returns a `distinct_routes_ranked` field showing
how many zone pairs were ranked (should be ~50,000 for no filters). Check that
`/api/zones/161` returns `median_fare` and `top_destinations`.

### Task 3 — Open the dashboard and check the charts render
```bash
open http://127.0.0.1:5000
```

Check each of these works:
- The zone map loads and zones are coloured
- Clicking a zone shows the detail panel with top destinations and median fare
- The speed line chart and fare/mile line chart both render
- Hovering over one chart highlights the same hour on the other chart
- The heatmap renders with 7 rows (days) × 24 columns (hours)
- The daily bar chart renders with weekends in orange
- The top routes table shows 10 rows

If any chart is blank, open DevTools → Console and look for errors.

### Task 4 — Understand what your algorithms actually do in production

**top_k in /api/top-routes:**
SQL gives you a list of every zone pair with its trip count — could be 50,000
pairs. Instead of sorting all 50,000 to find the top 10, you keep a min-heap
of size 10. For each new pair, if it beats the weakest in the heap, it
replaces it. Total work: 50,000 comparisons instead of 50,000 × log(50,000).

**count_by + top_k in /api/zones/<id>:**
For a zone like Midtown, you fetch all its trips from the database. In one
pass you count how many trips went to each dropoff zone (count_by), then rank
the top 5 destinations (top_k). You also collect all fare amounts in the same
pass so quickselect_median can find the median without sorting them.

**quickselect_median in /api/zones/<id>:**
JFK has thousands of $52.00 flat-fare trips. A normal two-way quickselect
would keep re-partitioning those identical values and slow down to O(n²).
The three-way partition puts all $52.00 fares in the middle block and skips
them entirely in the next round.

### Task 5 — Write your report sections

**Section 3 — Algorithms**

For each of the three algorithms, write in your own words:
- What problem in this dataset made you need it
- Step-by-step pseudocode (not Python — write it out in plain English steps)
- Time complexity and why (e.g. "O(n log k) because each of the n items
  triggers at most one heap operation costing log k")
- Space complexity
- What the naive approach would be and why yours is better

**Section 4 — Insights**

Run the dashboard with real data and find three things that surprised you.
For each one:
- Write the API call or SQL query you used to find it
- Use one of Kuol's screenshots to illustrate it
- Write 2–3 sentences explaining what it means for how New York moves

Suggested starting points:
1. Filter to hour 5am vs hour 8am — how much does speed drop and what does
   that do to fare per mile?
2. Look at the top routes table — why is Upper East Side → Upper East Side
   the busiest route? What does that say about how people use taxis for short trips?
3. Filter to airport_only=1 — how does the tip percentage compare to the
   city average? Why might airport passengers tip differently?

---

# SHARED SUBMISSION CHECKLIST

Go through this together the day before the deadline.

## Code — must all work
- [ ] `python backend/algorithms.py` → prints "All algorithm self-tests passed"
- [ ] `python backend/app.py` starts without errors
- [ ] All 12 endpoints return 200 with valid JSON (test with curl commands above)
- [ ] Dashboard loads at `http://127.0.0.1:5000` and all 6 sections render
- [ ] Changing filters updates every chart

## Files — must all exist in the repo
- [ ] `data/processed/cleaning_summary.json`
- [ ] `docs/data_profile.txt`
- [ ] `docs/architecture.png`
- [ ] `docs/screenshots/dashboard_overview.png`
- [ ] `docs/screenshots/map_speed.png`
- [ ] `docs/screenshots/heatmap.png`
- [ ] `docs/screenshots/top_routes.png`
- [ ] `docs/screenshots/zone_detail.png`
- [ ] `docs/screenshots/data_quality.png`
- [ ] `README.md` has real video link and real scrum board link
- [ ] `codevibe-reports/` has one `.report.json` per team member

## Report PDF — must be assembled by team lead
- [ ] Section 1 — Dataset & cleaning (Abay)
- [ ] Section 2 — Architecture & design decisions (Alier, include architecture.png)
- [ ] Section 3 — Algorithms with pseudocode and complexity (Chol)
- [ ] Section 4 — Three insights with screenshots (Chol, use Kuol's screenshots)
- [ ] Section 5 — One reflection paragraph per person (everyone)
- [ ] 2–3 pages total, PDF format

## Submission — team lead does this
- [ ] Team participation sheet filled in and shared (comment-only for non-leads)
- [ ] GitHub has meaningful commits from all 4 members on code files
- [ ] Repo zipped
- [ ] Submitted on Canvas with GitHub link, video link, and PDF
