const state = {
  mapData: null,
  distanceMap: null,
  traps: [],
  metrics: {},
  objective: null,
  coverageRadius: null,
  viewMode: "distance",
  editor: {
    tool: "walkable",
    weightValue: 1,
    drawing: false,
  },
};

const elements = {
  sampleSelect: document.getElementById("sampleSelect"),
  loadSample: document.getElementById("loadSample"),
  mapFile: document.getElementById("mapFile"),
  exportMap: document.getElementById("exportMap"),
  exportResults: document.getElementById("exportResults"),
  mapName: document.getElementById("mapName"),
  cellSize: document.getElementById("cellSize"),
  gridWidth: document.getElementById("gridWidth"),
  gridHeight: document.getElementById("gridHeight"),
  createMap: document.getElementById("createMap"),
  applyMeta: document.getElementById("applyMeta"),
  paintTool: document.getElementById("paintTool"),
  weightValue: document.getElementById("weightValue"),
  clearWeights: document.getElementById("clearWeights"),
  runSolve: document.getElementById("runSolve"),
  mapMeta: document.getElementById("mapMeta"),
  scaleInfo: document.getElementById("scaleInfo"),
  statusMessage: document.getElementById("statusMessage"),
  canvas: document.getElementById("mapCanvas"),
  viewMode: document.getElementById("viewMode"),
  objectiveValue: document.getElementById("objectiveValue"),
  metricsGrid: document.getElementById("metricsGrid"),
  trapList: document.getElementById("trapList"),
  kInput: document.getElementById("kInput"),
  candidateRule: document.getElementById("candidateRule"),
  minWallNeighbors: document.getElementById("minWallNeighbors"),
  objectiveSelect: document.getElementById("objectiveSelect"),
  coverageRadius: document.getElementById("coverageRadius"),
  localImprove: document.getElementById("localImprove"),
};

function setStatus(message) {
  elements.statusMessage.textContent = message || "";
}

function formatMetric(value) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (value === "inf") {
    return "inf";
  }
  if (typeof value === "number") {
    return value.toFixed(3);
  }
  return String(value);
}

function formatPercent(value) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (value === "inf") {
    return "inf";
  }
  if (typeof value === "number") {
    return `${(value * 100).toFixed(1)}%`;
  }
  return String(value);
}

function slugify(value) {
  return String(value || "map")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function invalidateSolve() {
  state.distanceMap = null;
  state.traps = [];
  state.metrics = {};
  state.objective = null;
  state.coverageRadius = null;
  updateResults();
}

function syncMapInputs(mapData) {
  if (!mapData) {
    return;
  }
  elements.mapName.value = mapData.name || "";
  elements.cellSize.value = mapData.cell_size_m || 1.0;
  elements.gridWidth.value = mapData.ascii?.[0]?.length || 0;
  elements.gridHeight.value = mapData.ascii?.length || 0;
}

function ensureWeights() {
  if (!state.mapData) {
    return null;
  }
  const ascii = state.mapData.ascii;
  const height = ascii.length;
  const width = ascii[0]?.length || 0;
  const weights = state.mapData.weights;
  if (
    !weights ||
    weights.length !== height ||
    weights[0]?.length !== width
  ) {
    const nextWeights = [];
    for (let r = 0; r < height; r += 1) {
      const row = [];
      for (let c = 0; c < width; c += 1) {
        row.push(ascii[r][c] === "." ? 1 : 0);
      }
      nextWeights.push(row);
    }
    state.mapData.weights = nextWeights;
  }
  return state.mapData.weights;
}

function setCell(row, col, value) {
  const ascii = state.mapData.ascii;
  const rowStr = ascii[row];
  ascii[row] = `${rowStr.slice(0, col)}${value}${rowStr.slice(col + 1)}`;
}

function applyTool(row, col) {
  if (!state.mapData) {
    return;
  }
  const ascii = state.mapData.ascii;
  if (row < 0 || col < 0 || row >= ascii.length || col >= ascii[0].length) {
    return;
  }
  const tool = state.editor.tool;
  if (tool === "obstacle") {
    setCell(row, col, "#");
    if (state.mapData.weights) {
      state.mapData.weights[row][col] = 0;
    }
  } else if (tool === "walkable") {
    setCell(row, col, ".");
    if (state.mapData.weights) {
      state.mapData.weights[row][col] = 1;
    }
  } else if (tool === "weight") {
    const weight = Number(state.editor.weightValue || 0);
    const weights = ensureWeights();
    setCell(row, col, ".");
    if (weights) {
      weights[row][col] = Math.max(0, weight);
    }
  }
  invalidateSolve();
  updateMeta();
  drawMap();
}

function updateMeta() {
  if (!state.mapData) {
    elements.mapMeta.textContent = "Load a sample or upload a map.";
    elements.scaleInfo.textContent = "";
    return;
  }
  const { name, cell_size_m: cellSize, ascii, weights } = state.mapData;
  const height = ascii.length;
  const width = ascii[0]?.length || 0;
  let weightInfo = "uniform weights";
  if (weights) {
    let minWeight = Infinity;
    let maxWeight = -Infinity;
    for (const row of weights) {
      for (const value of row) {
        if (typeof value !== "number") {
          continue;
        }
        minWeight = Math.min(minWeight, value);
        maxWeight = Math.max(maxWeight, value);
      }
    }
    if (!Number.isFinite(minWeight)) {
      weightInfo = "weights loaded";
    } else {
      weightInfo = `weights ${minWeight.toFixed(1)}-${maxWeight.toFixed(1)}`;
    }
  }
  elements.mapMeta.textContent = `${name} | ${width}x${height} cells | ${cellSize} m/cell | ${weightInfo}`;
}

function colorForDistance(value, min, max) {
  if (value < 0) {
    return "#6f6f6f";
  }
  if (max <= min) {
    return "#9bbf8f";
  }
  const t = (value - min) / (max - min);
  const hue = 120 - t * 80;
  const light = 62 - t * 16;
  return `hsl(${hue}, 55%, ${light}%)`;
}

function lerpColor(start, end, t) {
  const sr = parseInt(start.slice(1, 3), 16);
  const sg = parseInt(start.slice(3, 5), 16);
  const sb = parseInt(start.slice(5, 7), 16);
  const er = parseInt(end.slice(1, 3), 16);
  const eg = parseInt(end.slice(3, 5), 16);
  const eb = parseInt(end.slice(5, 7), 16);
  const r = Math.round(sr + (er - sr) * t);
  const g = Math.round(sg + (eg - sg) * t);
  const b = Math.round(sb + (eb - sb) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

function colorForWeight(value, max) {
  const t = max > 0 ? Math.min(Math.max(value / max, 0), 1) : 0;
  return lerpColor("#efe7d4", "#b24c2a", t);
}

function drawMap() {
  const ctx = elements.canvas.getContext("2d");
  if (!state.mapData) {
    ctx.clearRect(0, 0, elements.canvas.width, elements.canvas.height);
    return;
  }
  const ascii = state.mapData.ascii;
  const height = ascii.length;
  const width = ascii[0]?.length || 0;

  const maxDim = Math.max(width, height, 1);
  const target = window.innerWidth < 900 ? 320 : 520;
  const cellPx = Math.max(8, Math.min(24, Math.floor(target / maxDim)));
  elements.canvas.width = width * cellPx;
  elements.canvas.height = height * cellPx;

  const viewMode = state.viewMode;
  const distanceMap = viewMode === "distance" ? state.distanceMap : null;
  const weightMap = viewMode === "weights" ? state.mapData.weights : null;
  let minDist = Infinity;
  let maxDist = -Infinity;
  if (distanceMap) {
    for (const row of distanceMap) {
      for (const value of row) {
        if (value === null || value < 0) {
          continue;
        }
        minDist = Math.min(minDist, value);
        maxDist = Math.max(maxDist, value);
      }
    }
    if (!Number.isFinite(minDist)) {
      minDist = 0;
      maxDist = 1;
    }
  }

  let maxWeight = 0;
  if (weightMap) {
    for (const row of weightMap) {
      for (const value of row) {
        if (typeof value !== "number") {
          continue;
        }
        maxWeight = Math.max(maxWeight, value);
      }
    }
  }

  for (let r = 0; r < height; r += 1) {
    for (let c = 0; c < width; c += 1) {
      const cell = ascii[r][c];
      let fill = "#efe7d4";
      if (cell === "#") {
        fill = "#2c2b28";
      } else if (distanceMap) {
        const value = distanceMap[r][c];
        if (value === null) {
          fill = "#2c2b28";
        } else {
          fill = colorForDistance(value, minDist, maxDist);
        }
      } else if (weightMap) {
        const value = weightMap[r][c];
        fill = colorForWeight(typeof value === "number" ? value : 0, maxWeight);
      }
      ctx.fillStyle = fill;
      ctx.fillRect(c * cellPx, r * cellPx, cellPx, cellPx);
    }
  }

  if (state.traps.length) {
    ctx.strokeStyle = "#b24c2a";
    ctx.lineWidth = Math.max(2, Math.round(cellPx / 6));
    const pad = cellPx * 0.2;
    for (const trap of state.traps) {
      const x = trap.col * cellPx;
      const y = trap.row * cellPx;
      ctx.beginPath();
      ctx.moveTo(x + pad, y + pad);
      ctx.lineTo(x + cellPx - pad, y + cellPx - pad);
      ctx.moveTo(x + cellPx - pad, y + pad);
      ctx.lineTo(x + pad, y + cellPx - pad);
      ctx.stroke();
    }
  }

  elements.scaleInfo.textContent = `Grid scale: ${cellPx}px per cell`;
}

function renderMetrics() {
  elements.metricsGrid.innerHTML = "";
  if (!state.metrics) {
    return;
  }
  const items = [
    { label: "Mean (m)", key: "mean_distance_m" },
    { label: "Weighted mean (m)", key: "weighted_mean_distance_m" },
    { label: "Max (m)", key: "max_distance_m" },
    { label: "P95 (m)", key: "p95_distance_m" },
  ];
  for (const item of items) {
    const card = document.createElement("div");
    card.className = "metric-card";
    card.innerHTML = `<span>${item.label}</span><strong>${formatMetric(
      state.metrics[item.key]
    )}</strong>`;
    elements.metricsGrid.appendChild(card);
  }

  if (state.coverageRadius !== null && state.coverageRadius !== undefined) {
    const coverageItems = [
      { label: "Coverage", key: "coverage_within_radius" },
      { label: "Weighted coverage", key: "weighted_coverage_within_radius" },
    ];
    for (const item of coverageItems) {
      const card = document.createElement("div");
      card.className = "metric-card";
      card.innerHTML = `<span>${item.label}</span><strong>${formatPercent(
        state.metrics[item.key]
      )}</strong>`;
      elements.metricsGrid.appendChild(card);
    }
  }
}

function renderTraps() {
  elements.trapList.innerHTML = "";
  if (!state.traps.length) {
    elements.trapList.textContent = "No traps computed.";
    return;
  }
  for (const trap of state.traps) {
    const item = document.createElement("div");
    item.className = "trap-item";
    item.textContent = `(${trap.row}, ${trap.col}) -> (${trap.x_m.toFixed(
      2
    )}m, ${trap.y_m.toFixed(2)}m)`;
    elements.trapList.appendChild(item);
  }
}

function updateResults() {
  if (!state.objective) {
    elements.objectiveValue.textContent = "No run yet.";
    elements.metricsGrid.innerHTML = "";
    elements.trapList.textContent = state.mapData ? "No traps computed." : "";
    return;
  }
  const value = formatMetric(state.objective.value);
  elements.objectiveValue.textContent = `Objective (${state.objective.name}): ${value}`;
  renderMetrics();
  renderTraps();
}

function setMap(mapData) {
  state.mapData = mapData;
  invalidateSolve();
  syncMapInputs(mapData);
  updateMeta();
  drawMap();
}

function createBlankMap() {
  const name = elements.mapName.value.trim() || "Untitled Map";
  const cellSize = Number(elements.cellSize.value || 1);
  const width = parseInt(elements.gridWidth.value, 10);
  const height = parseInt(elements.gridHeight.value, 10);
  if (!Number.isFinite(cellSize) || cellSize <= 0) {
    setStatus("Cell size must be > 0.");
    return;
  }
  if (!Number.isFinite(width) || !Number.isFinite(height)) {
    setStatus("Grid width and height must be numbers.");
    return;
  }
  if (width < 2 || height < 2) {
    setStatus("Grid width and height must be at least 2.");
    return;
  }
  if (width > 120 || height > 120) {
    setStatus("Grid size too large (max 120x120).");
    return;
  }
  const ascii = [];
  const row = ".".repeat(width);
  for (let r = 0; r < height; r += 1) {
    ascii.push(row);
  }
  setMap({
    name,
    cell_size_m: cellSize,
    ascii,
  });
  setStatus("Blank map created.");
}

function applyMeta() {
  if (!state.mapData) {
    setStatus("Load a map before editing metadata.");
    return;
  }
  const name = elements.mapName.value.trim() || "Untitled Map";
  const cellSize = Number(elements.cellSize.value || 1);
  if (!Number.isFinite(cellSize) || cellSize <= 0) {
    setStatus("Cell size must be > 0.");
    return;
  }
  state.mapData.name = name;
  state.mapData.cell_size_m = cellSize;
  updateMeta();
  setStatus("Metadata updated.");
}

function clearWeights() {
  if (!state.mapData) {
    return;
  }
  state.mapData.weights = null;
  invalidateSolve();
  updateMeta();
  drawMap();
  setStatus("Weights cleared.");
}

function exportMap() {
  if (!state.mapData) {
    setStatus("No map loaded to export.");
    return;
  }
  const filename = `${slugify(state.mapData.name)}.json`;
  downloadJson(filename, state.mapData);
  setStatus("Map JSON downloaded.");
}

function exportResults() {
  if (!state.mapData || !state.objective) {
    setStatus("Run the solver before exporting results.");
    return;
  }
  const filename = `${slugify(state.mapData.name)}_results.json`;
  const payload = {
    map: state.mapData,
    objective: state.objective,
    metrics: state.metrics,
    coverage_radius_m: state.coverageRadius,
    traps: state.traps,
    distance_map: state.distanceMap,
  };
  downloadJson(filename, payload);
  setStatus("Results JSON downloaded.");
}

function updateViewMode() {
  state.viewMode = elements.viewMode.value;
  drawMap();
}

function updateTool() {
  state.editor.tool = elements.paintTool.value;
}

function updateWeightValue() {
  state.editor.weightValue = Number(elements.weightValue.value || 0);
}

function eventToCell(event) {
  if (!state.mapData) {
    return null;
  }
  const rect = elements.canvas.getBoundingClientRect();
  const width = state.mapData.ascii[0]?.length || 0;
  const height = state.mapData.ascii.length;
  if (width === 0 || height === 0) {
    return null;
  }
  const scaleX = elements.canvas.width / rect.width;
  const scaleY = elements.canvas.height / rect.height;
  const x = (event.clientX - rect.left) * scaleX;
  const y = (event.clientY - rect.top) * scaleY;
  const col = Math.floor(x / (elements.canvas.width / width));
  const row = Math.floor(y / (elements.canvas.height / height));
  if (row < 0 || col < 0 || row >= height || col >= width) {
    return null;
  }
  return { row, col };
}

function handlePointerDown(event) {
  if (event.button !== 0) {
    return;
  }
  if (!state.mapData) {
    return;
  }
  state.editor.drawing = true;
  elements.canvas.setPointerCapture(event.pointerId);
  const cell = eventToCell(event);
  if (cell) {
    applyTool(cell.row, cell.col);
  }
}

function handlePointerMove(event) {
  if (!state.editor.drawing) {
    return;
  }
  const cell = eventToCell(event);
  if (cell) {
    applyTool(cell.row, cell.col);
  }
}

function handlePointerUp(event) {
  if (!state.editor.drawing) {
    return;
  }
  state.editor.drawing = false;
  elements.canvas.releasePointerCapture(event.pointerId);
}

async function loadSamples() {
  try {
    const response = await fetch("/api/samples");
    const data = await response.json();
    elements.sampleSelect.innerHTML = "";
    for (const sample of data.samples || []) {
      const option = document.createElement("option");
      option.value = sample.name;
      option.textContent = sample.title || sample.name;
      elements.sampleSelect.appendChild(option);
    }
  } catch (error) {
    setStatus("Failed to load samples.");
  }
}

async function loadSample() {
  const name = elements.sampleSelect.value;
  if (!name) {
    setStatus("No sample selected.");
    return;
  }
  setStatus("Loading sample...");
  try {
    const response = await fetch(`/api/sample?name=${encodeURIComponent(name)}`);
    const data = await response.json();
    if (data.error) {
      throw new Error(data.error);
    }
    setMap(data.map);
    setStatus("Sample loaded.");
  } catch (error) {
    setStatus(`Failed to load sample: ${error.message}`);
  }
}

function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) {
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const mapData = JSON.parse(reader.result);
      setMap(mapData);
      setStatus("Map loaded.");
    } catch (error) {
      setStatus("Invalid JSON file.");
    }
  };
  reader.readAsText(file);
}

async function runSolve() {
  if (!state.mapData) {
    setStatus("Load a map before running.");
    return;
  }
  setStatus("Running optimization...");
  const coverageValue = elements.coverageRadius.value.trim();
  const payload = {
    map: state.mapData,
    k: Number(elements.kInput.value || 1),
    candidate_rule: elements.candidateRule.value,
    min_wall_neighbors: Number(elements.minWallNeighbors.value || 0),
    local_improve: elements.localImprove.checked,
    objective: elements.objectiveSelect.value,
    coverage_radius_m: coverageValue === "" ? null : Number(coverageValue),
  };
  try {
    const response = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (data.error) {
      throw new Error(data.error);
    }
    state.distanceMap = data.distance_map;
    state.traps = data.traps || [];
    state.metrics = data.metrics || {};
    state.objective = data.objective;
    state.coverageRadius = data.coverage_radius_m;
    updateResults();
    drawMap();
    setStatus("Done.");
  } catch (error) {
    setStatus(`Solve failed: ${error.message}`);
  }
}

elements.loadSample.addEventListener("click", loadSample);
elements.mapFile.addEventListener("change", handleFileUpload);
elements.exportMap.addEventListener("click", exportMap);
elements.exportResults.addEventListener("click", exportResults);
elements.createMap.addEventListener("click", createBlankMap);
elements.applyMeta.addEventListener("click", applyMeta);
elements.clearWeights.addEventListener("click", clearWeights);
elements.paintTool.addEventListener("change", updateTool);
elements.weightValue.addEventListener("change", updateWeightValue);
elements.viewMode.addEventListener("change", updateViewMode);
elements.runSolve.addEventListener("click", runSolve);
elements.canvas.addEventListener("pointerdown", handlePointerDown);
elements.canvas.addEventListener("pointermove", handlePointerMove);
elements.canvas.addEventListener("pointerup", handlePointerUp);
elements.canvas.addEventListener("pointerleave", handlePointerUp);
elements.canvas.addEventListener("pointercancel", handlePointerUp);
window.addEventListener("resize", drawMap);

updateTool();
updateWeightValue();
loadSamples();
