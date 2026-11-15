/*
 * BioPath browser solver.
 *
 * A direct port of the deterministic path of the Python package, so the
 * public page can solve without a server:
 *   biopath/mapio.py       load_map_data        -> parseMap
 *   biopath/objective.py   compute_distance_map -> distanceMap
 *                          mean / weighted mean -> meanDistance / weightedMeanDistance
 *                          distance_metrics     -> distanceMetrics
 *   biopath/optimizer.py   greedy_optimize      -> greedyOptimize
 *   biopath/run_pipeline.py evaluate_heuristic_baseline (trap choice) -> heuristicBaseline
 *   biopath/capture.py     simulate_capture_probability -> simulateCapture
 *
 * The deterministic parts return the same traps and the same numbers as the
 * Python code (checked by tests/test_browser_solver_parity.py). The capture
 * simulation uses the same walk model but a different random number
 * generator, so its estimates agree with Python only within sampling error.
 */
(function (root) {
  "use strict";

  const SOLVER_VERSION = "browser-port-1";

  function parseMap(data) {
    const rows = data.ascii;
    if (!Array.isArray(rows) || rows.length === 0) throw new Error("ascii grid must be non-empty");
    const height = rows.length;
    const width = rows[0].length;
    const walk = new Uint8Array(height * width);
    let walkableCount = 0;
    for (let r = 0; r < height; r++) {
      if (rows[r].length !== width) throw new Error("all ascii rows must be the same length");
      for (let c = 0; c < width; c++) {
        const ch = rows[r][c];
        if (ch === ".") {
          walk[r * width + c] = 1;
          walkableCount++;
        } else if (ch !== "#") {
          throw new Error("ascii grid may only contain '.' or '#'");
        }
      }
    }
    const weights = new Float64Array(height * width);
    let weightTotal = 0;
    const provided = Array.isArray(data.weights);
    for (let r = 0; r < height; r++) {
      for (let c = 0; c < width; c++) {
        const i = r * width + c;
        if (!walk[i]) continue;
        const w = provided ? Number(data.weights[r][c]) : 1.0;
        weights[i] = w;
        weightTotal += w;
      }
    }
    return {
      name: String(data.name || "Untitled map"),
      cellSize: Number(data.cell_size_m || 1),
      height,
      width,
      walk,
      walkableCount,
      weights,
      weightTotal,
      weightsProvided: provided,
    };
  }

  function toAscii(map) {
    const rows = [];
    for (let r = 0; r < map.height; r++) {
      let line = "";
      for (let c = 0; c < map.width; c++) line += map.walk[r * map.width + c] ? "." : "#";
      rows.push(line);
    }
    return rows;
  }

  // Neighbour order matches GridMap.neighbors4: up, down, left, right.
  const DIRS = [
    [-1, 0],
    [1, 0],
    [0, -1],
    [0, 1],
  ];

  function walkables(map) {
    const out = [];
    for (let r = 0; r < map.height; r++) {
      for (let c = 0; c < map.width; c++) if (map.walk[r * map.width + c]) out.push([r, c]);
    }
    return out;
  }

  /** Multi-source BFS distance (metres) to the nearest trap. Walls are NaN. */
  function distanceMap(map, traps) {
    const { height, width, walk, cellSize } = map;
    const dist = new Float64Array(height * width);
    for (let i = 0; i < dist.length; i++) dist[i] = walk[i] ? Infinity : NaN;
    if (!traps.length) return dist;
    const queue = new Int32Array(height * width);
    let head = 0;
    let tail = 0;
    for (const [r, c] of traps) {
      const i = r * width + c;
      if (!walk[i]) throw new Error("trap must be on a walkable cell");
      if (dist[i] !== 0) {
        dist[i] = 0;
        queue[tail++] = i;
      }
    }
    while (head < tail) {
      const i = queue[head++];
      const r = (i / width) | 0;
      const c = i - r * width;
      const cur = dist[i];
      for (const [dr, dc] of DIRS) {
        const nr = r + dr;
        const nc = c + dc;
        if (nr < 0 || nr >= height || nc < 0 || nc >= width) continue;
        const j = nr * width + nc;
        if (!walk[j]) continue;
        if (dist[j] === Infinity) {
          dist[j] = cur + cellSize;
          queue[tail++] = j;
        }
      }
    }
    return dist;
  }

  function meanDistance(map, traps) {
    const dist = distanceMap(map, traps);
    if (map.walkableCount === 0) return 0;
    let total = 0;
    let count = 0;
    for (let i = 0; i < dist.length; i++) {
      if (!map.walk[i]) continue;
      const v = dist[i];
      if (v === Infinity) return Infinity;
      total += v;
      count++;
    }
    return count ? total / count : 0;
  }

  function weightedMeanDistance(map, traps) {
    const dist = distanceMap(map, traps);
    if (map.weightTotal === 0) return 0;
    let total = 0;
    let weightTotal = 0;
    for (let i = 0; i < dist.length; i++) {
      if (!map.walk[i]) continue;
      const w = map.weights[i];
      if (w <= 0) continue;
      const v = dist[i];
      if (v === Infinity) return Infinity;
      total += w * v;
      weightTotal += w;
    }
    return weightTotal ? total / weightTotal : 0;
  }

  function percentile(values, fraction) {
    if (!values.length) return 0;
    const sorted = values.slice().sort((a, b) => a - b);
    const idx = Math.max(0, Math.min(sorted.length - 1, Math.ceil(fraction * sorted.length) - 1));
    return sorted[idx];
  }

  function distanceMetrics(map, dist) {
    const values = [];
    let hasInf = false;
    let total = 0;
    let wTotal = 0;
    let wWeight = 0;
    let wInf = false;
    for (let i = 0; i < dist.length; i++) {
      if (!map.walk[i]) continue;
      const v = dist[i];
      if (v === Infinity) hasInf = true;
      else {
        values.push(v);
        total += v;
      }
      const w = map.weights[i];
      if (w > 0) {
        wWeight += w;
        if (v === Infinity) wInf = true;
        else wTotal += w * v;
      }
    }
    return {
      mean_distance_m: hasInf ? Infinity : values.length ? total / values.length : 0,
      weighted_mean_distance_m: wInf ? Infinity : wWeight ? wTotal / wWeight : 0,
      max_distance_m: hasInf ? Infinity : values.length ? Math.max(...values) : 0,
      p95_distance_m: hasInf ? Infinity : percentile(values, 0.95),
    };
  }

  const key = (t) => t[0] * 100000 + t[1];

  /*
   * Fast evaluator for the mean / weighted-mean objectives. Single-source BFS
   * step counts from every candidate are computed once; the distance of a cell
   * to a trap set is then the minimum over traps, and the metre value is read
   * from a table built by repeated addition, exactly as the multi-source BFS
   * builds it. Sums run in row-major order, so results are bit-identical to
   * meanDistance / weightedMeanDistance.
   */
  function makeFastObjective(map, cands, weighted) {
    const cells = [];
    for (let i = 0; i < map.walk.length; i++) if (map.walk[i]) cells.push(i);
    const n = cells.length;
    const cellIndex = new Int32Array(map.walk.length).fill(-1);
    cells.forEach((cell, j) => (cellIndex[cell] = j));
    const UNREACHED = 65535;
    const steps = new Map();
    let maxStep = 0;
    const queue = new Int32Array(map.walk.length);
    const stepsFrom = (t) => {
      const k = key(t);
      if (steps.has(k)) return steps.get(k);
      const row = new Uint16Array(n).fill(UNREACHED);
      const start = t[0] * map.width + t[1];
      if (!map.walk[start]) throw new Error("trap must be on a walkable cell");
      let head = 0;
      let tail = 0;
      row[cellIndex[start]] = 0;
      queue[tail++] = start;
      while (head < tail) {
        const i = queue[head++];
        const r = (i / map.width) | 0;
        const c = i - r * map.width;
        const cur = row[cellIndex[i]];
        for (const [dr, dc] of DIRS) {
          const nr = r + dr;
          const nc = c + dc;
          if (nr < 0 || nr >= map.height || nc < 0 || nc >= map.width) continue;
          const j = nr * map.width + nc;
          if (!map.walk[j] || row[cellIndex[j]] !== UNREACHED) continue;
          row[cellIndex[j]] = cur + 1;
          if (cur + 1 > maxStep) maxStep = cur + 1;
          queue[tail++] = j;
        }
      }
      steps.set(k, row);
      return row;
    };
    cands.forEach(stepsFrom);
    const metres = new Float64Array(maxStep + 2);
    for (let s = 1; s < metres.length; s++) metres[s] = metres[s - 1] + map.cellSize;
    const w = new Float64Array(n);
    cells.forEach((cell, j) => (w[j] = map.weights[cell]));

    // Score a "current minimum" row combined with one more trap (or none).
    function score(minRow, extra) {
      let total = 0;
      let denom = 0;
      for (let j = 0; j < n; j++) {
        let s = minRow ? minRow[j] : UNREACHED;
        if (extra && extra[j] < s) s = extra[j];
        if (weighted) {
          if (w[j] <= 0) continue;
          if (s === UNREACHED) return Infinity;
          total += w[j] * metres[s];
          denom += w[j];
        } else {
          if (s === UNREACHED) return Infinity;
          total += metres[s];
          denom += 1;
        }
      }
      if (weighted && map.weightTotal === 0) return 0;
      return denom ? total / denom : 0;
    }
    function minRowOf(traps) {
      const row = new Uint16Array(n).fill(UNREACHED);
      for (const t of traps) {
        const st = stepsFrom(t);
        for (let j = 0; j < n; j++) if (st[j] < row[j]) row[j] = st[j];
      }
      return row;
    }
    return { score, minRowOf, stepsFrom, empty: n === 0 };
  }

  /** Same algorithm as greedyOptimize, on the fast evaluator. */
  function greedyOptimizeFast(map, candidates, k, localImprove, weighted) {
    const seen = new Set();
    const cands = [];
    for (const t of candidates) {
      if (!seen.has(key(t))) {
        seen.add(key(t));
        cands.push(t);
      }
    }
    const fast = makeFastObjective(map, cands, weighted);
    const evalSet = (traps) => (fast.empty ? 0 : fast.score(fast.minRowOf(traps), null));
    if (k <= 0) return { traps: [], objective: evalSet([]) };
    if (k > cands.length) throw new Error("k cannot exceed number of candidates");

    let selected = [];
    const selectedSet = new Set();
    let base = fast.minRowOf([]);
    for (let step = 0; step < k; step++) {
      let best = null;
      let bestObj = Infinity;
      for (const cand of cands) {
        if (selectedSet.has(key(cand))) continue;
        const obj = fast.score(base, fast.stepsFrom(cand));
        if (obj < bestObj) {
          bestObj = obj;
          best = cand;
        }
      }
      if (best === null) break;
      selected.push(best);
      selectedSet.add(key(best));
      base = fast.minRowOf(selected);
    }

    let current = evalSet(selected);
    if (localImprove && selected.length) {
      let improved = true;
      while (improved) {
        improved = false;
        let bestSwap = null;
        let bestObj = current;
        const unselected = cands.filter((c) => !selectedSet.has(key(c)));
        for (const out of selected.slice()) {
          const rest = fast.minRowOf(selected.filter((t) => key(t) !== key(out)));
          for (const inn of unselected) {
            const obj = fast.score(rest, fast.stepsFrom(inn));
            if (obj < bestObj) {
              bestObj = obj;
              bestSwap = [out, inn];
            }
          }
        }
        if (bestSwap) {
          const [out, inn] = bestSwap;
          selected = selected.filter((t) => key(t) !== key(out));
          selected.push(inn);
          selectedSet.delete(key(out));
          selectedSet.add(key(inn));
          current = bestObj;
          improved = true;
        }
      }
    }
    return { traps: selected, objective: current };
  }

  /** Greedy selection with optional best-swap improvement (optimizer.greedy_optimize). */
  function greedyOptimize(map, candidates, k, localImprove, objectiveFn) {
    const objective = objectiveFn || meanDistance;
    if (k <= 0) return { traps: [], objective: objective(map, []) };
    const seen = new Set();
    const cands = [];
    for (const t of candidates) {
      if (!seen.has(key(t))) {
        seen.add(key(t));
        cands.push(t);
      }
    }
    if (k > cands.length) throw new Error("k cannot exceed number of candidates");

    let selected = [];
    const selectedSet = new Set();
    for (let step = 0; step < k; step++) {
      let best = null;
      let bestObj = Infinity;
      for (const cand of cands) {
        if (selectedSet.has(key(cand))) continue;
        const obj = objective(map, selected.concat([cand]));
        if (obj < bestObj) {
          bestObj = obj;
          best = cand;
        }
      }
      if (best === null) break;
      selected.push(best);
      selectedSet.add(key(best));
    }

    let current = objective(map, selected);
    if (localImprove && selected.length) {
      let improved = true;
      while (improved) {
        improved = false;
        let bestSwap = null;
        let bestObj = current;
        const unselected = cands.filter((c) => !selectedSet.has(key(c)));
        for (const out of selected.slice()) {
          for (const inn of unselected) {
            const trial = selected.filter((t) => key(t) !== key(out)).concat([inn]);
            const obj = objective(map, trial);
            if (obj < bestObj) {
              bestObj = obj;
              bestSwap = [out, inn];
            }
          }
        }
        if (bestSwap) {
          const [out, inn] = bestSwap;
          selected = selected.filter((t) => key(t) !== key(out));
          selected.push(inn);
          selectedSet.delete(key(out));
          selectedSet.add(key(inn));
          current = bestObj;
          improved = true;
        }
      }
    }
    return { traps: selected, objective: current };
  }

  /** Rule-of-thumb layout: edges first, hotspots first, at least `spacing` cells apart. */
  function heuristicBaseline(map, candidates, k, spacing) {
    const minSpacing = spacing || 5;
    const ranked = [];
    for (const [r, c] of candidates) {
      const w = map.weights[r * map.width + c];
      let wall = 0;
      for (const [dr, dc] of DIRS) {
        const nr = r + dr;
        const nc = c + dc;
        if (nr < 0 || nr >= map.height || nc < 0 || nc >= map.width) continue;
        if (!map.walk[nr * map.width + nc]) wall++;
      }
      const score = w + (wall >= 1 ? 0.45 : 0) + (wall >= 2 ? 0.45 : 0);
      ranked.push([score, w, wall, r, c]);
    }
    // Python: sort by (score, weight, wall, -row, -col) with reverse=True.
    ranked.sort((a, b) => b[0] - a[0] || b[1] - a[1] || b[2] - a[2] || a[3] - b[3] || a[4] - b[4]);
    const want = Math.max(1, k);
    const selected = [];
    const manhattan = (a, b) => Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]);
    for (const item of ranked) {
      if (selected.length >= want) break;
      const t = [item[3], item[4]];
      if (selected.every((s) => manhattan(t, s) >= minSpacing)) selected.push(t);
    }
    if (selected.length < want) {
      for (const item of ranked) {
        if (selected.length >= want) break;
        const t = [item[3], item[4]];
        if (selected.some((s) => key(s) === key(t))) continue;
        selected.push(t);
      }
    }
    return selected;
  }

  // Small seeded generator (mulberry32) with a per-walk seed, as capture.py does.
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /** Lazy random walk (stay with probability 0.25), capture.simulate_capture_probability. */
  function simulateCapture(map, traps, opts) {
    const runs = Math.max(1, (opts && opts.runs) || 160);
    const horizon = Math.max(1, (opts && opts.horizon) || 48);
    const seed = (opts && opts.seed) || 7;
    const cells = walkables(map);
    if (!traps.length || !cells.length) {
      return { capture_probability: 0, ci95_low: 0, ci95_high: 0, expected_time_to_capture: horizon, runs, horizon };
    }
    const trapSet = new Set(traps.map(key));
    let captures = 0;
    let totalTime = 0;
    for (let run = 0; run < runs; run++) {
      const rand = rng(Math.imul(seed + 1, 0x9e3779b1) ^ Math.imul(run + 1, 0x85ebca6b));
      let r;
      let c;
      if (map.weightsProvided && map.weightTotal > 0) {
        const pick = rand() * map.weightTotal;
        let acc = 0;
        [r, c] = cells[cells.length - 1];
        for (const [rr, cc] of cells) {
          acc += map.weights[rr * map.width + cc];
          if (pick <= acc) {
            r = rr;
            c = cc;
            break;
          }
        }
      } else {
        [r, c] = cells[Math.floor(rand() * cells.length)];
      }
      let captured = false;
      for (let t = 1; t <= horizon; t++) {
        if (trapSet.has(key([r, c]))) {
          captures++;
          totalTime += t;
          captured = true;
          break;
        }
        const nbrs = [];
        for (const [dr, dc] of DIRS) {
          const nr = r + dr;
          const nc = c + dc;
          if (nr < 0 || nr >= map.height || nc < 0 || nc >= map.width) continue;
          if (map.walk[nr * map.width + nc]) nbrs.push([nr, nc]);
        }
        if (!nbrs.length) continue;
        if (rand() < 0.25) continue;
        [r, c] = nbrs[Math.floor(rand() * nbrs.length)];
      }
      if (!captured) totalTime += horizon;
    }
    const p = captures / runs;
    const margin = 1.96 * Math.sqrt(Math.max(p * (1 - p), 0) / runs);
    return {
      capture_probability: p,
      ci95_low: Math.max(0, p - margin),
      ci95_high: Math.min(1, p + margin),
      expected_time_to_capture: totalTime / runs,
      runs,
      horizon,
    };
  }

  /** True if every open cell can reach every other one. */
  function isConnected(map) {
    const cells = walkables(map);
    if (!cells.length) return false;
    const dist = distanceMap(map, [cells[0]]);
    for (let i = 0; i < dist.length; i++) if (map.walk[i] && dist[i] === Infinity) return false;
    return true;
  }

  /** One full plan: optimised traps, rule-of-thumb traps, both scored. */
  function plan(map, k, opts) {
    const cands = walkables(map);
    const solved = greedyOptimizeFast(map, cands, k, true, map.weightsProvided);
    const baseline = heuristicBaseline(map, cands, k, 5);
    const score = (traps) => ({
      traps,
      distance: distanceMap(map, traps),
      metrics: distanceMetrics(map, distanceMap(map, traps)),
      capture: simulateCapture(map, traps, opts),
    });
    return {
      solver_version: SOLVER_VERSION,
      objective: map.weightsProvided ? "weighted_mean" : "mean",
      k,
      optimised: score(solved.traps),
      baseline: score(baseline),
    };
  }

  const api = {
    SOLVER_VERSION,
    parseMap,
    toAscii,
    walkables,
    distanceMap,
    meanDistance,
    weightedMeanDistance,
    distanceMetrics,
    greedyOptimize,
    greedyOptimizeFast,
    heuristicBaseline,
    simulateCapture,
    isConnected,
    plan,
  };
  root.BioPathSolver = api;
  if (typeof module === "object" && module && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
