const NS = "http://www.w3.org/2000/svg";
const FOV_HALF_DEG = 60;
const VIEW_STORAGE_KEY = "ld2450-radar-lab-view/1";
const defaultView = {rotation_deg: 0, offset_x_mm: 0, offset_y_mm: 0, range_mm: 2400, mirror_x: false};
const state = { data: null, timer: null, view: loadView(), drag: null };

const trackerFields = [
  ["gate_mm", "Association gate (mm)", 100, 2000, 10],
  ["max_coast_s", "Maximum coast (s)", 0.1, 5, 0.05],
  ["measurement_sigma_mm", "Measurement sigma (mm)", 10, 500, 5],
  ["acceleration_sigma_mm_s2", "Acceleration sigma (mm/s²)", 50, 3000, 25],
  ["initial_position_sigma_mm", "Initial position sigma (mm)", 10, 1000, 10],
  ["initial_velocity_sigma_mm_s", "Initial velocity sigma (mm/s)", 100, 4000, 50],
  ["min_confirmed_hits", "Minimum confirmed hits", 1, 12, 1],
];
const classifierFields = [
  ["endpoint_points", "Endpoint median points", 1, 10, 1],
  ["min_span_mm", "Minimum track span (mm)", 0, 2000, 25],
];

function svg(tag, attrs = {}) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

function loadView() {
  try {
    return {...defaultView, ...JSON.parse(localStorage.getItem(VIEW_STORAGE_KEY) || "{}")};
  } catch (_error) {
    return {...defaultView};
  }
}

function saveView() {
  localStorage.setItem(VIEW_STORAGE_KEY, JSON.stringify(state.view));
}

function viewPoint(x_mm, y_mm) {
  const x = state.view.mirror_x ? -x_mm : x_mm;
  const y = -y_mm;
  const angle = state.view.rotation_deg * Math.PI / 180;
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  return [
    x * cosine - y * sine + state.view.offset_x_mm,
    x * sine + y * cosine + state.view.offset_y_mm,
  ];
}

function pathFromPoints(points, close = false) {
  const transformed = points.map(([x, y]) => viewPoint(x, y));
  return transformed.map(([x, y], index) => `${index ? "L" : "M"}${x} ${y}`).join(" ") + (close ? " Z" : "");
}

function arcPoints(range, minAngle = -FOV_HALF_DEG, maxAngle = FOV_HALF_DEG, steps = 48) {
  return Array.from({length: steps + 1}, (_, index) => {
    const angle = (minAngle + (maxAngle - minAngle) * index / steps) * Math.PI / 180;
    return [Math.sin(angle) * range, Math.cos(angle) * range];
  });
}

function control(container, object, field, label, min, max, step) {
  const row = document.createElement("div");
  row.className = "control";
  const caption = document.createElement("label");
  caption.textContent = label;
  const input = document.createElement("input");
  input.type = "number";
  input.min = min;
  input.max = max;
  input.step = step;
  input.value = object[field];
  input.addEventListener("change", () => {
    object[field] = Number(input.value);
    scheduleUpdate();
  });
  row.append(caption, input);
  container.append(row);
}

function renderControls() {
  const config = state.data.config;
  const tracker = document.querySelector("#tracker-controls");
  const classifier = document.querySelector("#classifier-controls");
  const portals = document.querySelector("#portal-controls");
  tracker.replaceChildren();
  classifier.replaceChildren();
  portals.replaceChildren();
  trackerFields.forEach(args => control(tracker, config.tracker, ...args));
  classifierFields.forEach(args => control(classifier, config.classifier, ...args));

  config.portals.forEach(portal => {
    const section = document.createElement("section");
    section.className = "portal";
    const title = document.createElement("div");
    title.className = "portal-title";
    title.innerHTML = `<strong>${portal.name}</strong><small>${portal.shape}</small>`;
    section.append(title);
    const fields = portal.shape === "box"
      ? [["min_x_mm", "Min X"], ["max_x_mm", "Max X"], ["min_y_mm", "Min Y"], ["max_y_mm", "Max Y"]]
      : [["min_range_mm", "Min range"], ["max_range_mm", "Max range"], ["near_min_angle_deg", "Near min angle"], ["near_max_angle_deg", "Near max angle"], ["far_min_angle_deg", "Far min angle"], ["far_max_angle_deg", "Far max angle"]];
    fields.forEach(([field, label]) => control(section, portal, field, `${label} (${field.includes("angle") ? "deg" : "mm"})`, -10000, 10000, field.includes("angle") ? 1 : 25));
    portals.append(section);
  });
}

function sectorPoints(portal) {
  const sample = (range, minAngle, maxAngle) => {
    const points = [];
    for (let i = 0; i <= 18; i++) {
      const angle = (minAngle + (maxAngle - minAngle) * i / 18) * Math.PI / 180;
      points.push([Math.sin(angle) * range, Math.cos(angle) * range]);
    }
    return points;
  };
  const outer = sample(portal.max_range_mm, portal.far_min_angle_deg, portal.far_max_angle_deg);
  const inner = sample(portal.min_range_mm, portal.near_min_angle_deg, portal.near_max_angle_deg).reverse();
  return [...outer, ...inner];
}

function renderViewControls() {
  const rotation = document.querySelector("#view-rotation");
  const offsetX = document.querySelector("#view-offset-x");
  const offsetY = document.querySelector("#view-offset-y");
  const range = document.querySelector("#view-range");
  rotation.value = state.view.rotation_deg;
  offsetX.value = state.view.offset_x_mm;
  offsetY.value = state.view.offset_y_mm;
  range.value = state.view.range_mm;
  document.querySelector("#view-mirror").checked = state.view.mirror_x;
  document.querySelector("#view-rotation-value").textContent = `${state.view.rotation_deg}°`;
  document.querySelector("#view-offset-x-value").textContent = `${Math.round(state.view.offset_x_mm)} mm`;
  document.querySelector("#view-offset-y-value").textContent = `${Math.round(state.view.offset_y_mm)} mm`;
  document.querySelector("#view-range-value").textContent = `${(state.view.range_mm / 1000).toFixed(1)} m`;
  document.querySelectorAll("[data-view-rotation]").forEach(button => {
    button.classList.toggle("active", Number(button.dataset.viewRotation) === state.view.rotation_deg);
  });
}

function updateView(field, value) {
  state.view[field] = value;
  saveView();
  renderViewControls();
  renderRadar();
}

function renderRadar() {
  const root = document.querySelector("#radar");
  root.replaceChildren();
  const fovRange = state.view.range_mm;
  const extent = Math.max(2600, fovRange * 1.08);
  root.setAttribute("viewBox", `${-extent} ${-extent} ${extent * 2} ${extent * 2}`);
  const wedge = [[0, 0], ...arcPoints(fovRange), [0, 0]];
  root.append(svg("path", {d: pathFromPoints(wedge, true), class: "fov-wedge"}));
  const ringStep = fovRange <= 3000 ? 500 : fovRange <= 7000 ? 1000 : 2000;
  for (let radius = ringStep; radius < fovRange; radius += ringStep) {
    root.append(svg("path", {d: pathFromPoints(arcPoints(radius)), class: "grid"}));
  }
  for (const angle of [-FOV_HALF_DEG, FOV_HALF_DEG]) {
    root.append(svg("path", {d: pathFromPoints([[0, 0], ...arcPoints(fovRange, angle, angle, 1)]), class: "fov-edge"}));
  }
  root.append(svg("path", {d: pathFromPoints([[0, -100], [0, fovRange]]), class: "boresight"}));
  const sensor = viewPoint(0, 0);
  root.append(svg("circle", {cx: sensor[0], cy: sensor[1], r: 70, class: "sensor"}));
  const fovLabelPoint = viewPoint(0, fovRange + ringStep * 0.28);
  const fovLabel = svg("text", {x: fovLabelPoint[0], y: fovLabelPoint[1], class: "svg-label", "text-anchor": "middle"});
  fovLabel.textContent = "120° FOV";
  root.append(fovLabel);

  for (const portal of state.data.config.portals) {
    let shape;
    if (portal.shape === "box") {
      const corners = [[portal.min_x_mm, portal.min_y_mm], [portal.max_x_mm, portal.min_y_mm], [portal.max_x_mm, portal.max_y_mm], [portal.min_x_mm, portal.max_y_mm]];
      shape = svg("path", {d: pathFromPoints(corners, true), class: "portal-shape"});
    } else {
      shape = svg("path", {d: pathFromPoints(sectorPoints(portal), true), class: "portal-shape"});
    }
    root.append(shape);
    let labelX = (portal.min_x_mm + portal.max_x_mm) / 2;
    let labelY = portal.max_y_mm + 120;
    if (portal.shape === "sector") {
      const angle = (portal.far_min_angle_deg + portal.far_max_angle_deg) * Math.PI / 360;
      const range = portal.max_range_mm + 100;
      labelX = Math.sin(angle) * range;
      labelY = Math.cos(angle) * range;
    }
    [labelX, labelY] = viewPoint(labelX, labelY);
    const label = svg("text", {x: labelX, y: labelY, class: "svg-label", "text-anchor": "middle"});
    label.textContent = portal.name;
    root.append(label);
  }

  const showRaw = document.querySelector("#show-raw").checked;
  const showFiltered = document.querySelector("#show-filtered").checked;
  state.data.tracks.forEach((track, index) => {
    if (showRaw) {
      track.points.forEach(point => {
        const position = viewPoint(point.observed_x_mm, point.observed_y_mm);
        root.append(svg("circle", {cx: position[0], cy: position[1], r: 34, class: "raw-point"}));
      });
    }
    if (showFiltered) {
      const points = track.points.map(point => viewPoint(point.filtered_x_mm, point.filtered_y_mm).join(",")).join(" ");
      root.append(svg("polyline", {points, class: `track-line track-${index % 3}`}));
    }
    const first = track.points[0];
    const last = track.points[track.points.length - 1];
    const start = viewPoint(first.filtered_x_mm, first.filtered_y_mm);
    const end = viewPoint(last.filtered_x_mm, last.filtered_y_mm);
    root.append(svg("circle", {cx: start[0], cy: start[1], r: 62, class: "endpoint-start"}));
    root.append(svg("circle", {cx: end[0], cy: end[1], r: 62, class: "endpoint-end"}));
  });
}

function renderResults() {
  const results = document.querySelector("#results");
  results.replaceChildren();
  state.data.labels.forEach(item => {
    const row = document.createElement("div");
    row.className = `result ${item.confidence}`;
    row.innerHTML = `<strong>Track ${item.track_id}: ${item.label}</strong><small>${item.confidence} / ${item.reason} / ${Math.round(item.span_mm)} mm / ${item.point_count} points</small>`;
    results.append(row);
  });
  document.querySelector("#contract").textContent = JSON.stringify({
    schema: "ld2450-radar-event/1",
    fields: ["observed_at", "track_id", "origin", "destination", "label", "confidence", "reason", "span_mm", "point_count"]
  }, null, 2);
  document.querySelector("#stats").innerHTML = [
    [state.data.summary.frame_count, "input frames"],
    [state.data.summary.track_count, "confirmed tracks"],
    [state.data.summary.classified_count, "O-D classified"],
  ].map(([value, label]) => `<div class="stat"><strong>${value}</strong><span>${label}</span></div>`).join("");
  document.querySelector("#source-name").textContent = state.data.summary.source_name;
  document.querySelector("#source-meta").textContent = `${state.data.summary.frame_count} frames / ${state.data.summary.epoch_count} epoch${state.data.summary.epoch_count === 1 ? "" : "s"}`;
}

function render() {
  renderControls();
  renderViewControls();
  renderRadar();
  renderResults();
  setStatus("Ready");
}

function setStatus(text, error = false) {
  const element = document.querySelector("#status");
  element.textContent = text;
  element.classList.toggle("error", error);
}

function scheduleUpdate() {
  clearTimeout(state.timer);
  setStatus("Evaluating");
  state.timer = setTimeout(updateConfig, 180);
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
  return value;
}

async function updateConfig() {
  try {
    state.data = await request("/api/config", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(state.data.config)});
    render();
  } catch (error) {
    setStatus(error.message, true);
  }
}

document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(item => item.classList.toggle("active", item === tab));
  document.querySelectorAll(".panel").forEach(panel => panel.classList.toggle("active", panel.id === `${tab.dataset.tab}-panel`));
}));
document.querySelector("#show-raw").addEventListener("change", renderRadar);
document.querySelector("#show-filtered").addEventListener("change", renderRadar);
document.querySelector("#load-frames").addEventListener("click", () => document.querySelector("#frame-file").click());
document.querySelector("#load-example").addEventListener("click", async () => {
  try {
    setStatus("Loading example");
    const response = await fetch("/synthetic-atomic-frames.csv");
    const content = await response.text();
    state.data = await request("/api/frames", {method: "POST", headers: {"Content-Type": "text/csv", "X-File-Name": "synthetic-atomic-frames.csv"}, body: content});
    render();
  } catch (error) {
    setStatus(error.message, true);
  }
});
document.querySelector("#frame-file").addEventListener("change", async event => {
  const file = event.target.files[0];
  if (!file) return;
  if (file.size > 25 * 1024 * 1024) {
    setStatus("CSV exceeds the 25 MB limit", true);
    event.target.value = "";
    return;
  }
  try {
    setStatus("Parsing CSV");
    state.data = await request("/api/frames", {method: "POST", headers: {"Content-Type": "text/csv", "X-File-Name": encodeURIComponent(file.name)}, body: file});
    render();
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    event.target.value = "";
  }
});
document.querySelector("#use-demo").addEventListener("click", async () => { state.data = await request("/api/demo", {method: "POST", body: "demo"}); render(); });
document.querySelectorAll("[data-view-rotation]").forEach(button => button.addEventListener("click", () => updateView("rotation_deg", Number(button.dataset.viewRotation))));
document.querySelector("#view-rotation").addEventListener("input", event => updateView("rotation_deg", Number(event.target.value)));
document.querySelector("#view-offset-x").addEventListener("input", event => updateView("offset_x_mm", Number(event.target.value)));
document.querySelector("#view-offset-y").addEventListener("input", event => updateView("offset_y_mm", Number(event.target.value)));
document.querySelector("#view-range").addEventListener("input", event => updateView("range_mm", Number(event.target.value)));
document.querySelector("#view-mirror").addEventListener("change", event => updateView("mirror_x", event.target.checked));
document.querySelector("#view-reset").addEventListener("click", () => { state.view = {...defaultView}; saveView(); renderViewControls(); renderRadar(); });
document.querySelector("#fit-data").addEventListener("click", () => {
  const radii = state.data.tracks.flatMap(track => track.points.map(point => Math.hypot(point.observed_x_mm, point.observed_y_mm)));
  const portalRadii = state.data.config.portals.map(portal => portal.shape === "sector" ? portal.max_range_mm : Math.max(
    Math.hypot(portal.min_x_mm, portal.min_y_mm),
    Math.hypot(portal.min_x_mm, portal.max_y_mm),
    Math.hypot(portal.max_x_mm, portal.min_y_mm),
    Math.hypot(portal.max_x_mm, portal.max_y_mm),
  ));
  const needed = Math.max(...radii, ...portalRadii, 1000) * 1.12;
  state.view.range_mm = Math.min(10000, Math.max(1000, Math.ceil(needed / 100) * 100));
  saveView();
  renderViewControls();
  renderRadar();
});
const radar = document.querySelector("#radar");
radar.addEventListener("pointerdown", event => {
  radar.setPointerCapture(event.pointerId);
  radar.classList.add("dragging");
  state.drag = {x: event.clientX, y: event.clientY, offsetX: state.view.offset_x_mm, offsetY: state.view.offset_y_mm};
});
radar.addEventListener("pointermove", event => {
  if (!state.drag) return;
  const rect = radar.getBoundingClientRect();
  const viewBox = radar.viewBox.baseVal;
  state.view.offset_x_mm = Math.round((state.drag.offsetX + (event.clientX - state.drag.x) * viewBox.width / rect.width) / 25) * 25;
  state.view.offset_y_mm = Math.round((state.drag.offsetY + (event.clientY - state.drag.y) * viewBox.height / rect.height) / 25) * 25;
  saveView();
  renderViewControls();
  renderRadar();
});
radar.addEventListener("pointerup", event => {
  if (radar.hasPointerCapture(event.pointerId)) radar.releasePointerCapture(event.pointerId);
  radar.classList.remove("dragging");
  state.drag = null;
});
document.querySelector("#reset").addEventListener("click", async () => { state.data = await request("/api/reset", {method: "POST"}); render(); });
document.querySelector("#download").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(state.data.config, null, 2) + "\n"], {type: "application/json"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "ld2450-radar-config.json";
  link.click();
  URL.revokeObjectURL(link.href);
});

request("/api/state").then(value => { state.data = value; render(); }).catch(error => setStatus(error.message, true));