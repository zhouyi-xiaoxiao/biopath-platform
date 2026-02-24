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
    proof: dict[str, object] | None = None,
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

    if proof:
        lines.extend(["", "## Proof Contract"])
        run_id = proof.get("run_id")
        if run_id:
            lines.append(f"- Run ID: {run_id}")
        lines.extend(
            [
                f"- Capture probability: {format_ratio(_as_float(proof.get('capture_probability')))}",
                f"- Robust score (scenario min): {format_ratio(_as_float(proof.get('robust_score')))}",
                f"- Capture 95% CI: "
                f"[{format_ratio(_as_float(proof.get('ci95_low')))}, {format_ratio(_as_float(proof.get('ci95_high')))}]",
                f"- Expected time to capture (steps): {format_metric(_as_float(proof.get('expected_time_to_capture')))}",
                f"- Monte Carlo runs: {_format_int(proof.get('mc_runs'))}",
                f"- Time horizon (steps): {_format_int(proof.get('time_horizon_steps'))}",
                f"- Movement model: {_format_text(proof.get('movement_model'))}",
                f"- Seed: {_format_int(proof.get('seed'))}",
            ]
        )

        scenarios = proof.get("scenario_scores")
        if isinstance(scenarios, list) and scenarios:
            lines.extend(["", "## Scenario Scores"])
            for scenario in scenarios:
                if not isinstance(scenario, dict):
                    continue
                name = _format_text(scenario.get("name"))
                cp = format_ratio(_as_float(scenario.get("capture_probability")))
                ci_low = format_ratio(_as_float(scenario.get("ci95_low")))
                ci_high = format_ratio(_as_float(scenario.get("ci95_high")))
                exp_t = format_metric(_as_float(scenario.get("expected_time_to_capture")))
                lines.append(f"- {name}: capture {cp}, CI [{ci_low}, {ci_high}], E[T]={exp_t}")

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
    proof: dict[str, object] | None = None,
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
        proof=proof,
    )
    out_path.write_text(content)
    return content


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _format_int(value: object) -> str:
    if isinstance(value, bool):
        return "n/a"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return "n/a"


def _format_text(value: object) -> str:
    if value is None:
        return "n/a"
    text = str(value).strip()
    return text if text else "n/a"
