#!/usr/bin/env python3
"""Compare last two run metrics and emit short summary."""

from __future__ import annotations

import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    runs = sorted([p for p in Path("runs").glob("*/metrics.json")], reverse=True)
    if len(runs) < 2:
        print("Not enough runs for delta.")
        return

    latest = _load(runs[0])
    prev = _load(runs[1])

    cp_latest = float(latest.get("capture_probability", 0.0))
    cp_prev = float(prev.get("capture_probability", 0.0))
    rb_latest = float(latest.get("robust_score", 0.0))
    rb_prev = float(prev.get("robust_score", 0.0))

    print(
        json.dumps(
            {
                "latest_run": latest.get("run_id"),
                "prev_run": prev.get("run_id"),
                "capture_probability_delta": cp_latest - cp_prev,
                "robust_score_delta": rb_latest - rb_prev,
                "improved": (cp_latest - cp_prev) > 0 or (rb_latest - rb_prev) > 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
