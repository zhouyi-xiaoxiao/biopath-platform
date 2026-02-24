#!/usr/bin/env python3
"""Sync pitch/deck assets from site/data/latest*.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST_PATH = ROOT / "site" / "data" / "latest.json"
BENCH_PATH = ROOT / "site" / "data" / "latest-benchmark.json"
MAP_PATH = ROOT / "site" / "data" / "cambridge-photo-informed-map.json"

PITCH_DECK = ROOT / "site" / "pitch-deck.html"
PITCH_SCRIPT = ROOT / "site" / "pitch-script.html"
SUMMARY_MD = ROOT / "site" / "assets" / "cambridge-photo-informed-summary.md"
SOLVE_JSON = ROOT / "site" / "assets" / "cambridge-photo-informed-solve.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _replace_once(text: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"Expected exactly one match for pattern: {pattern}")
    return updated


def _pct_ratio(value: float) -> str:
    return f"{value * 100:.1f}%"


def _num_ratio(value: float) -> str:
    return f"{value * 100:.1f}"


def _fmt_pct_value(value: float) -> str:
    return f"{value:.1f}%"


def sync_pitch_deck(
    deck_text: str,
    *,
    optimized: float,
    baseline: float,
    uplift_pct: float,
    robust: float,
    random_baseline: float,
    random_uplift_pct: float,
) -> str:
    replacements = {
        "Optimized capture": _pct_ratio(optimized),
        "Heuristic baseline": _pct_ratio(baseline),
        "Uplift vs heuristic": f"+{_fmt_pct_value(uplift_pct)}",
        "Robust capture": _pct_ratio(robust),
        "Random baseline": _pct_ratio(random_baseline),
        "Secondary uplift": f"+{_fmt_pct_value(random_uplift_pct)}",
    }

    for label, value in replacements.items():
        pattern = rf'(<div class="metric"><span>{re.escape(label)}</span><strong>)([^<]+)(</strong></div>)'
        updated, count = re.subn(
            pattern,
            lambda m, v=value: f"{m.group(1)}{v}{m.group(3)}",
            deck_text,
            count=1,
            flags=re.DOTALL,
        )
        if count != 1:
            raise RuntimeError(f"Expected exactly one match for metric label: {label}")
        deck_text = updated

    return deck_text


def sync_pitch_script(
    script_text: str,
    *,
    k: int,
    optimized: float,
    baseline: float,
    uplift_pct: float,
    robust: float,
    random_baseline: float,
    random_uplift_pct: float,
    mc_runs: int,
) -> str:
    line1 = (
        f'<p class="line"><strong>Say:</strong> "With k equals {k} traps, optimized capture is {_num_ratio(optimized)} percent. '
        f'Heuristic baseline is {_num_ratio(baseline)} percent, so uplift is plus {uplift_pct:.1f} percent under the same trap budget."</p>'
    )
    line2 = (
        f'<p class="line"><strong>Say:</strong> "Robust capture is {_num_ratio(robust)} percent, validated with Monte Carlo N equals {mc_runs}. '
        'So this is not one lucky run; it is a conservative score under uncertainty."</p>'
    )
    line3 = (
        f'<p class="line"><strong>Say:</strong> "Random baseline is {_num_ratio(random_baseline)} percent and gives plus {random_uplift_pct:.1f} percent uplift, '
        'but for realism we report heuristic as primary and random as secondary."</p>'
    )

    script_text = _replace_once(
        script_text,
        r'<p class="line"><strong>Say:</strong> "With k equals .*?under the same trap budget\."</p>',
        line1,
    )
    script_text = _replace_once(
        script_text,
        r'<p class="line"><strong>Say:</strong> "Robust capture is .*?under uncertainty\."</p>',
        line2,
    )
    script_text = _replace_once(
        script_text,
        r'<p class="line"><strong>Say:</strong> "Random baseline is .*?random as secondary\."</p>',
        line3,
    )

    return script_text


def write_summary(*, latest: dict, map_data: dict) -> None:
    metrics = latest.get("metrics", {})
    traps = latest.get("traps", [])

    source_url = str(map_data.get("source_photo", "")).strip()
    source_license = str(map_data.get("source_license", "CC BY-SA 2.0")).strip() or "CC BY-SA 2.0"
    source_credit = str(map_data.get("source_credit", "Peter Bower / Geograph (via Wikimedia Commons)")).strip()

    lines = [
        "# BioPath Photo-informed Demo Summary",
        "",
        f"- Map: {latest.get('map', {}).get('name', map_data.get('name', 'Cambridge demo map'))}",
        "- Source photo: Cambridge University Farm (public reference image from Wikimedia Commons)",
        f"- Photo credit: {source_credit}",
        f"- Source URL: {source_url}",
        f"- Source license: {source_license}",
        "- Conversion method: publicly inspired synthetic geometry + photo-informed risk prior",
        "",
        "## Core outputs",
        f"- Capture probability: {float(latest.get('capture_probability', 0.0)):.4f}",
        f"- Robust score: {float(latest.get('robust_score', 0.0)):.4f}",
        f"- Mean distance (m): {float(metrics.get('mean_distance_m', 0.0)):.3f}",
        f"- Weighted mean distance (m): {float(metrics.get('weighted_mean_distance_m', 0.0)):.3f}",
        "",
        "## Trap coordinates (row, col)",
    ]

    for trap in traps:
        lines.append(f"- ({int(trap['row'])}, {int(trap['col'])})")

    lines.extend(
        [
            "",
            "## Important transparency note",
            "- Geometry and activity prior are demonstration-grade approximations based on public context, not private farm telemetry.",
            "- Real pilot deployment would replace priors with site survey + operator observations + actual monitoring traces.",
        ]
    )

    SUMMARY_MD.write_text("\n".join(lines) + "\n")


def write_solve_payload(*, latest: dict, map_data: dict) -> None:
    payload = {
        "source": {
            "photo_url": map_data.get("source_photo"),
            "photo_credit": map_data.get("source_credit", "Peter Bower / Geograph (via Wikimedia Commons)"),
            "license": map_data.get("source_license", "CC BY-SA 2.0"),
            "method": "synthetic geometry + photo-informed prior",
        },
        "result": latest,
    }
    SOLVE_JSON.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    latest = _read_json(LATEST_PATH)
    benchmark = _read_json(BENCH_PATH)
    map_data = _read_json(MAP_PATH)

    run_id_latest = str(latest.get("run_id", "")).strip()
    run_id_bench = str(benchmark.get("run_id") or benchmark.get("run", {}).get("run_id") or "").strip()
    if run_id_latest and run_id_bench and run_id_latest != run_id_bench:
        raise RuntimeError(f"run_id mismatch: latest={run_id_latest} benchmark={run_id_bench}")

    optimized = float(benchmark["optimized_score"])
    baseline = float(benchmark["baseline"]["mean"])
    uplift_pct = float(benchmark["uplift_vs_baseline_pct"])
    robust = float(latest["robust_score"])
    random_baseline = float(benchmark["baselines"]["random"]["mean"])
    random_uplift_pct = float(benchmark["uplift_vs_random_pct"])

    k = int(benchmark.get("k") or len(latest.get("traps", [])))
    mc_runs = int(benchmark.get("mc_runs") or 0)

    deck_text = PITCH_DECK.read_text()
    deck_text = sync_pitch_deck(
        deck_text,
        optimized=optimized,
        baseline=baseline,
        uplift_pct=uplift_pct,
        robust=robust,
        random_baseline=random_baseline,
        random_uplift_pct=random_uplift_pct,
    )
    PITCH_DECK.write_text(deck_text)

    script_text = PITCH_SCRIPT.read_text()
    script_text = sync_pitch_script(
        script_text,
        k=k,
        optimized=optimized,
        baseline=baseline,
        uplift_pct=uplift_pct,
        robust=robust,
        random_baseline=random_baseline,
        random_uplift_pct=random_uplift_pct,
        mc_runs=mc_runs,
    )
    PITCH_SCRIPT.write_text(script_text)

    write_summary(latest=latest, map_data=map_data)
    write_solve_payload(latest=latest, map_data=map_data)

    print(
        json.dumps(
            {
                "run_id": run_id_latest,
                "optimized": _pct_ratio(optimized),
                "baseline": _pct_ratio(baseline),
                "uplift": f"+{uplift_pct:.1f}%",
                "robust": _pct_ratio(robust),
                "random_baseline": _pct_ratio(random_baseline),
                "random_uplift": f"+{random_uplift_pct:.1f}%",
                "updated": [
                    str(PITCH_DECK.relative_to(ROOT)),
                    str(PITCH_SCRIPT.relative_to(ROOT)),
                    str(SUMMARY_MD.relative_to(ROOT)),
                    str(SOLVE_JSON.relative_to(ROOT)),
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
