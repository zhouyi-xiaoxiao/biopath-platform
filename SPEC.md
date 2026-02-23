# BioPath MVP Spec

## Inputs

- JSON map with `name`, `cell_size_m`, and `ascii` (list of strings).
- Optional `weights` list of lists (same shape as `ascii`) with non-negative numbers for
  walkable cells. Obstacles should be `0` or `null`.
- `#` indicates obstacles and `.` indicates walkable cells.

## Candidates

- `all_walkable`: every walkable cell is eligible.
- `adjacent_to_wall`: walkable cells with at least `min_wall_neighbors` adjacent wall cells (4-neighborhood). Out-of-bounds counts as a wall.

## Objective

- Mean shortest-path distance from each walkable cell to the nearest trap, or a
  weighted mean when `weights` are provided and the `weighted_mean` objective is used.
- Distances are computed via multi-source BFS on a 4-neighborhood.
- If any walkable cell is unreachable from all traps, the objective is infinite.

## Metrics

- Mean, weighted mean, max, and p95 distance summaries.
- Optional coverage within a user-defined radius (both unweighted and weighted).

## Optimizer

- Greedy selection of `K` traps that minimize the objective.
- Optional local improvement: swap an in-set trap with an out-of-set candidate if it improves the objective.

## Visualization

- Distance heatmap with trap overlay saved to PNG.

## Reporting

- Markdown summary with trap list and optional image link.
