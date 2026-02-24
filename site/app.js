const STORAGE_KEYS = {
  apiBase: "biopath_api_base",
  tourDone: "biopath_tour_completed",
  uiMode: "biopath_ui_mode",
};

const UI_MODES = {
  OPS: "ops",
  PITCH_SAFE: "pitch_safe",
  PITCH_LIVE: "pitch_live",
};

const DEFAULT_MAP_URL = "./data/cambridge-photo-informed-map.json";
const CURATED_LATEST_URL = "./data/latest.json";
const CURATED_RUNS_URL = "./data/runs.json";

const DEFAULT_ARTIFACTS = {
  heatmap: "./data/latest-heatmap.png",
  summary: "./assets/cambridge-photo-informed-summary.md",
};

const DEFAULT_MAP_FALLBACK = {
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
    "############################",
  ],
};

const TOUR_STEPS = [
  {
    title: "Auto-detect API",
    body: "Click Auto Connect. We check ?api=..., then saved URL, then site/config.json.",
    focusId: "autoConnect",
  },
  {
    title: "Confirm Health",
    body: "Use Health Check. Connected means you can run live solve and benchmark.",
    focusId: "healthCheck",
  },
  {
    title: "Load Cambridge Map",
    body: "The map box starts with a curated Cambridge-style JSON. Keep it for the standard demo.",
    focusId: "mapJson",
  },
  {
    title: "Run Solve",
    body: "Solve outputs trap coordinates and core metrics in one click.",
    focusId: "runSolve",
  },
  {
    title: "Run Benchmark",
    body: "Benchmark shows uplift against random baseline. This is your proof metric.",
    focusId: "runBenchmark",
  },
  {
    title: "Switch Pitch Mode",
    body: "Use Pitch Safe for stable demo. Use Pitch Live when API is healthy.",
    focusId: "pitchModeBtn",
  },
];

const state = {
  latestResult: null,
  latestBenchmark: null,
  benchmarkController: null,
  benchmarkCancelledByUser: false,
  currentTourStep: 0,
  configDefaultApi: "",
  connected: false,
  currentMode: UI_MODES.PITCH_SAFE,
};

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(window.location.search);

function normalizeApiBase(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

function getApiBase() {
  return normalizeApiBase(localStorage.getItem(STORAGE_KEYS.apiBase));
}

function setApiBase(value) {
  const normalized = normalizeApiBase(value);
  if (!normalized) {
    localStorage.removeItem(STORAGE_KEYS.apiBase);
    return "";
  }
  localStorage.setItem(STORAGE_KEYS.apiBase, normalized);
  return normalized;
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

function fmt(value, digits = 3) {
  if (typeof value !== "number" || Number.isNaN(value)) return "n/a";
  return value.toFixed(digits);
}

function formatUtc(value) {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "n/a";
  return `${date.toLocaleTimeString([], { hour12: false })} UTC`;
}

function toFriendlyError(error) {
  const raw = String(error && error.message ? error.message : error || "Unknown error");
  const msg = raw.toLowerCase();
  if (msg.includes("failed to fetch") || msg.includes("network")) {
    return "Live API is currently unreachable. You can continue with Pitch Safe mode and curated evidence.";
  }
  if (msg.includes("timed out")) {
    return "Benchmark request timed out. Try lower MC Runs and retry.";
  }
  if (msg.includes("api base url is empty")) {
    return "No API configured. Use Auto Connect or continue in Pitch Safe mode.";
  }
  if (msg.includes("cancelled")) {
    return "Benchmark was cancelled.";
  }
  return raw;
}

function resolveArtifactPath(pathValue, kind = "") {
  if (!pathValue) return "";
  const raw = String(pathValue);

  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("./") || raw.startsWith("../")) return raw;

  if (raw.startsWith("runs/")) {
    if (kind === "heatmap") return DEFAULT_ARTIFACTS.heatmap;
    if (kind === "summary") return DEFAULT_ARTIFACTS.summary;
    return "";
  }

  const idx = raw.lastIndexOf("/runs/");
  if (idx >= 0) {
    if (kind === "heatmap") return DEFAULT_ARTIFACTS.heatmap;
    if (kind === "summary") return DEFAULT_ARTIFACTS.summary;
  }

  return raw;
}

function extractArtifact(result, key) {
  const sitePath = result?.artifacts_site?.[key];
  if (sitePath) return resolveArtifactPath(sitePath, key);
  const oldPath = result?.artifacts?.[key];
  if (oldPath) return resolveArtifactPath(oldPath, key);
  return DEFAULT_ARTIFACTS[key] || "";
}

function showToast(message) {
  const el = $("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.remove("hidden");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => el.classList.add("hidden"), 2600);
}

function showConnectionBanner(title, message) {
  $("bannerTitle").textContent = title;
  $("bannerMessage").textContent = message;
  $("connectionBanner").classList.remove("hidden");
}

function hideConnectionBanner() {
  $("connectionBanner").classList.add("hidden");
}

function setApiStatus(message) {
  $("apiStatus").textContent = message;
}

function setConnectionState(mode, details) {
  const pill = $("connectionPill");
  pill.classList.remove("connected", "disconnected", "checking");

  if (mode === "connected") {
    pill.classList.add("connected");
    pill.textContent = "Connected";
    state.connected = true;
  } else if (mode === "checking") {
    pill.classList.add("checking");
    pill.textContent = "Checking";
    state.connected = false;
  } else {
    pill.classList.add("disconnected");
    pill.textContent = "Disconnected";
    state.connected = false;
  }

  $("apiLastChecked").textContent = details || "No health check yet.";
  const liveBtn = $("liveModeBtn");
  if (liveBtn) liveBtn.disabled = !state.connected;

  if (!state.connected && state.currentMode === UI_MODES.PITCH_LIVE) {
    setUiMode(UI_MODES.PITCH_SAFE);
    showToast("Switched to Pitch Safe because API disconnected");
  }
}

function setMapError(message) {
  const el = $("mapError");
  if (!message) {
    el.textContent = "";
    el.classList.add("hidden");
    return;
  }
  el.textContent = message;
  el.classList.remove("hidden");
}

function parseJsonWithLocation(text) {
  try {
    return JSON.parse(text);
  } catch (error) {
    const msg = String(error && error.message ? error.message : "Invalid JSON");
    const match = msg.match(/position\s+(\d+)/i);
    if (!match) {
      throw new Error(`Map JSON error: ${msg}`);
    }

    const position = Number(match[1]);
    const before = text.slice(0, position);
    const lines = before.split("\n");
    const line = lines.length;
    const col = lines[lines.length - 1].length + 1;
    throw new Error(`Map JSON error at line ${line}, column ${col}`);
  }
}

function payloadFromUI() {
  setMapError("");
  const mapText = $("mapJson").value;
  const mapJson = parseJsonWithLocation(mapText);

  return {
    map_json: mapJson,
    k: Number($("kInput").value || 6),
    objective: $("objective").value,
    mc_runs: Number($("mcRuns").value || 140),
    time_horizon_steps: Number($("horizon").value || 48),
    seed: Number($("seed").value || 7),
    local_improve: true,
    candidate_rule: "all_walkable",
  };
}

async function callApi(path, options = {}) {
  const base = getApiBase();
  if (!base) {
    throw new Error("API Base URL is empty. Use Auto Connect first.");
  }

  const timeoutMs = options.timeoutMs || 20000;
  const externalSignal = options.signal;
  const controller = new AbortController();
  let timeoutHandle = null;

  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort(externalSignal.reason || "cancel");
    } else {
      externalSignal.addEventListener("abort", () => controller.abort(externalSignal.reason || "cancel"), { once: true });
    }
  }

  timeoutHandle = window.setTimeout(() => controller.abort("timeout"), timeoutMs);

  try {
    const res = await fetch(base + path, {
      method: options.method || "GET",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      body: options.body,
      signal: controller.signal,
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `HTTP ${res.status}`);
    }

    return await res.json();
  } catch (error) {
    if (controller.signal.aborted) {
      const reason = controller.signal.reason;
      if (reason === "timeout") throw new Error("Request timed out");
      throw new Error("Request cancelled");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutHandle);
  }
}

async function readConfigDefaultApi() {
  if (state.configDefaultApi) return state.configDefaultApi;

  try {
    const res = await fetch("./config.json", { cache: "no-store" });
    if (!res.ok) return "";
    const data = await res.json();
    state.configDefaultApi = normalizeApiBase(data.defaultApiBase || "");
    return state.configDefaultApi;
  } catch (_) {
    return "";
  }
}

async function loadDefaultMap() {
  try {
    const res = await fetch(DEFAULT_MAP_URL, { cache: "no-store" });
    if (!res.ok) return DEFAULT_MAP_FALLBACK;
    const data = await res.json();
    if (!data || typeof data !== "object" || !Array.isArray(data.ascii)) return DEFAULT_MAP_FALLBACK;
    return data;
  } catch (_) {
    return DEFAULT_MAP_FALLBACK;
  }
}

function unique(values) {
  const seen = new Set();
  const out = [];
  for (const value of values) {
    const normalized = normalizeApiBase(value);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    out.push(normalized);
  }
  return out;
}

function runtimeApiCandidates() {
  const out = [];
  const origin = normalizeApiBase(window.location.origin || "");
  if (origin && !origin.includes("github.io")) {
    out.push(origin);
  }
  return out;
}

async function probeApi(base) {
  const normalized = normalizeApiBase(base);
  if (!normalized) return { ok: false };

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort("timeout"), 7000);

  try {
    const res = await fetch(`${normalized}/`, { signal: controller.signal });
    if (!res.ok) return { ok: false };
    const data = await res.json();
    return { ok: true, data };
  } catch (_) {
    return { ok: false };
  } finally {
    window.clearTimeout(timeout);
  }
}

async function autoDetectAndConnect({ quiet = false } = {}) {
  setConnectionState("checking", "Probing API candidates...");
  setApiStatus("Trying URL query -> saved value -> config.json -> same-origin API...");

  const queryApi = normalizeApiBase(params.get("api") || "");
  const storedApi = getApiBase();
  const configApi = await readConfigDefaultApi();
  const runtimeApi = runtimeApiCandidates();
  const candidates = unique([queryApi, storedApi, configApi, ...runtimeApi]);

  if (!candidates.length) {
    setConnectionState("disconnected", "No API configured.");
    showConnectionBanner("API not connected", "Paste your API URL and click Auto Connect.");
    setApiStatus("No API candidate found.");
    return false;
  }

  for (const candidate of candidates) {
    const probe = await probeApi(candidate);
    if (!probe.ok) continue;

    const connected = setApiBase(candidate);
    $("apiBase").value = connected;
    setConnectionState("connected", `Connected to ${connected} at ${formatUtc(probe.data?.time)}`);
    hideConnectionBanner();
    setApiStatus(`Connected from auto-detection: ${connected}`);
    if (!quiet) showToast("API connected");
    return true;
  }

  $("apiBase").value = candidates[0] || "";
  setConnectionState("disconnected", "All candidates failed health check.");
  showConnectionBanner("API unreachable", "Use Fix in 1 step or replace API URL, then run Health Check.");
  setApiStatus("Auto-detection failed. You can still run Pitch Safe mode.");
  return false;
}

async function runHealthCheck() {
  const candidate = normalizeApiBase($("apiBase").value);
  if (!candidate) {
    showConnectionBanner("API missing", "Enter API URL first, then run Health Check.");
    setConnectionState("disconnected", "API URL is empty.");
    setApiStatus("Cannot run health check without API URL.");
    return false;
  }

  setConnectionState("checking", `Checking ${candidate} ...`);
  const probe = await probeApi(candidate);
  if (!probe.ok) {
    setConnectionState("disconnected", `Health check failed for ${candidate}.`);
    showConnectionBanner("API unreachable", "Fix API URL and click Health Check again.");
    setApiStatus("Health check failed. Pitch Safe mode remains available.");
    return false;
  }

  const connected = setApiBase(candidate);
  $("apiBase").value = connected;
  setConnectionState("connected", `Connected to ${connected} at ${formatUtc(probe.data?.time)}`);
  hideConnectionBanner();
  setApiStatus("Health check passed.");
  showToast("Health check passed");
  return true;
}

function setCompareBox(text, loading = false) {
  const box = $("compareBox");
  if (!box) return;
  box.textContent = text;
  box.classList.toggle("loading", loading);
}

function setBenchmarkUi(running) {
  $("runBenchmark").disabled = running;
  $("runSolve").disabled = running;
  $("cancelBenchmark").classList.toggle("hidden", !running);
  $("retryBenchmark").classList.add("hidden");
  if (running) {
    setCompareBox("Running benchmark and preparing proof metrics...", true);
  } else {
    $("compareBox").classList.remove("loading");
  }
}

function suggestLowerMcRuns() {
  const current = Number($("mcRuns").value || 140);
  const next = Math.max(40, Math.floor(current * 0.65));
  $("mcRuns").value = String(next);
  return next;
}

function updateHeroProof(result, benchmark = null) {
  const cp = typeof result?.capture_probability === "number" ? `${(result.capture_probability * 100).toFixed(1)}%` : "n/a";
  const robust = typeof result?.robust_score === "number" ? `${(result.robust_score * 100).toFixed(1)}%` : "n/a";
  const runId = result?.run_id || "n/a";
  const trapCount = Array.isArray(result?.traps) ? result.traps.length : 0;

  const uplift = benchmark && typeof benchmark.uplift_vs_random_mean === "number"
    ? benchmark.uplift_vs_random_mean
    : null;
  const baseline = benchmark && benchmark.baseline && typeof benchmark.baseline.mean === "number"
    ? benchmark.baseline.mean
    : null;

  $("heroRunId").textContent = runId;
  $("heroCapture").textContent = cp;
  $("heroRobust").textContent = robust;
  $("heroTrapCount").textContent = `${trapCount}`;

  if (uplift === null) {
    $("heroUplift").textContent = "Run benchmark to compute uplift";
  } else if (baseline && baseline > 0) {
    $("heroUplift").textContent = `+${((uplift / baseline) * 100).toFixed(1)}% vs random`;
  } else {
    $("heroUplift").textContent = `+${fmt(uplift, 3)} absolute`;
  }
}

function renderProof(result, benchmark = null) {
  const proof = $("proofMetrics");
  const metrics = result?.metrics || {};
  const cp = typeof result?.capture_probability === "number" ? `${(result.capture_probability * 100).toFixed(1)}%` : "n/a";
  const rb = typeof result?.robust_score === "number" ? `${(result.robust_score * 100).toFixed(1)}%` : "n/a";
  const runId = result?.run_id || "n/a";

  proof.innerHTML = `
    <article class="metric metric--wide">
      <span class="metric-label">Run ID</span>
      <strong class="metric-value">${runId}</strong>
    </article>
    <article class="metric">
      <span class="metric-label">Capture Probability</span>
      <strong class="metric-value">${cp}</strong>
    </article>
    <article class="metric">
      <span class="metric-label">Robust Score</span>
      <strong class="metric-value">${rb}</strong>
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
      <span class="metric-label">Trap Coordinates</span>
      <strong class="metric-value">${Array.isArray(result?.traps) ? result.traps.length : 0}</strong>
    </article>
  `;

  const uplift = benchmark && typeof benchmark.uplift_vs_random_mean === "number"
    ? benchmark.uplift_vs_random_mean
    : null;
  const baseline = benchmark && benchmark.baseline && typeof benchmark.baseline.mean === "number"
    ? benchmark.baseline.mean
    : null;

  $("upliftValue").textContent = uplift === null ? "n/a" : fmt(uplift, 4);
  $("baselineValue").textContent = baseline === null ? "n/a" : fmt(baseline, 4);
  $("benchmarkState").textContent = benchmark ? "Benchmark complete" : "No benchmark yet";

  const summaryPath = extractArtifact(result, "summary");
  const link = $("summaryLink");
  const fallback = $("summaryFallback");

  if (summaryPath) {
    link.href = summaryPath;
    link.textContent = "Open run summary";
    link.classList.remove("hidden");
    fallback.textContent = "If this link is unavailable on your network, use the one-page guide script and proof panel values below.";
  } else {
    link.href = "#";
    link.classList.add("hidden");
    fallback.textContent = "Summary link unavailable. Use the proof metrics and ask line directly.";
  }

  const preview = $("cambridgeHeatmapPreview");
  const heatmapPath = extractArtifact(result, "heatmap") || DEFAULT_ARTIFACTS.heatmap;
  preview.onerror = () => {
    if (preview.dataset.fallbackApplied === "1") return;
    preview.dataset.fallbackApplied = "1";
    preview.src = DEFAULT_ARTIFACTS.heatmap;
  };
  preview.dataset.fallbackApplied = "0";
  preview.src = `${heatmapPath}?ts=${Date.now()}`;

  updateHeroProof(result, benchmark);
}

function setPitchNarrative(result, benchmark = null) {
  const cp = typeof result?.capture_probability === "number" ? `${(result.capture_probability * 100).toFixed(1)}%` : "n/a";
  const rb = typeof result?.robust_score === "number" ? `${(result.robust_score * 100).toFixed(1)}%` : "n/a";

  const uplift = benchmark && typeof benchmark.uplift_vs_random_mean === "number"
    ? benchmark.uplift_vs_random_mean
    : null;
  const baseline = benchmark && benchmark.baseline && typeof benchmark.baseline.mean === "number"
    ? benchmark.baseline.mean
    : null;

  let proofLine = `Latest run shows capture probability ${cp} and robust score ${rb}.`;
  if (uplift !== null && baseline && baseline > 0) {
    proofLine += ` Uplift versus random baseline is +${((uplift / baseline) * 100).toFixed(1)}%.`;
  }

  const askLine = "We are currently applying CREGS + LINCAM PoC and ask for 2 pilot introductions, one 8-week data access trial, and support for a £5k-£20k PoC application.";

  $("narrativeProof").textContent = proofLine;
  $("proofCopy").setAttribute("data-copy", proofLine);
  $("askLine").textContent = askLine;
  $("askCopy").setAttribute("data-copy", askLine);
}

function setNoApiFriendlyState() {
  setCompareBox(
    "Live API is not connected. Pitch Safe mode is active with curated evidence, so you can continue the demo without interruption."
  );
  const fallback = $("summaryFallback");
  fallback.textContent = "Pitch Safe mode uses curated run artifacts for reliable presentation.";
}

async function loadCuratedLatest() {
  try {
    const res = await fetch(CURATED_LATEST_URL, { cache: "no-store" });
    if (!res.ok) throw new Error("Curated latest not found");
    const data = await res.json();
    state.latestResult = data;
    state.latestBenchmark = null;
    renderProof(data, null);
    setPitchNarrative(data, null);
    return true;
  } catch (_) {
    setCompareBox("Curated latest dataset is unavailable. Add site/data/latest.json before presenting.");
    return false;
  }
}

async function loadLatestFromApi() {
  const result = await callApi("/api/runs/latest", { timeoutMs: 12000 });
  state.latestResult = result;
  renderProof(result, state.latestBenchmark);
  setPitchNarrative(result, state.latestBenchmark);
}

async function loadLatestWithFallback({ preferApi = false } = {}) {
  if (preferApi && getApiBase()) {
    try {
      await loadLatestFromApi();
      return;
    } catch (error) {
      setCompareBox(toFriendlyError(error));
    }
  }

  await loadCuratedLatest();
}

function attachRunList(rows) {
  const list = $("runList");
  list.innerHTML = "";

  if (!rows.length) {
    const li = document.createElement("li");
    li.className = "empty-run";
    li.innerHTML = `
      <span class="run-meta">No run history available.</span>
      <span class="run-id">Use Pitch Safe mode or run a live benchmark.</span>
    `;
    list.appendChild(li);
    return;
  }

  rows.forEach((row) => {
    const li = document.createElement("li");
    const cp = typeof row.capture_probability === "number" ? `${(row.capture_probability * 100).toFixed(1)}%` : "n/a";
    li.innerHTML = `
      <span class="run-id">${row.run_id}</span>
      <span class="run-meta">${row.objective || "n/a"} - CP ${cp}</span>
    `;

    li.addEventListener("click", async () => {
      if (getApiBase()) {
        try {
          const detail = await callApi(`/api/runs/${row.run_id}`, { timeoutMs: 15000 });
          state.latestResult = detail;
          renderProof(detail, state.latestBenchmark);
          setPitchNarrative(detail, state.latestBenchmark);
          return;
        } catch (_) {
          // Continue to curated fallback.
        }
      }
      await loadCuratedLatest();
    });

    list.appendChild(li);
  });
}

async function loadRunList() {
  if (getApiBase()) {
    try {
      const data = await callApi("/api/runs", { timeoutMs: 15000 });
      attachRunList(data.runs || []);
      return;
    } catch (_) {
      // continue to fallback
    }
  }

  try {
    const res = await fetch(CURATED_RUNS_URL, { cache: "no-store" });
    if (!res.ok) throw new Error("fallback unavailable");
    const data = await res.json();
    attachRunList(data.runs || []);
  } catch (_) {
    const list = $("runList");
    list.innerHTML = '<li class="run-meta">Run history unavailable.</li>';
  }
}

async function runSolve({ quiet = false } = {}) {
  setMapError("");

  if (!getApiBase()) {
    setNoApiFriendlyState();
    showConnectionBanner("API not connected", "Use Auto Connect for live mode, or continue in Pitch Safe mode.");
    if (!quiet) showToast("No API. Continuing with Pitch Safe evidence.");
    setUiMode(UI_MODES.PITCH_SAFE);
    return;
  }

  let payload;
  try {
    payload = payloadFromUI();
  } catch (error) {
    setMapError(String(error.message || error));
    return;
  }

  try {
    const result = await callApi("/api/solve", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 60000,
    });

    state.latestResult = result;
    renderProof(result, state.latestBenchmark);
    setPitchNarrative(result, state.latestBenchmark);
    await loadRunList();
    if (!quiet) showToast("Solve completed");
  } catch (error) {
    setCompareBox(toFriendlyError(error));
    if (!quiet) showToast("Solve could not complete");
  }
}

function cancelBenchmark() {
  if (!state.benchmarkController) return;
  state.benchmarkCancelledByUser = true;
  state.benchmarkController.abort("cancel");
}

async function runBenchmark({ quiet = false } = {}) {
  setMapError("");

  if (!getApiBase()) {
    setNoApiFriendlyState();
    showConnectionBanner("API not connected", "Benchmark requires API. Pitch Safe mode remains available.");
    if (!quiet) showToast("Benchmark skipped (no API)");
    setUiMode(UI_MODES.PITCH_SAFE);
    return;
  }

  let payload;
  try {
    payload = payloadFromUI();
  } catch (error) {
    setMapError(String(error.message || error));
    return;
  }

  state.benchmarkController = new AbortController();
  state.benchmarkCancelledByUser = false;
  setBenchmarkUi(true);

  try {
    const result = await callApi("/api/benchmark", {
      method: "POST",
      body: JSON.stringify({ ...payload, baseline_samples: 40 }),
      timeoutMs: 120000,
      signal: state.benchmarkController.signal,
    });

    state.latestBenchmark = result;
    state.latestResult = result.run;
    renderProof(result.run, result);
    setPitchNarrative(result.run, result);
    setCompareBox(pretty(result));
    $("runHint").textContent = "Benchmark complete. Quote uplift and robust score in your proof segment.";
    await loadRunList();
    if (!quiet) showToast("Benchmark completed");
  } catch (error) {
    const msg = toFriendlyError(error);
    if (state.benchmarkCancelledByUser) {
      setCompareBox("Benchmark cancelled by user.");
    } else if (msg.toLowerCase().includes("timed out")) {
      const suggested = suggestLowerMcRuns();
      setCompareBox(`Benchmark timed out. Suggested MC Runs: ${suggested}. Click retry after updating.`);
      $("retryBenchmark").classList.remove("hidden");
    } else {
      setCompareBox(msg);
    }
    if (!quiet) showToast("Benchmark could not complete");
  } finally {
    setBenchmarkUi(false);
    state.benchmarkController = null;
    state.benchmarkCancelledByUser = false;
  }
}

function resetDemoState() {
  $("objective").value = "robust_capture";
  $("kInput").value = "6";
  $("mcRuns").value = "140";
  $("horizon").value = "48";
  $("seed").value = "7";

  state.latestBenchmark = null;
  setCompareBox("Demo reset complete. Use Solve -> Benchmark for live proof, or stay in Pitch Safe mode.");
  loadCuratedLatest();
  setUiMode(UI_MODES.PITCH_SAFE);
  showToast("Demo reset");
}

async function startTwoMinuteDemo() {
  const btn = $("startDemoBtn");
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "Running demo...";

  try {
    let connected = Boolean(getApiBase());
    if (!connected) connected = await autoDetectAndConnect({ quiet: true });

    if (!connected) {
      await loadCuratedLatest();
      setNoApiFriendlyState();
      setUiMode(UI_MODES.PITCH_SAFE);
      showToast("Pitch Safe demo ready");
      return;
    }

    $("objective").value = "robust_capture";
    $("kInput").value = "6";
    await runSolve({ quiet: true });
    await runBenchmark({ quiet: true });
    setUiMode(UI_MODES.PITCH_LIVE);
    showToast("2-minute live demo complete");
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

function setUiMode(mode, { persist = true } = {}) {
  let nextMode = mode;
  if (mode === UI_MODES.PITCH_LIVE && !state.connected) {
    nextMode = UI_MODES.PITCH_SAFE;
  }

  state.currentMode = nextMode;
  const body = document.body;
  body.classList.remove("ui-ops", "ui-pitch-safe", "ui-pitch-live");

  if (nextMode === UI_MODES.OPS) body.classList.add("ui-ops");
  if (nextMode === UI_MODES.PITCH_SAFE) body.classList.add("ui-pitch-safe");
  if (nextMode === UI_MODES.PITCH_LIVE) body.classList.add("ui-pitch-live");

  $("pitchModeBtn").textContent = nextMode === UI_MODES.OPS ? "Switch to Pitch Safe" : "Open Ops Panel";
  $("liveModeBtn").textContent = nextMode === UI_MODES.PITCH_LIVE ? "Switch to Pitch Safe" : "Switch to Pitch Live";
  $("modeBadge").textContent = nextMode === UI_MODES.PITCH_LIVE
    ? "Pitch Live"
    : nextMode === UI_MODES.PITCH_SAFE
      ? "Pitch Safe"
      : "Ops";

  if (persist) localStorage.setItem(STORAGE_KEYS.uiMode, nextMode);
}

function parseQueryMode() {
  if (params.get("pitch") === "1") return UI_MODES.PITCH_SAFE;
  const stored = localStorage.getItem(STORAGE_KEYS.uiMode);
  if (stored && Object.values(UI_MODES).includes(stored)) return stored;
  return UI_MODES.PITCH_SAFE;
}

function highlightTourTarget(id) {
  if (!id) return;
  const target = $(id);
  if (!target) return;
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.classList.add("tour-focus");
  window.setTimeout(() => target.classList.remove("tour-focus"), 1200);
}

function renderTourStep() {
  const step = TOUR_STEPS[state.currentTourStep];
  $("tourStepBadge").textContent = `Step ${state.currentTourStep + 1} / ${TOUR_STEPS.length}`;
  $("tourTitle").textContent = step.title;
  $("tourBody").textContent = step.body;
  $("tourBack").disabled = state.currentTourStep === 0;
  $("tourNext").textContent = state.currentTourStep === TOUR_STEPS.length - 1 ? "Finish" : "Next";
  highlightTourTarget(step.focusId);
}

function openTour() {
  state.currentTourStep = 0;
  $("tourBackdrop").classList.remove("hidden");
  renderTourStep();
}

function closeTour(markDone = true) {
  $("tourBackdrop").classList.add("hidden");
  if (markDone) localStorage.setItem(STORAGE_KEYS.tourDone, "1");
}

function bindCopyButtons() {
  document.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const text = btn.getAttribute("data-copy") || "";
      try {
        await navigator.clipboard.writeText(text);
      } catch (_) {
        const area = document.createElement("textarea");
        area.value = text;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        document.body.removeChild(area);
      }
      showToast("Copied");
    });
  });
}

function bindEvents() {
  $("saveApi").addEventListener("click", () => {
    const value = setApiBase($("apiBase").value);
    $("apiBase").value = value;
    setApiStatus("Saved API URL. Run Health Check to verify.");
    showToast("API URL saved");
  });

  $("autoConnect").addEventListener("click", () => autoDetectAndConnect());
  $("healthCheck").addEventListener("click", () => runHealthCheck());
  $("fixApiBtn").addEventListener("click", async () => {
    const ok = await autoDetectAndConnect();
    if (!ok) {
      setUiMode(UI_MODES.OPS);
      setApiStatus("No healthy API found. Paste API URL and click Health Check, or run: bash scripts/start_public_demo.sh");
      $("apiBase").focus();
    }
  });
  $("autoConnectHero")?.addEventListener("click", () => autoDetectAndConnect());
  $("healthCheckHero")?.addEventListener("click", () => runHealthCheck());

  $("runSolve").addEventListener("click", () => runSolve());
  $("runBenchmark").addEventListener("click", () => runBenchmark());
  $("cancelBenchmark").addEventListener("click", cancelBenchmark);
  $("retryBenchmark").addEventListener("click", () => runBenchmark());
  $("loadLatest").addEventListener("click", () => loadLatestWithFallback({ preferApi: true }));

  $("startDemoBtn").addEventListener("click", () => startTwoMinuteDemo());
  $("resetDemoBtn").addEventListener("click", () => resetDemoState());

  $("pitchModeBtn").addEventListener("click", () => {
    const next = state.currentMode === UI_MODES.OPS ? UI_MODES.PITCH_SAFE : UI_MODES.OPS;
    setUiMode(next);
  });

  $("liveModeBtn").addEventListener("click", () => {
    if (!state.connected) {
      showToast("Live API mode requires a healthy API connection");
      return;
    }
    const next = state.currentMode === UI_MODES.PITCH_LIVE ? UI_MODES.PITCH_SAFE : UI_MODES.PITCH_LIVE;
    setUiMode(next);
  });

  $("helpBtn").addEventListener("click", openTour);

  $("tourSkip").addEventListener("click", () => closeTour(true));
  $("tourBack").addEventListener("click", () => {
    state.currentTourStep = Math.max(0, state.currentTourStep - 1);
    renderTourStep();
  });
  $("tourNext").addEventListener("click", () => {
    if (state.currentTourStep >= TOUR_STEPS.length - 1) {
      closeTour(true);
      return;
    }
    state.currentTourStep += 1;
    renderTourStep();
  });

  bindCopyButtons();
}

async function setup() {
  const defaultMap = await loadDefaultMap();
  $("mapJson").value = pretty(defaultMap);

  $("proofMetrics").innerHTML = '<article class="metric metric--wide"><span class="metric-label">Status</span><strong class="metric-value">Loading curated evidence...</strong></article>';
  setCompareBox("Loading curated baseline for stable demo...");

  const queryApi = normalizeApiBase(params.get("api") || "");
  if (queryApi) {
    $("apiBase").value = queryApi;
  } else {
    $("apiBase").value = getApiBase();
  }

  bindEvents();
  setUiMode(parseQueryMode(), { persist: false });

  const connected = await autoDetectAndConnect({ quiet: true });
  if (!connected) {
    setApiStatus("Auto-connect failed. Pitch Safe mode is ready with curated evidence.");
    setNoApiFriendlyState();
  }

  await loadLatestWithFallback({ preferApi: false });
  await loadRunList();

  const forceTour = params.get("tour") === "1";
  const tourDone = localStorage.getItem(STORAGE_KEYS.tourDone) === "1";
  if (forceTour || !tourDone) openTour();
}

window.addEventListener("DOMContentLoaded", setup);
