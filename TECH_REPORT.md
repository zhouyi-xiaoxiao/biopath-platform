# BioPath MVP Technical Report

## 1. Overview

BioPath is a lightweight optimization tool that recommends trap locations on a grid map. It
minimizes average walking distance to the nearest trap using bio-inspired search principles.
The MVP accepts ASCII maps, generates candidate trap locations, solves a greedy placement
problem, and outputs metrics, plots, and reports. A local web UI provides visual interaction.

## 2. Architecture

- Core map parsing and data model: `biopath/mapio.py`
- Candidate generation: `biopath/candidates.py`
- Objective functions and metrics: `biopath/objective.py`
- Greedy optimizer with optional local swap: `biopath/optimizer.py`
- Reporting and visualization: `biopath/report.py`, `biopath/viz.py`
- CLI entry point: `biopath/cli.py`
- Local web UI server and assets: `biopath/web.py`, `biopath/web/`

## 3. Data Model

The system uses a `GridMap` dataclass with:

- `ascii`: list of strings with `.` for walkable cells and `#` for obstacles.
- `cell_size_m`: meters per grid cell.
- `weights` (optional): same shape as `ascii`, with non-negative values for walkable cells.
  Obstacles must be `0` or `null`. When omitted, all walkable cells have weight `1.0`.
- Derived fields: height, width, walkable mask, walkable count, and weight totals.

Parsing is implemented in `load_map_data` and `load_map` in `biopath/mapio.py`.

## 4. Optimization Algorithms

### 4.1 Distance Map (Multi-source BFS)

Distances are computed via multi-source breadth-first search on the 4-neighborhood. All
traps are enqueued as sources with distance `0`, and distances propagate through walkable
cells in increments of `cell_size_m`. This yields the shortest-path distance to the nearest
trap for every cell. Implementation: `compute_distance_map` in `biopath/objective.py`.

Complexity: `O(H * W)` per distance map, where `H` and `W` are grid height and width.

### 4.2 Objective Functions

- Mean distance: average of all walkable cell distances.
- Weighted mean distance: average weighted by cell weights.

Implementation: `mean_distance_to_traps` and `weighted_mean_distance_to_traps` in
`biopath/objective.py`.

### 4.3 Greedy Placement

The optimizer selects traps iteratively. At each step, it evaluates all remaining candidates
and chooses the one that minimizes the objective with the current set. Optional local
improvement attempts single swaps to further reduce the objective.

Implementation: `greedy_optimize` in `biopath/optimizer.py`.

Complexity: `O(K * C * H * W)` for greedy selection where `K` is the trap count and `C` is
candidate count. Local improvement adds `O(S * C * H * W)` where `S` is the number of swaps.

## 5. Metrics

The MVP reports:

- Mean distance
- Weighted mean distance
- Max distance
- P95 distance
- Optional coverage within a user-defined radius (unweighted and weighted)

Implementation: `distance_metrics` in `biopath/objective.py`.

## 6. Web UI Implementation

### 6.1 Server

`biopath/web.py` runs a local HTTP server using Python standard library modules. Endpoints:

- `GET /api/samples`: lists sample maps from `tests/fixtures`
- `GET /api/sample?name=...`: returns the JSON map
- `POST /api/solve`: runs optimization on a provided map JSON

The server uses `load_map_data`, candidate rules, and `greedy_optimize` to compute traps,
then returns metrics and a serialized distance map for visualization.

### 6.2 Frontend

`biopath/web/index.html`, `app.css`, and `app.js` provide a two-panel UI with:

- Map preview canvas and legend
- Map builder to create blank grids, edit metadata, and paint obstacles or weights
- Solver controls (k, objective, candidate rules, coverage radius)
- Results panel with metrics and trap list
- One-click export of map and results JSON

The heatmap renders directly on a canvas by mapping distance values to an HSL color scale,
and traps are drawn as red cross markers.

## 7. Validation and Error Handling

- Map input validation: shape, allowed characters, numeric weights.
- Parameter validation: non-negative counts, valid objective names.
- Unreachable cells: objective returns infinity; the UI renders unreachable cells in gray.

Errors are returned as JSON with an `error` field in the web API and surfaced in the UI.

## 8. Web UI Usage

1. Start the server: `python3 -m biopath.web --port 8000`.
2. Open `http://127.0.0.1:8000` in a browser.
3. Use **Map Input** to load a sample or upload a JSON map, or use **Map Builder** to:
   - Create a blank grid and set name/cell size.
   - Paint obstacles, walkable cells, or custom weights on the canvas.
4. Configure solver settings (k, objective, candidate rule).
5. Click **Run Optimization** to generate traps and metrics.
6. Download JSON via **Download map/results** when needed.

## 9. Limitations and Next Steps

- Greedy optimization is fast but not globally optimal; consider simulated annealing or
  integer programming for larger maps.
- Real-world geometry could be imported from GIS formats rather than ASCII grids.
- Multi-objective extensions (cost, accessibility, regulatory constraints) can be added.
- Add authentication and job queueing if deployed beyond local use.
