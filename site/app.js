const DEFAULT_MAP = {
  name: "Cambridge Synthetic Farm Layout",
  cell_size_m: 1,
  ascii: [
    "########################",
    "#....#........#.......#",
    "#....#........#.......#",
    "#....#........#.......#",
    "#.............#.......#",
    "######.############...#",
    "#........#............#",
    "#........#............#",
    "#........#............#",
    "#........#########....#",
    "#.....................#",
    "########################"
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

function renderMetrics(result) {
  const metrics = result.metrics || {};
  $("metrics").innerHTML = `
    <p><strong>Run:</strong> ${result.run_id || "n/a"}</p>
    <p><strong>Objective:</strong> ${result.objective?.name} = ${result.objective?.value}</p>
    <p><strong>Capture Probability:</strong> ${(result.capture_probability * 100).toFixed(1)}%</p>
    <p><strong>Robust Score:</strong> ${(result.robust_score * 100).toFixed(1)}%</p>
    <p><strong>Mean Distance:</strong> ${metrics.mean_distance_m}</p>
    <p><strong>Weighted Mean Distance:</strong> ${metrics.weighted_mean_distance_m}</p>
    <p><strong>Traps:</strong> ${result.traps?.length || 0}</p>
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
  try {
    const data = await callApi("/api/runs");
    (data.runs || []).forEach((r) => {
      const li = document.createElement("li");
      li.textContent = `${r.run_id} | ${r.objective} | cp=${r.capture_probability ?? "n/a"}`;
      li.onclick = async () => {
        const detail = await callApi(`/api/runs/${r.run_id}`);
        renderMetrics(detail);
      };
      runList.appendChild(li);
    });
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
