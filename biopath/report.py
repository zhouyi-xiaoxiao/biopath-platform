"""Report generation for BioPath."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable, Tuple

from .mapio import GridMap


def build_report(
    grid_map: GridMap,
    traps: Iterable[Tuple[int, int]],
    objective_value: float,
    objective_name: str,
    metrics: dict[str, float | None],
    coverage_radius_m: float | None = None,
    image_path: str | None = None,
) -> str:
    trap_list = list(traps)

    def format_metric(value: float | None) -> str:
        if value is None:
            return "n/a"
        if math.isinf(value):
            return "inf"
        return f"{value:.3f}"

    def format_ratio(value: float | None) -> str:
        if value is None:
            return "n/a"
        if math.isinf(value):
            return "inf"
        return f"{value * 100:.1f}%"

    lines = [
        f"# BioPath Report: {grid_map.name}",
        "",
        f"- Cell size (m): {grid_map.cell_size_m}",
        f"- Walkable cells: {grid_map.walkable_count}",
        f"- Trap count: {len(trap_list)}",
        f"- Objective ({objective_name}): {format_metric(objective_value)}",
        f"- Mean distance (m): {format_metric(metrics.get('mean_distance_m'))}",
        f"- Weighted mean distance (m): {format_metric(metrics.get('weighted_mean_distance_m'))}",
        f"- Max distance (m): {format_metric(metrics.get('max_distance_m'))}",
        f"- P95 distance (m): {format_metric(metrics.get('p95_distance_m'))}",
    ]
    if grid_map.weights_provided:
        lines.append(f"- Weight total: {grid_map.weight_total:.3f}")
    if coverage_radius_m is not None:
        lines.extend(
            [
                f"- Coverage within {coverage_radius_m:.3f} m: "
                f"{format_ratio(metrics.get('coverage_within_radius'))}",
                f"- Weighted coverage within {coverage_radius_m:.3f} m: "
                f"{format_ratio(metrics.get('weighted_coverage_within_radius'))}",
            ]
        )
    lines.extend(["", "## Traps (row, col)"])
    for row, col in trap_list:
        lines.append(f"- ({row}, {col})")

    if image_path:
        lines.extend(["", "## Heatmap", "", f"![Distance heatmap]({image_path})"])

    return "\n".join(lines) + "\n"


def save_report(
    grid_map: GridMap,
    traps: Iterable[Tuple[int, int]],
    objective_value: float,
    objective_name: str,
    metrics: dict[str, float | None],
    out_path: str | Path,
    coverage_radius_m: float | None = None,
    image_path: str | None = None,
) -> str:
    out_path = Path(out_path)
    content = build_report(
        grid_map,
        traps,
        objective_value,
        objective_name=objective_name,
        metrics=metrics,
        coverage_radius_m=coverage_radius_m,
        image_path=image_path,
    )
    out_path.write_text(content)
    return content
