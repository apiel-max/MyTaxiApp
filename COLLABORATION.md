# Team Collaboration Guide — NYC Urban Mobility Data Explorer

## Final Ownership Split

| Member | Role | Files | Lines |
|--------|------|-------|-------|
| **Abay Tessema** | Data Engineering | `pipeline/profile_data.py`, `pipeline/clean_data.py`, `pipeline/convert_zones.py`, `pipeline/make_sample.py`, `database/load_database.py` | ~938 |
| **Alier Akuang** | Database & API | `database/schema.sql`, `database/indexes.sql`, `backend/db.py`, `backend/app.py` (all endpoints except `/api/top-routes` and `/api/zones/<id>`) | ~704 |
| **Kuol Akech** | Frontend | `frontend/index.html`, `frontend/css/style.css`, `frontend/js/api.js`, `frontend/js/main.js` | ~1325 |
| **Chol Mach Kuol** | Algorithms & Visualisation | `backend/algorithms.py`, `frontend/js/charts.js`, `frontend/js/map.js`, `/api/top-routes` and `/api/zones/<id>` in `backend/app.py` | ~831 |

**Why this is the best split:**
- Every person owns one complete, self-contained concern — no shared file ownership, no merge conflicts
- Abay owns the full data engineering layer end-to-end including the database loader (inserting data is data engineering work)
- Alier owns the schema, indexes, DB connection layer, and all API endpoints that do not call custom algorithms
- Kuol owns the HTML structure, all CSS, the fetch/format layer (`api.js`), and the dashboard orchestrator (`main.js`)
- Chol owns the algorithm implementations, the two hand-drawn SVG chart files, and the two endpoints that call the algorithms — this keeps the assignment's "algorithm solves a real problem inside the app" requirement clearly in one person's hands
- Workload is balanced: Abay ~938, Alier ~704, Kuol ~1325, Chol ~831 lines of meaningful code

---

## Git Workflow

```bash
# 1. Each person clones the repo on their own machine
git clone <repo-url>
cd MyTaxiApp

# 2. Create your branch
git checkout -b abay/pipeline
git checkout -b alier/database
git checkout -b kuol/frontend
git checkout -b chol/algorithms

# 3. Commit often with clear messages
git add pipeline/clean_data.py
git commit -m "clean_data: add exclusion rule for zero distance"

# 4. Push and open a Pull Request to main
git push origin abay/pipeline
# Open PR on GitHub, tag one teammate to review
```

**Rules:**
- Never commit directly to `main`
- One PR per feature or milestone
- Never edit a file owned by someone else — ask them instead

---

# ABAY TESSEMA — Data Engineering

## Your files
```
pipeline/
  profile_data.py     ← Step 1: inspect the raw data, save docs/data_profile.txt
  clean_data.py       ← Step 2: clean, normalize, engineer features
  convert_zones.py    ← Step 3: shapefile → GeoJSON (pure stdlib, no GDAL)
  make_sample.py      ← helper: random sample for fast testing
database/
  load_database.py    ← Step 4: build data/mobility.db from the cleaned CSVs
```

## Step-by-step tasks

### 1. Run the profiler first
```bash
python pipeline/profile_data.py
# Reads data/raw/yellow_tripdata_2019-01.csv
# Prints missing values, duplicates, outliers, categorical codes
# Saves output to docs/data_profile.txt — commit this file
```

### 2. Understand clean_data.py before touching it

The script runs four functions in order inside `main()`:

**`load_raw()`** — reads the CSV with pandas, adds a `source_row` column so
any removed ride can be traced back to its line in the raw file.

**`apply_exclusion_rules(df)`** — each rule is a `(name, boolean_mask)` pair.
A ride is excluded by the FIRST rule it breaks, so every excluded ride has
exactly one reason and the counts add up to the total removed:

```python
rules = [
    ("pickup_outside_jan_2019",    (df["tpep_pickup_datetime"] < MONTH_START) | ...),
    ("dropoff_not_after_pickup",   duration_min <= 0),
    ("duration_over_6h",           duration_min > MAX_DURATION_MIN),
    ("zero_distance",              df["trip_distance"] <= 0),
    ("distance_over_100mi",        df["trip_distance"] > MAX_DISTANCE_MI),
    ("fare_zero_or_negative",      df["fare_amount"] <= 0),
    ("fare_over_500",              df["fare_amount"] > MAX_FARE),
    ("negative_charge_component",  negative_component),
    ("speed_over_80mph",           speed > MAX_SPEED_MPH),
]
```

Returns `(kept_df, excluded_df, counts_dict)`.

**`repair_and_normalize(df, lookup)`** — fixes small problems in rides we keep:
- `congestion_surcharge` NaN → 0.0 (the surcharge only started in Feb 2019)
- `passenger_count == 0` → NULL (data-entry habit, not an empty cab)
- `RatecodeID == 99` → NULL (not in the TLC data dictionary)
- Rounds all money columns to 2 decimal places
- Renames columns to match the database schema (`VendorID` → `vendor_id`, etc.)

**`add_features(df)`** — adds 9 derived columns:

| Column | Formula | Why it matters |
|--------|---------|----------------|
| `trip_duration_min` | `(dropoff - pickup).total_seconds() / 60` | Base for speed calculation |
| `avg_speed_mph` | `distance / (duration_min / 60)` | Direct proxy for traffic congestion |
| `fare_per_mile` | `fare / distance` (NULL if distance < 0.25 mi) | Price efficiency metric |
| `tip_pct` | `tip / fare * 100` (card payments only) | Tipping behaviour analysis |
| `pickup_hour` | `pickup_datetime.hour` | Rush hour patterns |
| `pickup_dow` | `pickup_datetime.dayofweek` (0=Mon) | Weekday vs weekend patterns |
| `is_weekend` | `dow >= 5` | Weekend flag |
| `time_of_day` | cut into 5 bins: night/morning_rush/midday/evening_rush/evening | Categorical time bucket |
| `is_airport_trip` | pickup or dropoff zone in {1, 132, 138} | JFK/LGA/EWR flag |

### 3. Understand convert_zones.py

The TLC ships a binary ESRI shapefile in NY State Plane feet — not longitude/latitude.
This script converts it to GeoJSON using only `struct` and `math` from the standard library.

Key functions:
- `state_plane_to_lonlat(x_ft, y_ft)` — inverse Lambert Conformal Conic projection (Snyder 1987)
- `read_dbf(path)` — reads the `.dbf` attribute table (LocationID, zone name, borough)
- `read_shp(path)` — reads the `.shp` polygon geometry
- `rings_to_geometry(rings)` — converts rings to GeoJSON, fixes winding order (shapefile = clockwise outer, GeoJSON = counter-clockwise outer)

```bash
python pipeline/convert_zones.py
# Output: data/processed/taxi_zones.geojson
```

### 4. Understand load_database.py

Builds `data/mobility.db` from the cleaned CSVs. Runs in this order:

```python
# 1. Create all tables
con.executescript(SCHEMA_SQL.read_text())

# 2. Insert dimension data
load_dimensions(con)   # boroughs, zones + GeoJSON shapes, vendors, rate codes, payment types

# 3. Bulk-insert trips in 250k-row chunks (avoids loading 7.5M rows into memory at once)
load_trips(con, sample)

# 4. Insert the exclusion log
load_excluded(con)

# 5. Build the two summary tables from the trips table
build_summaries(con)   # GROUP BY queries — much faster than scanning trips every request

# 6. Apply all indexes AFTER bulk insert (5x faster than inserting with indexes active)
con.executescript(INDEXES_SQL.read_text())

# 7. Verify: foreign keys, row counts, summary tables add up to trips
verify(con, n_trips)
```

```bash
python database/load_database.py               # full dataset (~3-5 min, ~2.7 GB)
python database/load_database.py --sample 0.1  # 10% sample, ~30 seconds
```

### 5. Verify your outputs

```python
import pandas as pd, json, sqlite3

# Check clean trips
df = pd.read_csv("data/processed/trips_clean.csv")
assert df.shape[1] == 29, "wrong column count"
assert (df["trip_distance"] > 0).all()
assert (df["fare_amount"] > 0).all()
assert (df["avg_speed_mph"] <= 80).all()
print(f"Clean trips: {len(df):,} rows")

# Check GeoJSON
geo = json.loads(open("data/processed/taxi_zones.geojson").read())
assert len(geo["features"]) >= 260, "too few zones"
print(f"Zones: {len(geo['features'])}")

# Check database
con = sqlite3.connect("data/mobility.db")
n = con.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
n_zdhs = con.execute("SELECT SUM(trip_count) FROM zone_date_hour_stats").fetchone()[0]
assert n == n_zdhs, "summary table does not add up"
print(f"Database trips: {n:,}")
con.close()
```

## Extra deliverable
Upload `yellow_tripdata_2019-01.csv`, `taxi_zone_lookup.csv`, and the `taxi_zones/`
folder to Google Drive and share the link with the team so everyone can run the
pipeline on their own machine.

## Report — Section 1 (400–500 words)
1. What the dataset is: NYC TLC yellow taxi, January 2019, ~7.5M rows
2. Data challenges found — use the exact numbers from `docs/data_profile.txt`
3. Your cleaning assumptions — justify each threshold (why 6h max duration? why 80mph?)
4. One unexpected observation (e.g. `congestion_surcharge` was always NULL in Jan 2019 because the surcharge started in Feb 2019)

---

# ALIER AKUANG — Database & API

## Your files
```
database/
  schema.sql      ← all table definitions (star schema)
  indexes.sql     ← 17 performance indexes, applied after bulk insert
backend/
  db.py           ← DB connection, filter parsing, WHERE-clause builder
  app.py          ← all Flask endpoints EXCEPT /api/top-routes and /api/zones/<id>
README.md
requirements.txt
```

## Step-by-step tasks

### 1. Understand schema.sql

The schema is a **star schema**: one fact table (`trips`) surrounded by
dimension tables. Every string that would repeat millions of times is stored
once in a dimension table and referenced by a small integer ID.

```
Dimension tables (small, rarely change):
  boroughs       (borough_id, name)
  zones          (zone_id, zone_name, borough_id, service_zone, is_airport, geometry)
  vendors        (vendor_id, name)
  rate_codes     (rate_code_id, description)
  payment_types  (payment_type_id, description)

Fact table (one row per cleaned ride):
  trips          → references all five dimension tables via foreign keys

Transparency tables:
  exclusion_reasons   (reason_code, description)
  excluded_records    ← every removed ride with its reason

Summary tables (pre-aggregated, rebuilt by load_database.py):
  zone_date_hour_stats   ← date × zone × hour  (~100k rows)
  route_date_stats       ← date × pickup zone × dropoff zone
```

The summary tables store **SUMS and COUNTS, never averages**. This means any
combination of rows can be re-aggregated correctly:
```sql
-- Correct: re-sum the sums
SELECT SUM(sum_distance) / (SUM(sum_duration_min) / 60.0) AS avg_speed
FROM zone_date_hour_stats WHERE pickup_hour BETWEEN 7 AND 9;

-- Wrong: average of averages gives wrong result when group sizes differ
SELECT AVG(avg_speed) FROM zone_date_hour_stats WHERE pickup_hour BETWEEN 7 AND 9;
```

### 2. Understand db.py

Two responsibilities:

**Database connection** — one read-only SQLite connection per Flask request,
opened lazily on first use, closed automatically when the request ends:

```python
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
        g.db.row_factory = sqlite3.Row   # rows behave like dicts
    return g.db
```

**Filter parsing + WHERE clause builder** — `parse_filters(request.args)`
validates every query parameter and returns a typed dict. `where_clause(f)`
turns that dict into a safe SQL fragment. User input **never** goes into SQL
text — always as `?` parameters:

```python
# Safe — user value goes into params list, never into the SQL string
parts.append(f"{p}pickup_hour >= ?")
params.append(f["hour_min"])

# Never do this — SQL injection risk
parts.append(f"pickup_hour >= {f['hour_min']}")
```

`can_use(filters, allowed)` decides which table to query:
```python
ZONE_STATS_FILTERS = {"start_date","end_date","borough_id","zone_id","dow","hour_min","hour_max"}

if can_use(filters, ZONE_STATS_FILTERS):
    # zone_date_hour_stats: ~100k rows, fast
else:
    # trips: 7.5M rows, slower but handles all filters
```

### 3. Your endpoints in app.py

You own all endpoints except `/api/top-routes` and `/api/zones/<id>` (those are Chol's).
The pattern every endpoint follows is the same:

```python
@app.get("/api/summary")
def summary():
    f = parse_filters(request.args)           # 1. parse + validate filters
    table, agg, where, params = source_for(f) # 2. choose fast or full table
    row = query_one(f"SELECT {agg} FROM {table} {where}", params)  # 3. query
    return jsonify({**metrics(row), "source": table})              # 4. respond
```

Your endpoints and what they return:

| Endpoint | Returns |
|----------|---------|
| `GET /api/health` | `{"status": "ok", "trips_in_database": n}` |
| `GET /api/meta` | boroughs, zones, payment types, date range |
| `GET /api/zones/geojson` | GeoJSON FeatureCollection (cached in memory after first call) |
| `GET /api/summary` | KPI headline numbers (trips, avg fare, avg speed, etc.) |
| `GET /api/by-hour` | list of 24 rows, one per hour |
| `GET /api/heatmap` | 7×24 grid rows with `trips_per_day` normalised by weekday count |
| `GET /api/by-day` | one row per calendar date |
| `GET /api/zone-stats` | one row per pickup zone (colours the map) |
| `GET /api/trips` | paginated, sortable trip list |
| `GET /api/data-quality` | exclusion log + cleaning summary |

### 4. Test every endpoint

```bash
python backend/app.py &

curl -s http://127.0.0.1:5000/api/health | python3 -m json.tool
curl -s http://127.0.0.1:5000/api/meta | python3 -m json.tool
curl -s "http://127.0.0.1:5000/api/summary" | python3 -m json.tool
curl -s "http://127.0.0.1:5000/api/summary?borough_id=1&hour_min=7&hour_max=9" | python3 -m json.tool
curl -s "http://127.0.0.1:5000/api/by-hour" | python3 -m json.tool
curl -s "http://127.0.0.1:5000/api/heatmap" | python3 -m json.tool
curl -s "http://127.0.0.1:5000/api/by-day" | python3 -m json.tool
curl -s "http://127.0.0.1:5000/api/zone-stats" | python3 -m json.tool
curl -s "http://127.0.0.1:5000/api/trips?sort=fare_amount&order=desc" | python3 -m json.tool
curl -s "http://127.0.0.1:5000/api/data-quality" | python3 -m json.tool
```

Every endpoint must return valid JSON with a 200 status. A 400 means a bad
filter value. A 500 means the database is missing — run Abay's pipeline first.

### 5. README.md and requirements.txt

Keep `README.md` up to date as the project evolves. The video link and scrum
board link must be filled in before submission. `requirements.txt` must list
every Python package needed to run the project:

```
flask>=3.0
pandas>=2.0
numpy>=1.24
```

## Extra deliverables
- Create the GitHub repository, invite all teammates as collaborators
- Set up branch protection on `main` (require at least one PR review before merge)
- Draw the architecture diagram on Draw.io: raw data → pipeline → SQLite → Flask API → browser
  Save as `docs/architecture.png` and commit it

## Report — Section 2 (400–500 words)
1. Include `docs/architecture.png`
2. Why SQLite: single file, no server process, easy to share, fast enough for a read-only dashboard
3. Why a star schema: a borough name stored once vs repeated 7.5M times saves ~200MB and makes joins fast
4. Why two summary tables: ~50MB extra storage buys queries that run in milliseconds instead of seconds
5. Why indexes are applied after bulk insert: inserting 7.5M rows with indexes active is ~5x slower

---

# KUOL AKECH — Frontend

## Your files
```
frontend/
  index.html        ← single-page dashboard structure and all HTML sections
  css/style.css     ← all styles, light + dark mode, no external CSS
  js/api.js         ← fetch wrapper, request cancellation, number formatters
  js/main.js        ← wires filters → API calls → chart renders
```

Chol owns `js/charts.js` and `js/map.js`. Your files import from them —
coordinate with Chol on the public function signatures but never edit his files.

## Step-by-step tasks

### 1. Understand index.html

One HTML file, no framework. The structure maps directly to the dashboard sections:

```html
<header class="masthead">        ← title + KPI meter (trips, fare, speed, tip)
<form class="filters" id="filters">  ← all filter controls; main.js reads with FormData
<main id="main">
  <section id="map-section">     ← Chol's map.js renders the SVG zone map here
  <section id="speed-section">   ← hourly speed + fare/mile line charts
  <section id="rhythm-section">  ← weekday×hour heatmap + daily bar chart
  <section id="routes-section">  ← top routes table (Chol's endpoint)
  <section id="trips-section">   ← paginated, sortable trip explorer
  <section id="quality-section"> ← data quality exclusion log
</main>
```

Every chart container is an empty `<div>` or `<figure>` — Chol's chart
functions write SVG into them at runtime. Never put chart markup in the HTML.

### 2. Understand css/style.css

All colours are CSS custom properties. Never hardcode a colour value anywhere:

```css
:root {
  --page:      #e9ebee;   /* page background */
  --surface:   #fcfcfb;   /* card / panel background */
  --ink:       #15171a;   /* primary text */
  --ink-2:     #5a5f6a;   /* secondary text */
  --border:    #d8dade;   /* dividers */
  --taxi:      #f6b100;   /* taxi yellow — meter only */
  --series-1:  #2a78d6;   /* blue — weekdays, primary data series */
  --series-2:  #eb6834;   /* orange — weekends, congestion */
  --no-data:   #e4e6ea;   /* zones with no rides */
}

@media (prefers-color-scheme: dark) {
  :root {
    --page:    #1a1c20;
    --surface: #23262c;
    /* ... override every variable here */
  }
}
```

### 3. Understand api.js

Two exports: `get()` and `fmt`.

**`get(path, filters, extra, channel)`** — fetches a JSON endpoint. Cancels
any in-flight request on the same channel so fast filter changes never let a
slow stale response overwrite a newer one:

```javascript
// Each section uses its own channel so they cancel independently
const { data, ms } = await get("summary", filters);
const { data } = await get("zones/161", filters, {}, "zone-detail");
```

**`fmt`** — all number formatters. Always use these, never format inline:

```javascript
fmt.int(7300000)        // "7,300,000"
fmt.money(12.5)         // "$12.50"
fmt.mph(23.4)           // "23.4 mph"
fmt.miles(2.1)          // "2.10 mi"
fmt.minutes(14.3)       // "14.3 min"
fmt.pct(18.5)           // "18.5%"
fmt.hour(8)             // "8 am"
fmt.date("2019-01-15")  // "Tue, Jan 15"
```

**`esc(value)`** — always use this before putting any API string into innerHTML:

```javascript
// Correct — prevents XSS
tbody.innerHTML = `<td>${esc(row.zone_name)}</td>`;

// Wrong — XSS risk if zone_name contains < > & " '
tbody.innerHTML = `<td>${row.zone_name}</td>`;
```

### 4. Understand main.js

The orchestrator. Key functions:

```javascript
readFilters()          // reads the <form> with FormData → returns filter object
populateFilters(meta)  // fills borough/zone/payment <select> from /api/meta
refresh()              // calls every load* function with current filters

loadMeter(f)           // GET /api/summary → updates the 5 KPI values in the header
loadMap(f)             // GET /api/zone-stats → calls state.map.update() (Chol's code)
loadZoneDetail(f)      // GET /api/zones/<id> → builds the zone side panel (Chol's endpoint)
loadHourly(f)          // GET /api/by-hour → calls lineChart() twice (Chol's code)
loadRhythm(f)          // GET /api/heatmap + /api/by-day → calls heatmap() + barChart()
loadRoutes(f)          // GET /api/top-routes → builds the routes table
loadTrips(f)           // GET /api/trips → builds the paginated trip table
loadQuality()          // GET /api/data-quality → builds the exclusion bar charts
```

The `section(panelId, work)` helper wraps every load function. It sets
`aria-busy` while loading and catches errors per-section so one slow query
never breaks the whole page:

```javascript
async function section(panelId, work) {
  const panel = document.getElementById(panelId);
  panel?.setAttribute("aria-busy", "true");
  try {
    await work();
  } catch (err) {
    if (err.name === "AbortError") return;
    // show error message inside the panel only
  } finally {
    panel?.setAttribute("aria-busy", "false");
  }
}
```

### 5. How to test without the backend

Open `frontend/index.html` directly in a browser — it will show a connection
error because there is no API. That is fine for layout and style work.

To test with real data:
```bash
python backend/app.py
# Open http://127.0.0.1:5000
# Use browser DevTools → Network tab to watch every API call as you change filters
```

### 6. Common tasks

**Add a new filter:**
1. Add `<input>` or `<select>` to `index.html` with a `name` attribute
2. `readFilters()` picks it up automatically via `FormData` — no JS change needed
3. Ask Alier to add the parameter to `parse_filters()` in `backend/db.py`

**Change a colour:** edit the CSS variable in `:root` — one change, affects everything.

**Change a number format:** edit the `fmt` object in `api.js` — one change, affects the whole dashboard.

## Extra deliverable
Take these screenshots of the running dashboard and save to `docs/screenshots/`:

| Filename | What to show |
|----------|-------------|
| `dashboard_overview.png` | Full dashboard, no filters applied |
| `map_speed.png` | Map shaded by average speed |
| `heatmap.png` | Heatmap showing the Thu/Fri evening peak |
| `top_routes.png` | Top routes table |
| `zone_detail.png` | Zone side panel after clicking a zone on the map |
| `data_quality.png` | Data quality section |

Record and edit the 5-minute video walkthrough:
- 0:00–0:30 — what the project does and why
- 0:30–2:00 — live demo (show filters changing every chart)
- 2:00–3:30 — walk through the architecture diagram (Alier explains)
- 3:30–4:30 — show the algorithm code (Chol explains)
- 4:30–5:00 — each person says one sentence about their contribution

---

# CHOL MACH KUOL — Algorithms & Visualisation

## Your files
```
backend/
  algorithms.py   ← MinHeap, top_k, count_by, quickselect_median (no built-ins)
  app.py          ← /api/top-routes and /api/zones/<id> only
frontend/js/
  charts.js       ← hand-drawn SVG: lineChart, barChart, heatmap, hbars
  map.js          ← SVG zone map with zoom, pan, quantile colouring
```

## Step-by-step tasks

### 1. Understand algorithms.py

Three hand-written data structures — no `heapq`, no `Counter`, no `sort()`:

---

**MinHeap + top_k — O(n log k)**

A binary heap stored in a plain list. For item at index `i`:
- parent = `(i - 1) // 2`
- left child = `2i + 1`
- right child = `2i + 2`

The smallest item (by `key`) is always at index 0. `top_k` keeps a min-heap
of the best `k` seen so far. Each new item needs only one comparison with the
root — if it beats the weakest of the current top-k, it replaces it:

```python
def top_k(items, k, key):
    heap = MinHeap(key=key)
    for item in items:
        if len(heap) < k:
            heap.push(item)                      # O(log k)
        elif key(item) > key(heap.peek()):
            heap.replace_top(item)               # O(log k)
    # pop smallest-first, fill result backwards to get largest-first
    result = [None] * len(heap)
    for i in range(len(result) - 1, -1, -1):
        result[i] = heap.pop()
    return result
```

Used by `/api/top-routes` to rank ~50,000 zone pairs in O(n log k) instead
of O(n log n) for a full sort. With k=10 and n=50,000 that is ~5x fewer
comparisons.

---

**count_by — O(n)**

Manual hash-map grouping using a plain dict. Replaces `collections.Counter`:

```python
def count_by(values):
    counts = {}
    for v in values:
        if v in counts:
            counts[v] += 1
        else:
            counts[v] = 1
    return counts
```

Used by `/api/zones/<id>` to count how many trips went to each dropoff zone
in a single pass over the rows.

---

**quickselect_median — O(n) average**

Finds the median without sorting. Uses three-way partitioning (Dutch national
flag) because taxi fares have huge runs of identical values (e.g. the $52.00
JFK flat fare). A normal two-way partition keeps re-scanning those duplicates
and degrades to O(n²); grouping them in one block discards all of them in a
single step:

```python
# Three-way partition of a[lo..hi] around pivot:
lt, i, gt = lo, lo, hi
while i <= gt:
    if a[i] < pivot:
        a[lt], a[i] = a[i], a[lt]
        lt += 1; i += 1
    elif a[i] > pivot:
        a[i], a[gt] = a[gt], a[i]
        gt -= 1
    else:
        i += 1
# a[lo..lt-1] < pivot, a[lt..gt] == pivot, a[gt+1..hi] > pivot
```

Used by `/api/zones/<id>` to return the median fare for a zone without
sorting all its fares.

Run the self-tests at any time:
```bash
python backend/algorithms.py
# All algorithm self-tests passed.
```

### 2. Your two endpoints in app.py

**`GET /api/top-routes`**

SQL groups all zone pairs and sums their trips. Your `top_k` then ranks the
best k without sorting everything:

```python
@app.get("/api/top-routes")
def top_routes():
    f = parse_filters(request.args)
    k = min(max(int(request.args.get("k", 10)), 1), 50)
    # ... choose table based on filters ...
    pairs = query("SELECT pickup_zone_id AS pu, dropoff_zone_id AS dz, "
                  "COUNT(*) AS n, ... FROM ... GROUP BY pu, dz", params)
    # Filter out unknown zones 264/265 unless caller asks for them
    if request.args.get("include_unknown") not in ("1", "true"):
        pairs = [r for r in pairs if r["pu"] not in UNKNOWN_ZONES
                                  and r["dz"] not in UNKNOWN_ZONES]
    best = top_k(pairs, k, key=lambda r: (r["n"], -r["pu"], -r["dz"]))
    names = {r["zone_id"]: r["zone_name"] for r in query("SELECT zone_id, zone_name FROM zones")}
    return jsonify({"distinct_routes_ranked": len(pairs), "routes": [...]})
```

**`GET /api/zones/<id>`**

One pass over the trip rows builds everything the zone detail panel needs:

```python
@app.get("/api/zones/<int:zone_id>")
def zone_detail(zone_id):
    # ... fetch zone metadata, build where clause ...
    rows = get_db().execute(
        "SELECT dropoff_zone_id, fare_amount, trip_distance, "
        "trip_duration_min, total_amount, tip_pct FROM trips WHERE ...", params
    ).fetchall()

    dropoffs, fares = [], []
    totals = {"n": 0, "dist": 0.0, "dur": 0.0, "fare": 0.0,
              "total": 0.0, "tip_sum": 0.0, "tip_n": 0}
    for dz, fare, dist, dur, total, tip_pct in rows:
        dropoffs.append(dz)
        fares.append(fare)
        totals["n"] += 1
        totals["dist"] += dist
        # ... accumulate other totals ...

    destinations = top_k(list(count_by(dropoffs).items()), 5,
                         key=lambda kv: (kv[1], -kv[0]))
    return jsonify({
        "zone": zone,
        **metrics(totals),
        "median_fare": quickselect_median(fares),
        "top_destinations": [...],
    })
```

### 3. Understand charts.js

Four hand-drawn SVG chart functions — no Chart.js, no D3:

```javascript
lineChart(container, opts)          // speed and fare/mile by hour
barChart(container, opts)           // daily trip counts
heatmap(container, cells, opts)     // weekday × hour grid (HTML buttons, keyboard-accessible)
hbars(container, items)             // horizontal bar list (destinations, quality log)
```

All chart functions follow the same pattern:
1. `frame(container, height, margin)` — clear the container, create the SVG element
2. `niceTicks(min, max)` — calculate clean axis values (1, 2, 5 × 10^n steps)
3. Draw grid lines and axis labels as SVG `<line>` and `<text>` elements
4. Draw data marks (`<path>` for lines and bars, `<button>` for heatmap cells)
5. Add a transparent hit layer for hover/tooltip interaction

`lineChart` returns `{ highlight(index), clear() }` so two charts can share
a crosshair — hovering over the speed chart also highlights the same hour on
the fare-per-mile chart.

### 4. Understand map.js

SVG zone map with zoom, pan, and quantile colouring.

**Projection** — equirectangular scaled by cos(40.7°) to avoid a stretched city:
```javascript
const KX = Math.cos((40.7 * Math.PI) / 180);
const project = ([lon, lat]) => [(lon + 74.3) * KX * 1000, (41.0 - lat) * 1000];
```

**Zoom/pan** — changes the SVG `viewBox`, not element positions. This means
all the zone paths stay at fixed coordinates; only the visible window moves:
```javascript
function zoomAt(factor, cx, cy) {
    const w = Math.min(home.w * 1.5, Math.max(home.w / 25, view.w * factor));
    view = { x: cx - ((cx - view.x) / view.w) * w, ... };
    svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.w} ${view.h}`);
}
```

**Quantile colouring** — equal number of zones per colour step, not equal
value ranges. Pickup counts are extremely skewed (Midtown has thousands of
times more rides than most of Queens), so equal-width steps would paint
almost every zone the lightest colour:
```javascript
const k = BLUE_RAMP.length;   // 7 colour steps
const breaks = [];
for (let i = 1; i < k; i++)
    breaks.push(sorted[Math.floor((i / k) * (sorted.length - 1))]);
```

### 5. Test your part

```bash
# Test algorithms in isolation
python backend/algorithms.py

# Test your two endpoints
python backend/app.py &
curl "http://127.0.0.1:5000/api/top-routes?k=5"
curl "http://127.0.0.1:5000/api/zones/161"    # Midtown Center
curl "http://127.0.0.1:5000/api/zones/132"    # JFK Airport

# Open the dashboard and check the map, charts, and routes table render
open http://127.0.0.1:5000
```

## Report — Section 3 (400–500 words)

For each of the three algorithms write:
- What problem it solves in this specific dataset
- Pseudocode (written out step by step, not copied from the Python)
- Time and space complexity with justification
- Why you chose it over the obvious alternative

Example structure for top_k:
```
Problem: rank the K busiest routes from ~50,000 zone pairs
Naive approach: sort all pairs → O(n log n) time, O(n) space
Better approach: min-heap of size k → O(n log k) time, O(k) space
With k=10, n=50,000: log₂(10) ≈ 3.3 vs log₂(50,000) ≈ 15.6 → ~5x fewer comparisons

Pseudocode:
  heap ← empty min-heap of capacity k
  for each route r in all_routes:
      if heap.size < k:
          heap.push(r)
      else if r.trips > heap.minimum.trips:
          heap.replace_minimum(r)
  return heap contents sorted largest-first
```

## Report — Section 4 (400–500 words)

Derive 3 insights from the actual data. For each:
- The API call or SQL query that produced it
- A screenshot from Kuol's `docs/screenshots/` folder
- What it means for urban mobility

Suggested insights:
1. Speed drops from ~23 mph at 5 am to ~11 mph at 8 am — what does that cost riders in fare per mile?
2. Upper East Side → Upper East Side is the single busiest route — what does that say about short local trips?
3. Card tip % averages ~18% overall but drops for airport trips — why might that be?

---

# NEW FOR EVERYONE

- Write **one paragraph** for **Section 5 (Reflection)** covering your personal technical challenges and what you would do differently
- Present your own part in the video (see Kuol's section for the structure)
- Test the full project from scratch on your own laptop before the submission deadline:

```bash
git checkout main && git pull
pip install -r requirements.txt
python pipeline/profile_data.py
python pipeline/clean_data.py
python pipeline/convert_zones.py
python database/load_database.py --sample 0.1
python backend/app.py
# open http://127.0.0.1:5000 and check every section loads
```

---

# SHARED SUBMISSION CHECKLIST

## Code
- [ ] `python backend/algorithms.py` prints "All algorithm self-tests passed" (Chol)
- [ ] All 12 API endpoints return valid JSON (Alier + Chol)
- [ ] Dashboard loads and all 6 sections render correctly (Kuol)
- [ ] Filters change every chart correctly (Kuol)
- [ ] `data/mobility.db` built and verified — FK check passes, summary tables add up (Abay)

## Files that must exist before submission
- [ ] `data/processed/taxi_zones.geojson` (Abay)
- [ ] `data/processed/cleaning_summary.json` (Abay)
- [ ] `docs/data_profile.txt` (Abay)
- [ ] `docs/architecture.png` (Alier)
- [ ] `docs/screenshots/` — at least 6 screenshots (Kuol)
- [ ] `README.md` — video link and scrum board link filled in (Alier)
- [ ] `codevibe-reports/<name>.report.json` — one per team member (everyone)

## Report PDF (team lead assembles)
- [ ] Section 1 — Dataset & cleaning (Abay)
- [ ] Section 2 — Architecture & design (Alier)
- [ ] Section 3 — Algorithms (Chol)
- [ ] Section 4 — Insights with screenshots (Chol)
- [ ] Section 5 — Reflection (one paragraph each)

## Submission
- [ ] Team participation sheet completed and linked (team lead)
- [ ] GitHub commit history shows meaningful commits from all 4 members
- [ ] Repo zipped and submitted with GitHub link and video link
