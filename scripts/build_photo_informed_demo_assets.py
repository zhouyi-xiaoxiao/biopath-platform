#!/usr/bin/env python3
"""Build photo-informed demo assets for BioPath pitch.

Outputs:
- maps/cambridgeshire_photo_informed.json
- site/data/cambridge-photo-informed-map.json
- site/assets/cambridge-photo-informed-heatmap.png
- site/assets/cambridge-photo-informed-transform.png
- site/assets/cambridge-photo-informed-solve.json
- site/assets/cambridge-photo-informed-summary.md
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MAPS_DIR = ROOT / "maps"
SITE_ASSETS = ROOT / "site" / "assets"
SITE_DATA = ROOT / "site" / "data"

from biopath.mapio import load_map_data
from biopath.objective import compute_distance_map
from biopath.run_pipeline import SolveOptions, run_solve
from biopath.viz import save_heatmap

BASE_MAP_PATH = MAPS_DIR / "cambridgeshire_demo_farm.json"
PHOTO_PATH = SITE_ASSETS / "cambridge-university-farm.jpg"
PHOTO_URL = "https://commons.wikimedia.org/wiki/File:Cambridge_University_Farm_-_geograph.org.uk_-_3363476.jpg"


def _build_weights(ascii_rows: list[str]) -> list[list[float]]:
    height = len(ascii_rows)
    width = len(ascii_rows[0])

    # Publicly inspired hotspots for demonstration: access gates, feed/storage area,
    # central corridor junctions, and shelter edges.
    hotspots: list[tuple[float, float, float, float]] = [
        (2.4, 3.4, 2.3, 2.5),
        (2.4, 18.8, 2.1, 2.6),
        (6.3, 7.2, 1.8, 2.4),
        (6.6, 15.8, 2.4, 2.8),
        (10.2, 22.2, 2.2, 2.9),
        (10.8, 14.2, 1.7, 3.0),
    ]

    weights = [[0.0 for _ in range(width)] for _ in range(height)]

    for r in range(height):
        for c in range(width):
            if ascii_rows[r][c] != ".":
                continue

            value = 0.55
            for hr, hc, amp, sigma in hotspots:
                d2 = (r - hr) ** 2 + (c - hc) ** 2
                value += amp * math.exp(-d2 / (2.0 * sigma**2))

            # Slight wall-proximity boost to mimic edge-running behaviour.
            wall_bonus = 0.0
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                rr, cc = r + dr, c + dc
                if 0 <= rr < height and 0 <= cc < width and ascii_rows[rr][cc] == "#":
                    wall_bonus += 0.14
            value += min(0.42, wall_bonus)

            weights[r][c] = round(min(4.8, max(0.15, value)), 3)

    return weights


def _save_transform_figure(
    photo_path: Path,
    ascii_rows: list[str],
    weights: list[list[float]],
    traps: list[tuple[int, int]],
    out_path: Path,
) -> None:
    photo = plt.imread(photo_path)
    geom = np.array([[0 if ch == "#" else 1 for ch in row] for row in ascii_rows], dtype=float)
    weight_arr = np.array(weights, dtype=float)
    mask = geom == 0
    weight_masked = np.ma.array(weight_arr, mask=mask)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.8), dpi=220, facecolor="#06120d")
    panel_bg = "#0d1f17"

    for ax in axes:
        ax.set_facecolor(panel_bg)
        for spine in ax.spines.values():
            spine.set_color("#335447")
            spine.set_linewidth(0.9)

    axes[0].imshow(photo)
    axes[0].set_title("1) Real farm context", fontsize=10, pad=9, color="#e5f7ee", weight="bold")
    axes[0].axis("off")

    cmap_geom = plt.cm.Greens.copy()
    axes[1].imshow(geom, cmap=cmap_geom, origin="upper", vmin=0, vmax=1, interpolation="nearest", aspect="auto")
    axes[1].set_title("2) Synthetic walkable geometry", fontsize=10, pad=9, color="#e5f7ee", weight="bold")
    axes[1].set_xticks([])
    axes[1].set_yticks([])
    axes[1].set_xlabel("Transparent geometry for computation", fontsize=8, color="#bddbcc")

    cmap_w = plt.cm.inferno.copy()
    cmap_w.set_bad(color="#101418")
    im = axes[2].imshow(weight_masked, cmap=cmap_w, origin="upper", interpolation="nearest", aspect="auto")
    if traps:
        rows, cols = zip(*traps)
        axes[2].scatter(cols, rows, c="#dffdf0", marker="X", s=40, linewidths=0.8, edgecolors="#8a4330")
    axes[2].set_title("3) Photo-informed prior + optimised traps", fontsize=10, pad=9, color="#e5f7ee", weight="bold")
    axes[2].set_xticks([])
    axes[2].set_yticks([])
    axes[2].set_xlabel("Brighter = higher prior activity", fontsize=8, color="#bddbcc")

    cbar = fig.colorbar(im, ax=axes[2], fraction=0.042, pad=0.022)
    cbar.set_label("Relative activity prior", fontsize=8, color="#e6f8ef")
    cbar.ax.tick_params(labelsize=7, colors="#d5efe2")
    cbar.outline.set_edgecolor("#2d463b")

    fig.text(0.335, 0.51, "→", fontsize=24, color="#cae7d8", ha="center", va="center")
    fig.text(0.665, 0.51, "→", fontsize=24, color="#cae7d8", ha="center", va="center")
    fig.suptitle("Photo -> Model -> Solve", fontsize=13, y=0.965, color="#effaf4", weight="bold")
    fig.tight_layout(rect=[0.01, 0.01, 0.99, 0.94])
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def _write_summary(
    result: dict[str, Any],
    map_data: dict[str, Any],
    out_path: Path,
) -> None:
    metrics = result.get("metrics", {})
    lines = [
        "# BioPath Photo-informed Demo Summary",
        "",
        f"- Map: {map_data['name']}",
        "- Source photo: Cambridge University Farm (Wikimedia Commons, CC BY-SA 2.0)",
        f"- Source URL: {PHOTO_URL}",
        "- Conversion method: publicly inspired synthetic geometry + photo-informed risk prior",
        "",
        "## Core outputs",
        f"- Capture probability: {result.get('capture_probability', 0.0):.4f}",
        f"- Robust score: {result.get('robust_score', 0.0):.4f}",
        f"- Mean distance (m): {metrics.get('mean_distance_m', 0.0):.3f}",
        f"- Weighted mean distance (m): {metrics.get('weighted_mean_distance_m', 0.0):.3f}",
        "",
        "## Trap coordinates (row, col)",
    ]

    for trap in result.get("traps", []):
        lines.append(f"- ({trap['row']}, {trap['col']})")

    lines.extend(
        [
            "",
            "## Important transparency note",
            "- Geometry and activity prior are demonstration-grade approximations based on public context, not private farm telemetry.",
            "- Real pilot deployment would replace priors with site survey + operator observations + actual monitoring traces.",
        ]
    )

    out_path.write_text("\n".join(lines))


def main() -> None:
    base_map = json.loads(BASE_MAP_PATH.read_text())
    ascii_rows = base_map["ascii"]
    weights = _build_weights(ascii_rows)

    photo_map = {
        "name": "Cambridgeshire Photo-informed Demo Farm (Synthetic Geometry + Publicly Inspired Risk Prior)",
        "cell_size_m": 1.0,
        "ascii": ascii_rows,
        "weights": weights,
        "source_photo": PHOTO_URL,
        "source_license": "CC BY-SA 2.0",
        "distribution_note": "Publicly inspired prior for demo only; replace with pilot data in production.",
    }

    photo_map_path = MAPS_DIR / "cambridgeshire_photo_informed.json"
    photo_map_path.write_text(json.dumps(photo_map, indent=2))

    site_map_path = SITE_DATA / "cambridge-photo-informed-map.json"
    site_map_path.write_text(json.dumps(photo_map, indent=2))

    options = SolveOptions(
        k=6,
        objective="robust_capture",
        candidate_rule="all_walkable",
        local_improve=True,
        mc_runs=160,
        time_horizon_steps=48,
        seed=7,
        create_run=False,
    )
    result = run_solve(photo_map, runs_root=ROOT / "runs", options=options)

    grid_map = load_map_data(photo_map)
    traps = [(int(t["row"]), int(t["col"])) for t in result["traps"]]
    distance_map = compute_distance_map(grid_map, traps)

    heatmap_path = SITE_ASSETS / "cambridge-photo-informed-heatmap.png"
    save_heatmap(grid_map, distance_map, traps, heatmap_path)

    transform_path = SITE_ASSETS / "cambridge-photo-informed-transform.png"
    _save_transform_figure(PHOTO_PATH, ascii_rows, weights, traps, transform_path)

    solve_payload = {
        "source": {
            "photo_url": PHOTO_URL,
            "license": "CC BY-SA 2.0",
            "method": "synthetic geometry + photo-informed prior",
        },
        "result": result,
    }
    solve_json_path = SITE_ASSETS / "cambridge-photo-informed-solve.json"
    solve_json_path.write_text(json.dumps(solve_payload, indent=2))

    summary_path = SITE_ASSETS / "cambridge-photo-informed-summary.md"
    _write_summary(result, photo_map, summary_path)

    print(
        json.dumps(
            {
                "map": str(photo_map_path),
                "site_map": str(site_map_path),
                "heatmap": str(heatmap_path),
                "transform": str(transform_path),
                "summary": str(summary_path),
                "capture_probability": result.get("capture_probability"),
                "robust_score": result.get("robust_score"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
