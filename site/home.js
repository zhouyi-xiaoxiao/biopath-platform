/*
 * BioPath public page: the interactive map, budget, coordinates and proof.
 * Needs solver.js loaded first. The page's text and a pre-rendered plan are
 * in the HTML, so nothing disappears if this script does not run.
 */
(function (root) {
  "use strict";

  // maps/cambridgeshire_demo_farm.json, the same synthetic map the scheduled benchmark uses.
  const DEMO_MAP = {
    name: "Cambridgeshire Demo Farm (Publicly Inspired Synthetic)",
    cell_size_m: 1.0,
    ascii: [
      "############################",
      "#............#.............#",
      "#............#.............#",
      "#............#.............#",
      "#..........................#",
      "######.##################..#",
      "#............#............##",
      "#............#.............#",
      "#............#.............#",
      "#.....################.....#",
      "#..........................#",
      "#..........................#",
      "############################",
    ],
  };
  const CAPTURE = { runs: 160, horizon: 48, seed: 7 };
  const SCALE_MAX_M = 20;
  const CELL = 10;

  // matplotlib viridis, sampled.
  const VIRIDIS = [
    [0.0, [68, 1, 84]],
    [0.13, [71, 44, 122]],
    [0.25, [59, 82, 139]],
    [0.38, [44, 114, 142]],
    [0.5, [33, 145, 140]],
    [0.63, [39, 173, 129]],
    [0.75, [94, 201, 98]],
    [0.88, [170, 220, 50]],
    [1.0, [253, 231, 37]],
  ];

  function viridis(t) {
    const x = Math.max(0, Math.min(1, t));
    for (let i = 1; i < VIRIDIS.length; i++) {
      const [t1, c1] = VIRIDIS[i];
      if (x <= t1) {
        const [t0, c0] = VIRIDIS[i - 1];
        const f = (x - t0) / (t1 - t0);
        const c = c0.map((v, j) => Math.round(v + (c1[j] - v) * f));
        return `rgb(${c[0]},${c[1]},${c[2]})`;
      }
    }
    return "rgb(253,231,37)";
  }

  const fmtM = (v) => (Number.isFinite(v) ? `${(Math.round(v * 10) / 10).toFixed(1)} m` : "unreached");
  const fmtWholeM = (v) => (Number.isFinite(v) ? `${Math.round(v)} m` : "unreached");
  const pct = (v) => `${Math.round(v * 100)}%`;

  /** SVG markup for one layer of a plan. Pure string building, also used to pre-render the HTML. */
  function renderSvg(map, layerResult, otherTraps) {
    const w = map.width * CELL;
    const h = map.height * CELL;
    const parts = [];
    parts.push(
      `<svg class="field" viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Synthetic farmyard, ${map.width} by ${map.height} metres, with ${layerResult.traps.length} trap positions and the walking distance from every open cell to the nearest trap.">`
    );
    for (let r = 0; r < map.height; r++) {
      for (let c = 0; c < map.width; c++) {
        const i = r * map.width + c;
        const x = c * CELL;
        const y = r * CELL;
        if (!map.walk[i]) {
          parts.push(`<rect class="wall" data-r="${r}" data-c="${c}" x="${x}" y="${y}" width="${CELL}" height="${CELL}"/>`);
        } else {
          const d = layerResult.distance[i];
          const fill = Number.isFinite(d) ? viridis(d / SCALE_MAX_M) : "#7d8a83";
          parts.push(`<rect class="open" data-r="${r}" data-c="${c}" x="${x}" y="${y}" width="${CELL}" height="${CELL}" fill="${fill}"/>`);
        }
      }
    }
    if (otherTraps) {
      for (const [r, c] of otherTraps) {
        parts.push(`<circle class="ghost" cx="${c * CELL + CELL / 2}" cy="${r * CELL + CELL / 2}" r="3.2"/>`);
      }
    }
    layerResult.traps.forEach(([r, c], n) => {
      const cx = c * CELL + CELL / 2;
      const cy = r * CELL + CELL / 2;
      parts.push(
        `<g class="trap"><circle cx="${cx}" cy="${cy}" r="4.1"/><text x="${cx}" y="${cy + 2.1}">${n + 1}</text></g>`
      );
    });
    parts.push("</svg>");
    return parts.join("");
  }

  function coordsHtml(map, traps) {
    return traps
      .map(([r, c], n) => {
        const x = c * map.cellSize;
        const y = r * map.cellSize;
        return `<li><span class="tn">${n + 1}</span><span class="xy">x&nbsp;${x}, y&nbsp;${y}</span></li>`;
      })
      .join("");
  }

  function proofRows(p) {
    const o = p.optimised;
    const b = p.baseline;
    const ci = (c) => `${pct(c.capture_probability)} <small>(${pct(c.ci95_low)}–${pct(c.ci95_high)})</small>`;
    return [
      ["Average walk to the nearest trap", fmtM(o.metrics.mean_distance_m), fmtM(b.metrics.mean_distance_m)],
      ["95% of the yard is within", fmtWholeM(o.metrics.p95_distance_m), fmtWholeM(b.metrics.p95_distance_m)],
      ["Farthest open ground", fmtWholeM(o.metrics.max_distance_m), fmtWholeM(b.metrics.max_distance_m)],
      [`Wanderers caught within ${CAPTURE.horizon} steps`, ci(o.capture), ci(b.capture)],
    ]
      .map(([label, a, z]) => `<tr><th scope="row">${label}</th><td>${a}</td><td>${z}</td></tr>`)
      .join("");
  }

  function planBundle(map, p) {
    const asTraps = (traps) => traps.map(([r, c]) => ({ row: r, col: c, x_m: c * map.cellSize, y_m: r * map.cellSize }));
    const clean = (m) => {
      const out = {};
      for (const k in m) out[k] = Number.isFinite(m[k]) ? m[k] : "inf";
      return out;
    };
    return {
      name: map.name,
      cell_size_m: map.cellSize,
      ascii: root.BioPathSolver.toAscii(map),
      biopath_browser_demo: {
        note: "Generated in the browser demo on the BioPath page. The map fields above are a valid BioPath map; rerun with the command below.",
        rerun: `python -m biopath.cli solve --map biopath-plan.json --k ${p.k} --objective ${p.objective} --local-improve --out-json out.json`,
        solver_version: p.solver_version,
        objective: p.objective,
        k: p.k,
        created_at: new Date().toISOString(),
        optimised: { traps: asTraps(p.optimised.traps), metrics: clean(p.optimised.metrics), capture_estimate: p.optimised.capture },
        rule_of_thumb_baseline: { traps: asTraps(p.baseline.traps), metrics: clean(p.baseline.metrics), capture_estimate: p.baseline.capture },
        capture_model: "lazy random walk (stays put with probability 0.25), start uniform over open cells; browser random numbers, so estimates differ from a Python run within sampling error",
      },
    };
  }

  function init() {
    const S = root.BioPathSolver;
    const box = document.getElementById("instrument");
    if (!S || !box) return;
    const stage = document.getElementById("fieldStage");
    const kInput = document.getElementById("budget");
    const kOut = document.getElementById("budgetOut");
    const coords = document.getElementById("coords");
    const proof = document.getElementById("proofBody");
    const layerBtns = Array.from(document.querySelectorAll("[data-layer]"));
    const resetBtn = document.getElementById("resetMap");
    const dlBtn = document.getElementById("downloadPlan");
    const note = document.getElementById("editNote");
    const coordsTitle = document.getElementById("coordsTitle");
    const legendShown = document.getElementById("legendShown");
    const legendOther = document.getElementById("legendOther");

    const small = typeof root.matchMedia === "function" && root.matchMedia("(max-width: 600px)").matches;
    const editHint = small
      ? "Tap a cell inside the yard to add or remove a wall (easier on a larger screen)."
      : "Tap any cell inside the yard to add or remove a wall.";
    let map = S.parseMap(DEMO_MAP);
    let layer = "optimised";
    let current = null;

    function draw() {
      const shown = current[layer];
      const other = layer === "optimised" ? current.baseline.traps : current.optimised.traps;
      stage.innerHTML = renderSvg(map, shown, other);
      coords.innerHTML = coordsHtml(map, shown.traps);
      coordsTitle.textContent = layer === "optimised" ? "BioPath's coordinates" : "Rule-of-thumb coordinates";
      if (legendShown && legendOther) {
        legendShown.textContent = layer === "optimised" ? "● numbered: BioPath traps" : "● numbered: rule-of-thumb traps";
        legendOther.textContent = layer === "optimised" ? "◌ small rings: rule-of-thumb traps" : "◌ small rings: BioPath traps";
      }
      layerBtns.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.layer === layer)));
    }

    function solve() {
      const k = Number(kInput.value);
      kOut.textContent = String(k);
      current = S.plan(map, k, CAPTURE);
      proof.innerHTML = proofRows(current);
      draw();
    }

    kInput.addEventListener("input", solve);
    layerBtns.forEach((b) =>
      b.addEventListener("click", () => {
        layer = b.dataset.layer;
        draw();
      })
    );

    stage.addEventListener("click", (ev) => {
      const cell = ev.target.closest("rect[data-r]");
      if (!cell) return;
      const r = Number(cell.dataset.r);
      const c = Number(cell.dataset.c);
      if (r === 0 || c === 0 || r === map.height - 1 || c === map.width - 1) {
        note.textContent = "The outer fence stays. Tap inside the yard.";
        return;
      }
      const ascii = S.toAscii(map);
      const row = ascii[r].split("");
      row[c] = row[c] === "." ? "#" : ".";
      ascii[r] = row.join("");
      const next = S.parseMap({ name: DEMO_MAP.name + " (edited)", cell_size_m: DEMO_MAP.cell_size_m, ascii });
      if (next.walkableCount < 12 || !S.isConnected(next)) {
        note.textContent = "That wall would close off part of the yard. In this demo the yard stays connected.";
        return;
      }
      map = next;
      note.textContent = "Edited map. The plan and the proof are recomputed for it.";
      resetBtn.hidden = false;
      solve();
    });

    resetBtn.addEventListener("click", () => {
      map = S.parseMap(DEMO_MAP);
      resetBtn.hidden = true;
      note.textContent = editHint;
      solve();
    });

    dlBtn.addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(planBundle(map, current), null, 2) + "\n"], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "biopath-plan.json";
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        URL.revokeObjectURL(a.href);
        a.remove();
      }, 0);
    });

    box.classList.add("is-live");
    note.textContent = editHint;
    solve();
  }

  function loadLatestRun() {
    const out = document.getElementById("latestRun");
    if (!out || typeof fetch !== "function") return;
    Promise.all([
      fetch("./data/latest.json", { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)),
      fetch("./data/latest-benchmark.json", { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([run, bench]) => {
        if (!run || !run.run_id || !run.created_at) return;
        const when = new Date(run.created_at);
        if (Number.isNaN(when.getTime())) return;
        const date = when.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
        const time = when.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
        let text = `The job keeps running. Newest run in this copy of the site: ${date}, ${time} UTC, run ${run.run_id}. Capture ${pct(run.capture_probability)} (95% interval ${pct(run.ci95_low)}–${pct(run.ci95_high)})`;
        if (bench && bench.baselines && bench.baselines.heuristic && bench.baselines.random) {
          text += `; rule of thumb ${pct(bench.baselines.heuristic.mean)}; random layouts ${pct(bench.baselines.random.mean)} on average`;
        }
        out.textContent = text + ".";
      })
      .catch(() => {});
  }

  root.BioPathHome = { renderSvg, coordsHtml, proofRows, DEMO_MAP, CAPTURE };
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => {
        init();
        loadLatestRun();
      });
    } else {
      init();
      loadLatestRun();
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
