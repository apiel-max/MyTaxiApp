# NYC Urban Mobility Data Explorer

An interactive dashboard for exploring every yellow taxi ride in New York City
during January 2019. Filter by borough, zone, time of day, fare range, and more.
The whole page updates instantly.

**Video walkthrough:** <!-- ADD YOUR VIDEO LINK HERE before submitting -->

**Architecture diagram:** `docs/architecture.png`

**Scrum board:** <!-- ADD YOUR SCRUM BOARD LINK HERE -->

---

## What the project does

| Layer | Technology | Role |
|-------|-----------|------|
| Pipeline | Python + pandas | Cleans raw data, engineers features, builds the DB |
| Database | SQLite | Star-schema with pre-aggregated summary tables |
| Backend | Flask (Python) | REST API serving filtered aggregates and trip records |
| Frontend | HTML + CSS + JS (no frameworks) | Interactive dashboard with SVG charts and a zone map |

---

## Quick start

### 1. Clone and install

```bash
git clone <your-repo-url>
cd MyTaxiApp
pip install -r requirements.txt
```

### 2. Download the raw data

Place these three items inside `data/raw/`:

| File | Source |
|------|--------|
| `yellow_tripdata_2019-01.csv` | [NYC TLC Trip Records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) — January 2019 Yellow Taxi (convert .parquet → .csv, or adjust `RAW_CSV` in `pipeline/clean_data.py`) |
| `taxi_zone_lookup.csv` | Same TLC page → Taxi Zone Lookup Table |
| `taxi_zones/` (folder with `.shp`, `.dbf`, `.prj`, …) | Same TLC page → Taxi Zone Shapefile |

Your `data/raw/` folder should look like:

```
data/raw/
├── yellow_tripdata_2019-01.csv
├── taxi_zone_lookup.csv
└── taxi_zones/
    ├── taxi_zones.shp
    ├── taxi_zones.dbf
    └── taxi_zones.prj
```

### 3. (Optional) Make a small sample for testing

If you want to test quickly without loading 7.5 million rows:

```bash
python pipeline/make_sample.py data/raw/yellow_tripdata_2019-01.csv 0.05
# Creates data/raw/yellow_tripdata_sample.csv (≈5% of rides)
# Then edit RAW_CSV in pipeline/clean_data.py to point at the sample file
```

### 4. Run the data pipeline

```bash
# Step 1: profile the raw data (optional but informative)
python pipeline/profile_data.py

# Step 2: clean, normalize, and engineer features
python pipeline/clean_data.py

# Step 3: convert the shapefile to GeoJSON (standard library only, no GDAL needed)
python pipeline/convert_zones.py

# Step 4: build the SQLite database
python database/load_database.py           # full dataset (~2–5 min, ~2.7 GB)
# OR for a quick demo:
python database/load_database.py --sample 0.1   # 10% sample, much faster
```

### 5. Start the backend

```bash
python backend/app.py
# Dashboard is now at http://127.0.0.1:5000
```

Open your browser at **http://127.0.0.1:5000** — the Flask server also serves
the frontend, so no separate web server is needed.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MOBILITY_DB` | `data/mobility.db` | Path to the SQLite database |
| `HOST` | `127.0.0.1` | Bind address (`0.0.0.0` to expose on the network) |
| `PORT` | `5000` | Port number |
| `FLASK_DEBUG` | _(unset)_ | Set to `1` to enable Flask debug mode |

Example:

```bash
MOBILITY_DB=/data/mobility.db PORT=8080 python backend/app.py
```

---

## Project structure

```
MyTaxiApp/
├── backend/
│   ├── app.py              Flask API + static file server
│   ├── db.py               DB connection, filter parsing, WHERE-clause builder
│   └── algorithms.py       Hand-written MinHeap, top-K, count_by, quickselect
├── database/
│   ├── schema.sql          Star schema (trips fact + dimension + summary tables)
│   ├── indexes.sql         Performance indexes (applied after bulk load)
│   └── load_database.py    Builds data/mobility.db from the cleaned CSVs
├── pipeline/
│   ├── profile_data.py     Step 1: data quality report on the raw CSV
│   ├── clean_data.py       Step 2: exclusion rules, repairs, feature engineering
│   ├── convert_zones.py    Step 3: shapefile → GeoJSON (pure stdlib, no GDAL)
│   └── make_sample.py      Optional: random sample for fast local testing
├── frontend/
│   ├── index.html          Single-page dashboard
│   ├── css/style.css       All styles (light + dark mode)
│   └── js/
│       ├── main.js         Wires filters → API → charts
│       ├── api.js          fetch wrapper + number formatters
│       ├── charts.js       Hand-drawn SVG line, bar, heatmap, hbars
│       └── map.js          SVG zone map with zoom/pan and quantile colouring
├── data/
│   ├── raw/                Raw input files (git-ignored)
│   └── processed/          Cleaned CSVs, GeoJSON, cleaning_summary.json
├── docs/
│   └── screenshots/        Test screenshots for the report
├── requirements.txt
└── README.md
```

---

## API endpoints

All endpoints accept the same optional filter parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` / `end_date` | `YYYY-MM-DD` | Inclusive date range |
| `borough_id` | integer | Filter by pickup borough |
| `zone_id` | integer | Filter by pickup zone (1–265) |
| `dow` | 0–6 | Day of week (0 = Monday) |
| `hour_min` / `hour_max` | 0–23 | Hour range |
| `min_distance` / `max_distance` | float (miles) | Trip distance range |
| `min_fare` / `max_fare` | float ($) | Fare range |
| `payment_type_id` | integer | 1 = card, 2 = cash, … |
| `airport_only` | `1` | Only trips to/from JFK, LGA, EWR |

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Liveness check + total trip count |
| `GET /api/meta` | Boroughs, zones, payment types, date range |
| `GET /api/summary` | KPI headline numbers |
| `GET /api/by-hour` | Trips and speed by hour of day |
| `GET /api/by-day` | Daily totals (time series) |
| `GET /api/heatmap` | Weekday × hour grid |
| `GET /api/zone-stats` | Per-zone pickup counts and averages |
| `GET /api/top-routes?k=10` | Top-K busiest pickup → dropoff pairs |
| `GET /api/zones/<id>` | Zone detail: top destinations, median fare |
| `GET /api/trips` | Paginated, sortable trip list |
| `GET /api/data-quality` | Exclusion log and cleaning summary |
| `GET /api/zones/geojson` | GeoJSON zone shapes for the map |

---

## Algorithms (hand-written, no built-in sort/heap/Counter)

See `backend/algorithms.py` for full implementation and self-tests.

| Algorithm | Where used | Complexity |
|-----------|-----------|------------|
| **MinHeap + top_k** | Ranking the K busiest routes from thousands of zone pairs | O(n log k) time, O(k) space |
| **count_by** | Counting dropoff destinations for a zone detail panel | O(n) time, O(distinct) space |
| **Quickselect (3-way)** | Median fare per zone without sorting all fares | O(n) average time |

Run the self-tests:

```bash
python backend/algorithms.py
# All algorithm self-tests passed.
```

---

## Running on a sample (for demos or low-memory machines)

```bash
# 1. Make a 5% sample
python pipeline/make_sample.py data/raw/yellow_tripdata_2019-01.csv 0.05

# 2. Edit pipeline/clean_data.py: change RAW_CSV to point at the sample file

# 3. Run the pipeline as normal
python pipeline/clean_data.py
python pipeline/convert_zones.py
python database/load_database.py

# 4. Start the server
python backend/app.py
```
