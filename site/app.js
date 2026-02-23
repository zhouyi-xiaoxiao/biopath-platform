const STORAGE_KEYS = {
  apiBase: "biopath_api_base",
  tourDone: "biopath_tour_completed",
  uiMode: "biopath_ui_mode",
};

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
    "############################",
  ],
};

const TOUR_STEPS = [
  {
    title: "Auto-detect API",
    body: "Click Auto Connect. We check query ?api=..., then saved URL, then site/config.json.",
    focusId: "autoConnect",
  },
  {
    title: "Confirm Health",
    body: "Use Health Check. A green status means the real-time API path is ready.",
    focusId: "healthCheck",
  },
  {
    title: "Load Default Cambridge Map",
    body: "The map textarea starts with the Cambridge demo layout. Keep it for your standard demo.",
    focusId: "mapJson",
  },
  {
    title: "Run Solve",
    body: "Run Solve to generate trap coordinates and core metrics for the current configuration.",
    focusId: "runSolve",
  },
  {
    title: "Run Benchmark and Read Uplift",
    body: "Run Benchmark to produce uplift versus random baseline. Quote this in your proof section.",
    focusId: "runBenchmark",
  },
  {
    title: "Switch to Pitch Mode + Ask",
    body: "Open Pitch Mode, then use the copy buttons in the narrative panel for clean delivery.",
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

function showToast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.remove("hidden");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => el.classList.add("hidden"), 2600);
}

function setConnectionState(mode, details) {
  const pill = $("connectionPill");
  pill.classList.remove("connected", "disconnected", "checking");
  if (mode === "connected") {
    pill.classList.add("connected");
    pill.textContent = "Connected";
  } else if (mode === "checking") {
    pill.classList.add("checking");
    pill.textContent = "Checking";
  } else {
    pill.classList.add("disconnected");
    pill.textContent = "Disconnected";
  }

  $("apiLastChecked").textContent = details || "No health check yet.";
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
    mc_runs: Number($("mcRuns").value || 160),
    time_horizon_steps: Number($("horizon").value || 48),
    seed: Number($("seed").value || 7),
    local_improve: true,
    candidate_rule: "all_walkable",
  };
}

function isNetworkError(error) {
  const msg = String(error && error.message ? error.message : error).toLowerCase();
  return msg.includes("failed to fetch") || msg.includes("network") || msg.includes("disconnected");
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
      externalSignal.addEventListener(
        "abort",
        () => controller.abort(externalSignal.reason || "cancel"),
        { once: true }
      );
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
      if (reason === "timeout") {
        throw new Error("Request timed out");
      }
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

function unique(values) {
  const seen = new Set();
  const out = [];
  for (const value of values) {
    const normalized = normalizeApiBase(value);
    if (!normalized) continue;
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    out.push(normalized);
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
  setApiStatus("Trying URL query -> saved value -> config.json...");

  const queryApi = normalizeApiBase(params.get("api") || "");
  const storedApi = getApiBase();
  const configApi = await readConfigDefaultApi();
  const candidates = unique([queryApi, storedApi, configApi]);

  if (!candidates.length) {
    setConnectionState("disconnected", "No API configured.");
    showConnectionBanner("API not connected", "Paste your API URL and click Auto Connect.");
    setApiStatus("No API candidate found.");
    return false;
  }

  for (const candidate of candidates) {
    const probe = await probeApi(candidate);
    if (probe.ok) {
      const connected = setApiBase(candidate);
      $("apiBase").value = connected;
      setConnectionState("connected", `Connected to ${connected} at ${formatUtc(probe.data?.time)}`);
      hideConnectionBanner();
      setApiStatus(`Connected from auto-detection: ${connected}`);
      if (!quiet) showToast("API connected");
      return true;
    }
  }

  $("apiBase").value = candidates[0] || "";
  setConnectionState("disconnected", "All candidates failed health check.");
  showConnectionBanner(
    "API unreachable",
    "Use Fix in 1 step or replace API URL, then run Health Check."
  );
  setApiStatus("Auto-detection failed: no candidate responded.");
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
    setApiStatus("Health check failed.");
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
      <span class="metric-label">Trap Count</span>
      <strong class="metric-value">${result?.traps?.length || 0}</strong>
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

  const link = $("summaryLink");
  if (result?.artifacts?.summary) {
    link.href = result.artifacts.summary;
    link.textContent = "Open run summary";
  } else {
    link.href = "#";
    link.textContent = "Summary not available";
  }
}

function setCompareBox(text, loading = false) {
  const box = $("compareBox");
  box.textContent = text;
  box.classList.toggle("loading", loading);
}

function setBenchmarkUi(running) {
  $("runBenchmark").disabled = running;
  $("runSolve").disabled = running;
  $("cancelBenchmark").classList.toggle("hidden", !running);
  $("retryBenchmark").classList.add("hidden");
  if (running) {
    setCompareBox("Running benchmark...", true);
  } else {
    $("compareBox").classList.remove("loading");
  }
}

function suggestLowerMcRuns() {
  const current = Number($("mcRuns").value || 160);
  const next = Math.max(40, Math.floor(current * 0.6));
  $("mcRuns").value = String(next);
  return next;
}

async function loadLatestWithFallback() {
  try {
    const result = await callApi("/api/runs/latest", { timeoutMs: 12000 });
    state.latestResult = result;
    renderProof(result, state.latestBenchmark);
    return;
  } catch (_) {
    // continue to fallback
  }

  const fallbackCandidates = ["./runs/latest.json", "./data/latest.json"];
  for (const candidate of fallbackCandidates) {
    try {
      const res = await fetch(candidate);
      if (!res.ok) continue;
      const data = await res.json();
      state.latestResult = data;
      renderProof(data, state.latestBenchmark);
      return;
    } catch (_) {
      // Try next fallback.
    }
  }

  setCompareBox("Fallback latest run is unavailable.");
}

function attachRunList(rows) {
  const list = $("runList");
  list.innerHTML = "";

  if (!rows.length) {
    const li = document.createElement("li");
    li.className = "empty-run";
    li.innerHTML = `
      <span class="run-meta">No runs yet.</span>
      <button id="runFirstBenchmarkNow" class="btn">Run first benchmark now</button>
    `;
    list.appendChild(li);
    const quick = $("runFirstBenchmarkNow");
    quick?.addEventListener("click", () => runBenchmark());
    return;
  }

  rows.forEach((row) => {
    const li = document.createElement("li");
    const cp = typeof row.capture_probability === "number"
      ? `${(row.capture_probability * 100).toFixed(1)}%`
      : "n/a";
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
          return;
        } catch (_) {
          // fallback below
        }
      }
      await loadLatestWithFallback();
    });

    list.appendChild(li);
  });
}

async function loadRunList() {
  try {
    const data = await callApi("/api/runs", { timeoutMs: 15000 });
    attachRunList(data.runs || []);
    return;
  } catch (_) {
    // continue to fallback
  }

  const fallbackCandidates = ["./runs/runs.json", "./data/runs.json"];
  for (const candidate of fallbackCandidates) {
    try {
      const res = await fetch(candidate);
      if (!res.ok) continue;
      const data = await res.json();
      attachRunList(data.runs || []);
      return;
    } catch (_) {
      // Try next fallback.
    }
  }

  const list = $("runList");
  list.innerHTML = '<li class="run-meta">Fallback run history is unavailable.</li>';
}

async function runSolve({ quiet = false } = {}) {
  setMapError("");

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
      timeoutMs: 30000,
    });

    state.latestResult = result;
    renderProof(result, state.latestBenchmark);
    await loadRunList();
    if (!quiet) showToast("Solve completed");
  } catch (error) {
    const message = String(error.message || error);
    setCompareBox(message);
    if (isNetworkError(error)) {
      showConnectionBanner("API unreachable", "Fix API URL and click Auto Connect.");
      setConnectionState("disconnected", "Solve failed due to connection issue.");
    }
    if (!quiet) showToast("Solve failed");
  }
}

function cancelBenchmark() {
  if (!state.benchmarkController) return;
  state.benchmarkCancelledByUser = true;
  state.benchmarkController.abort("cancel");
}

async function runBenchmark({ quiet = false } = {}) {
  setMapError("");

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
      timeoutMs: 45000,
      signal: state.benchmarkController.signal,
    });

    state.latestBenchmark = result;
    state.latestResult = result.run;
    renderProof(result.run, result);
    setCompareBox(pretty(result));
    $("runHint").textContent = "Benchmark complete. Use uplift value in your proof slide.";
    await loadRunList();
    if (!quiet) showToast("Benchmark completed");
  } catch (error) {
    const message = String(error.message || error);

    if (state.benchmarkCancelledByUser || message.includes("cancelled")) {
      setCompareBox("Benchmark cancelled by user.");
      $("runHint").textContent = "Benchmark cancelled. You can run it again anytime.";
      if (!quiet) showToast("Benchmark cancelled");
    } else if (message.toLowerCase().includes("timed out")) {
      const suggested = suggestLowerMcRuns();
      setCompareBox(`Benchmark timed out. Suggested fix: retry with MC Runs ${suggested}.`);
      $("retryBenchmark").classList.remove("hidden");
      $("runHint").textContent = `Timeout detected. MC Runs adjusted to ${suggested}. Retry when ready.`;
      if (!quiet) showToast("Benchmark timed out");
    } else {
      setCompareBox(message);
      $("runHint").textContent = "Benchmark failed. Check API health and map JSON.";
      if (isNetworkError(error)) {
        showConnectionBanner("API unreachable", "Fix API URL and click Auto Connect.");
        setConnectionState("disconnected", "Benchmark failed due to connection issue.");
      }
      if (!quiet) showToast("Benchmark failed");
    }
  } finally {
    setBenchmarkUi(false);
    state.benchmarkController = null;
    state.benchmarkCancelledByUser = false;
  }
}

async function startTwoMinuteDemo() {
  const btn = $("startDemoBtn");
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "Running demo...";

  try {
    let connected = Boolean(getApiBase());
    if (!connected) {
      connected = await autoDetectAndConnect({ quiet: true });
    }
    if (!connected) {
      showToast("Connect API first");
      return;
    }

    $("objective").value = "robust_capture";
    $("kInput").value = "6";

    await runSolve({ quiet: true });
    await runBenchmark({ quiet: true });
    setUiMode("pitch");
    showToast("2-min demo complete. You are in Pitch Mode.");
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

function setUiMode(mode, { persist = true } = {}) {
  const pitch = mode === "pitch";
  document.body.classList.toggle("pitch-mode", pitch);
  $("pitchModeBtn").textContent = pitch ? "Exit Pitch Mode" : "Open Pitch Mode";
  $("mobilePitch").textContent = pitch ? "Exit Pitch" : "Pitch Mode";

  if (persist) {
    localStorage.setItem(STORAGE_KEYS.uiMode, pitch ? "pitch" : "ops");
  }
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
  if (markDone) {
    localStorage.setItem(STORAGE_KEYS.tourDone, "1");
  }
}

function parseQueryMode() {
  if (params.get("pitch") === "1") return "pitch";
  const stored = localStorage.getItem(STORAGE_KEYS.uiMode);
  return stored === "pitch" ? "pitch" : "ops";
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
  $("fixApiBtn").addEventListener("click", () => autoDetectAndConnect());

  $("runSolve").addEventListener("click", () => runSolve());
  $("runBenchmark").addEventListener("click", () => runBenchmark());
  $("cancelBenchmark").addEventListener("click", cancelBenchmark);
  $("retryBenchmark").addEventListener("click", () => runBenchmark());

  $("loadLatest").addEventListener("click", () => loadLatestWithFallback());
  $("startDemoBtn").addEventListener("click", () => startTwoMinuteDemo());

  $("pitchModeBtn").addEventListener("click", () => {
    const next = document.body.classList.contains("pitch-mode") ? "ops" : "pitch";
    setUiMode(next);
  });

  $("mobilePitch").addEventListener("click", () => {
    const next = document.body.classList.contains("pitch-mode") ? "ops" : "pitch";
    setUiMode(next);
  });

  $("mobileSolve").addEventListener("click", () => runSolve());
  $("mobileBenchmark").addEventListener("click", () => runBenchmark());

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
  $("mapJson").value = pretty(DEFAULT_MAP);
  $("proofMetrics").innerHTML = '<article class="metric metric--wide"><span class="metric-label">Status</span><strong class="metric-value">Waiting for first run...</strong></article>';

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
    setApiStatus("Auto-connect failed. You can still view static fallback data.");
  }

  await loadLatestWithFallback();
  await loadRunList();

  const forceTour = params.get("tour") === "1";
  const hasSeenTour = localStorage.getItem(STORAGE_KEYS.tourDone) === "1";
  if (forceTour || !hasSeenTour) {
    openTour();
  }
}

window.addEventListener("DOMContentLoaded", setup);
