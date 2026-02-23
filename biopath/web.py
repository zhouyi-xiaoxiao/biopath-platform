"""Local web UI server for BioPath."""

from __future__ import annotations

import argparse
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .candidates import adjacent_to_wall, all_walkable
from .mapio import load_map_data
from .objective import (
    compute_distance_map,
    distance_metrics,
    mean_distance_to_traps,
    weighted_mean_distance_to_traps,
)
from .optimizer import greedy_optimize

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
SAMPLES_ROOT = ROOT.parent / "tests" / "fixtures"


def _safe_join(root: Path, relative: str) -> Path | None:
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def _serialize_distance_map(distance_map: list[list[float | None]]) -> list[list[float | None]]:
    output: list[list[float | None]] = []
    for row in distance_map:
        out_row: list[float | None] = []
        for value in row:
            if value is None:
                out_row.append(None)
            elif math.isinf(value):
                out_row.append(-1.0)
            else:
                out_row.append(value)
        output.append(out_row)
    return output


def _sanitize_value(value: float | None) -> float | str | None:
    if value is None:
        return None
    if math.isinf(value):
        return "inf"
    return value


def _sanitize_metrics(metrics: dict[str, float | None]) -> dict[str, float | str | None]:
    return {key: _sanitize_value(value) for key, value in metrics.items()}


class BioPathHandler(BaseHTTPRequestHandler):
    server_version = "BioPathHTTP/0.1"

    def _send_json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, content: str, content_type: str, status: int = 200) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_samples(self) -> None:
        if not SAMPLES_ROOT.exists():
            self._send_json({"samples": []})
            return
        samples = []
        for path in sorted(SAMPLES_ROOT.glob("*.json")):
            samples.append({"name": path.name, "title": path.stem.replace("_", " ").title()})
        self._send_json({"samples": samples})

    def _handle_sample(self, query: dict[str, list[str]]) -> None:
        name = query.get("name", [None])[0]
        if not name:
            self._send_json({"error": "name is required"}, status=400)
            return
        if "/" in name or "\\" in name:
            self._send_json({"error": "invalid name"}, status=400)
            return
        path = SAMPLES_ROOT / name
        if not path.exists():
            self._send_json({"error": "sample not found"}, status=404)
            return
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            self._send_json({"error": "invalid sample json"}, status=400)
            return
        self._send_json({"map": data, "name": name})

    def _handle_solve(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            self._send_json({"error": "empty body"}, status=400)
            return
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "invalid json"}, status=400)
            return
        if not isinstance(payload, dict):
            self._send_json({"error": "payload must be a json object"}, status=400)
            return

        map_data = payload.get("map")
        if not isinstance(map_data, dict):
            self._send_json({"error": "map must be an object"}, status=400)
            return

        try:
            grid_map = load_map_data(map_data)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return

        try:
            k = int(payload.get("k", 1))
        except (TypeError, ValueError):
            self._send_json({"error": "k must be an integer"}, status=400)
            return
        if k < 1:
            self._send_json({"error": "k must be >= 1"}, status=400)
            return

        candidate_rule = str(payload.get("candidate_rule", "all_walkable"))
        min_wall_neighbors = int(payload.get("min_wall_neighbors", 1))
        if min_wall_neighbors < 0:
            self._send_json({"error": "min_wall_neighbors must be >= 0"}, status=400)
            return
        local_improve = bool(payload.get("local_improve", False))

        objective_name = str(payload.get("objective", "mean")).lower()
        if objective_name == "mean":
            objective_fn = mean_distance_to_traps
        elif objective_name == "weighted_mean":
            objective_fn = weighted_mean_distance_to_traps
        else:
            self._send_json({"error": "objective must be 'mean' or 'weighted_mean'"}, status=400)
            return

        coverage_radius_m = payload.get("coverage_radius_m")
        if coverage_radius_m is not None:
            try:
                coverage_radius_m = float(coverage_radius_m)
            except (TypeError, ValueError):
                self._send_json({"error": "coverage_radius_m must be a number"}, status=400)
                return
            if coverage_radius_m < 0:
                self._send_json({"error": "coverage_radius_m must be >= 0"}, status=400)
                return

        if candidate_rule == "all_walkable":
            candidates = all_walkable(grid_map)
        elif candidate_rule == "adjacent_to_wall":
            candidates = adjacent_to_wall(grid_map, min_wall_neighbors=min_wall_neighbors)
        else:
            self._send_json(
                {"error": "candidate_rule must be 'all_walkable' or 'adjacent_to_wall'"},
                status=400,
            )
            return

        try:
            traps, _ = greedy_optimize(
                grid_map,
                candidates,
                k,
                local_improve=local_improve,
                objective_fn=objective_fn,
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return

        distance_map = compute_distance_map(grid_map, traps)
        metrics = distance_metrics(grid_map, distance_map, coverage_radius_m=coverage_radius_m)
        objective_value = metrics[
            "mean_distance_m" if objective_name == "mean" else "weighted_mean_distance_m"
        ]

        response = {
            "map": {
                "name": grid_map.name,
                "cell_size_m": grid_map.cell_size_m,
                "ascii": grid_map.ascii,
                "weights": grid_map.weights if grid_map.weights_provided else None,
            },
            "grid": {"height": grid_map.height, "width": grid_map.width},
            "traps": [
                {
                    "row": r,
                    "col": c,
                    "x_m": c * grid_map.cell_size_m,
                    "y_m": r * grid_map.cell_size_m,
                }
                for r, c in traps
            ],
            "objective": {"name": objective_name, "value": _sanitize_value(objective_value)},
            "metrics": _sanitize_metrics(metrics),
            "coverage_radius_m": coverage_radius_m,
            "weights_provided": grid_map.weights_provided,
            "weight_total": grid_map.weight_total,
            "distance_map": _serialize_distance_map(distance_map),
        }
        self._send_json(response)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/samples":
            self._handle_samples()
            return
        if parsed.path == "/api/sample":
            self._handle_sample(parse_qs(parsed.query))
            return

        path = "index.html" if parsed.path in ("/", "/index.html") else parsed.path.lstrip("/")
        target = _safe_join(WEB_ROOT, path)
        if target is None or not target.exists() or not target.is_file():
            self._send_text("Not found", "text/plain", status=404)
            return

        content_type = "text/plain"
        if target.suffix == ".html":
            content_type = "text/html"
        elif target.suffix == ".css":
            content_type = "text/css"
        elif target.suffix == ".js":
            content_type = "application/javascript"

        self._send_file(target, content_type)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/solve":
            self._handle_solve()
            return
        self._send_text("Not found", "text/plain", status=404)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="BioPath local web UI server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), BioPathHandler)
    address = f"http://{args.host}:{args.port}"
    print(f"BioPath web UI running at {address}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
