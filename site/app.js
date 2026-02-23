const DEFAULT_MAP = {
  name: "Cambridgeshire Demo Farm (Publicly Inspired Synthetic)",
  cell_size_m: 1,
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
    "############################"
  ]
};

const $ = (id) => document.getElementById(id);

function apiBase() {
  const stored = localStorage.getItem("biopath_api_base");
  if (stored) return stored.replace(/\/$/, "");
  return "";
}

function setApiBase(v) {
  localStorage.setItem("biopath_api_base", v.replace(/\/$/, ""));
}

async function callApi(path, options = {}) {
  const base = apiBase();
  if (!base) throw new Error("Set API Base URL first");
  const res = await fetch(base + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

function fmt(value, digits = 3) {
  if (typeof value !== "number" || Number.isNaN(value)) return "n/a";
  return value.toFixed(digits);
}

function renderMetrics(result) {
  const metrics = result.metrics || {};
  const cp = typeof result.capture_probability === "number" ? result.capture_probability : null;
  const rb = typeof result.robust_score === "number" ? result.robust_score : null;
  const objectiveName = result.objective?.name || "n/a";
  const objectiveValue = result.objective?.value;
  $("metrics").innerHTML = `
    <div class="metric-grid">
      <article class="metric metric--wide">
        <span class="metric-label">Run ID</span>
        <strong class="metric-value">${result.run_id || "n/a"}</strong>
      </article>
      <article class="metric metric--wide">
        <span class="metric-label">Objective</span>
        <strong class="metric-value">${objectiveName} = ${fmt(Number(objectiveValue), 4)}</strong>
      </article>
      <article class="metric">
        <span class="metric-label">Capture Probability</span>
        <strong class="metric-value">${cp === null ? "n/a" : `${(cp * 100).toFixed(1)}%`}</strong>
      </article>
      <article class="metric">
        <span class="metric-label">Robust Score</span>
        <strong class="metric-value">${rb === null ? "n/a" : `${(rb * 100).toFixed(1)}%`}</strong>
      </article>
      <article class="metric">
        <span class="metric-label">Mean Distance (m)</span>
        <strong class="metric-value">${fmt(Number(metrics.mean_distance_m), 2)}</strong>
      </article>
      <article class="metric">
        <span class="metric-label">Weighted Mean Distance (m)</span>
        <strong class="metric-value">${fmt(Number(metrics.weighted_mean_distance_m), 2)}</strong>
      </article>
      <article class="metric metric--wide">
        <span class="metric-label">Trap Count</span>
        <strong class="metric-value">${result.traps?.length || 0}</strong>
      </article>
    </div>
  `;
  const link = $("summaryLink");
  if (result.artifacts?.summary) {
    link.href = result.artifacts.summary;
    link.textContent = "Open summary file";
  } else {
    link.href = "#";
    link.textContent = "Summary not available";
  }
}

async function loadRunList() {
  const runList = $("runList");
  runList.innerHTML = "";
  const drawRows = (rows) => {
    if (!rows.length) {
      runList.innerHTML = '<li class="muted">No runs yet.</li>';
      return;
    }
    rows.forEach((r) => {
      const li = document.createElement("li");
      const cp = typeof r.capture_probability === "number" ? `${(r.capture_probability * 100).toFixed(1)}%` : "n/a";
      li.innerHTML = `
        <span class="run-id">${r.run_id}</span>
        <span class="run-meta">${r.objective || "n/a"} · CP ${cp}</span>
      `;
      li.onclick = async () => {
        if (apiBase()) {
          const detail = await callApi(`/api/runs/${r.run_id}`);
          renderMetrics(detail);
        } else {
          await loadLatestWithFallback();
        }
      };
      runList.appendChild(li);
    });
  };
  try {
    const data = await callApi("/api/runs");
    drawRows(data.runs || []);
    return;
  } catch (_) {
    // fallback to static history
  }

  try {
    const res = await fetch("./data/runs.json");
    if (!res.ok) throw new Error("No fallback runs.json");
    const data = await res.json();
    drawRows(data.runs || []);
  } catch (err) {
    runList.innerHTML = `<li class="muted">${err.message}</li>`;
  }
}

async function loadLatestWithFallback() {
  try {
    const result = await callApi("/api/runs/latest");
    renderMetrics(result);
    return;
  } catch (_) {
    // fallback for static hosting
  }
  try {
    const res = await fetch("./data/latest.json");
    if (!res.ok) throw new Error("No fallback latest.json");
    const data = await res.json();
    renderMetrics(data);
  } catch (err) {
    $("metrics").innerHTML = `<p class="muted">${err.message}</p>`;
  }
}

function payloadFromUI() {
  return {
    map_json: JSON.parse($("mapJson").value),
    k: Number($("kInput").value || 5),
    objective: $("objective").value,
    mc_runs: Number($("mcRuns").value || 120),
    time_horizon_steps: Number($("horizon").value || 40),
    seed: Number($("seed").value || 7),
    local_improve: true,
    candidate_rule: "all_walkable",
  };
}

function setup() {
  $("mapJson").value = pretty(DEFAULT_MAP);
  $("apiBase").value = apiBase();

  $("saveApi").onclick = () => {
    setApiBase($("apiBase").value.trim());
    $("apiStatus").textContent = "Saved.";
  };

  $("healthCheck").onclick = async () => {
    try {
      const res = await callApi("/");
      $("apiStatus").textContent = `API OK: ${res.time}`;
    } catch (err) {
      $("apiStatus").textContent = `API check failed: ${err.message}`;
    }
  };

  $("runSolve").onclick = async () => {
    try {
      const result = await callApi("/api/solve", {
        method: "POST",
        body: JSON.stringify(payloadFromUI()),
      });
      renderMetrics(result);
      await loadRunList();
    } catch (err) {
      $("metrics").innerHTML = `<p class="muted">${err.message}</p>`;
    }
  };

  $("runBenchmark").onclick = async () => {
    const box = $("compareBox");
    box.textContent = "Running benchmark...";
    try {
      const result = await callApi("/api/benchmark", {
        method: "POST",
        body: JSON.stringify({ ...payloadFromUI(), baseline_samples: 40 }),
      });
      box.textContent = pretty(result);
      renderMetrics(result.run);
      await loadRunList();
    } catch (err) {
      box.textContent = err.message;
    }
  };

  $("loadLatest").onclick = () => loadLatestWithFallback();

  $("pitchModeBtn").onclick = () => {
    document.body.classList.toggle("pitch-mode");
    const hidden = document.body.classList.contains("pitch-mode");
    ["iterationsCard"].forEach((id) => {
      $(id).style.display = hidden ? "none" : "block";
    });
  };

  loadLatestWithFallback();
  loadRunList();
}

window.addEventListener("DOMContentLoaded", setup);
