(function () {
  "use strict";

  const state = {
    serverOnline: false,
    precomputed: null,
    mission: null,
    scenarioId: "semeru",
    activeTool: "inspect",
    customCamps: null,
    customObstacles: null,
    focusedDroneId: null,
    playing: false,
    progress: 0.0,
    speed: 1.0,
    lastFrameTime: 0,
    hoverCell: null,
  };

  const els = {
    badge: document.getElementById("engineModeBadge"),
    themeBtn: document.getElementById("themeToggleBtn"),
    scenarioSelect: document.getElementById("scenarioSelect"),
    scenarioDesc: document.getElementById("scenarioDesc"),
    kpiDistance: document.getElementById("kpiDistance"),
    kpiMakespan: document.getElementById("kpiMakespan"),
    kpiOnTime: document.getElementById("kpiOnTime"),
    pathAlgoSelect: document.getElementById("pathAlgoSelect"),
    routingAlgoSelect: document.getElementById("routingAlgoSelect"),
    numDronesRange: document.getElementById("numDronesRange"),
    popSizeRange: document.getElementById("popSizeRange"),
    generationsRange: document.getElementById("generationsRange"),
    batteryRange: document.getElementById("batteryRange"),
    payloadRange: document.getElementById("payloadRange"),
    numDronesVal: document.getElementById("numDronesVal"),
    popSizeVal: document.getElementById("popSizeVal"),
    generationsVal: document.getElementById("generationsVal"),
    batteryVal: document.getElementById("batteryVal"),
    payloadVal: document.getElementById("payloadVal"),
    showExploredChk: document.getElementById("showExploredChk"),
    solveBtn: document.getElementById("solveBtn"),
    resetScenarioBtn: document.getElementById("resetScenarioBtn"),
    clearCampsBtn: document.getElementById("clearCampsBtn"),
    emptyReloadBtn: document.getElementById("emptyReloadBtn"),
    errorResetBtn: document.getElementById("errorResetBtn"),
    loadingBanner: document.getElementById("loadingBanner"),
    errorBanner: document.getElementById("errorBanner"),
    errorMessage: document.getElementById("errorMessage"),
    emptyOverlay: document.getElementById("emptyOverlay"),
    mapCanvas: document.getElementById("mapCanvas"),
    mapTooltip: document.getElementById("mapTooltip"),
    playPauseBtn: document.getElementById("playPauseBtn"),
    replayBtn: document.getElementById("replayBtn"),
    timeScrubber: document.getElementById("timeScrubber"),
    clockReadout: document.getElementById("clockReadout"),
    benchChartCanvas: document.getElementById("benchChartCanvas"),
    benchSummaryTable: document.getElementById("benchSummaryTable"),
    convChartCanvas: document.getElementById("convChartCanvas"),
    convSummaryNote: document.getElementById("convSummaryNote"),
    manifestBody: document.getElementById("manifestBody"),
    clearFocusDroneBtn: document.getElementById("clearFocusDroneBtn"),
    openVideoModalBtn: document.getElementById("openVideoModalBtn"),
    closeVideoModalBtn: document.getElementById("closeVideoModalBtn"),
    videoModal: document.getElementById("videoModal"),
    modalDemoVideo: document.getElementById("modalDemoVideo"),
  };

  function getThemeColors() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    return {
      isDark,
      bg: isDark ? "#0D151E" : "#F6F5F0",
      panel: isDark ? "#14202D" : "#FFFFFF",
      gridLine: isDark ? "rgba(159, 176, 194, 0.14)" : "rgba(20, 32, 43, 0.10)",
      ink: isDark ? "#EDF2F7" : "#14202B",
      muted: isDark ? "#9FB0C2" : "#425262",
      accent: isDark ? "#F26A36" : "#C84318",
      ok: isDark ? "#34D399" : "#0F7B58",
      warn: isDark ? "#F59E0B" : "#B86B00",
      crit: isDark ? "#F87171" : "#B4232E",
      hazardFill: isDark ? "rgba(185, 28, 28, 0.55)" : "rgba(220, 38, 38, 0.24)",
      hazardStroke: isDark ? "#F87171" : "#B91C1C",
      explored: isDark ? "rgba(88, 153, 255, 0.22)" : "rgba(29, 91, 214, 0.16)",
      uavs: isDark
        ? ["#5899FF", "#F59E0B", "#2DD4BF", "#FB7185"]
        : ["#1D5BD6", "#B86B00", "#0F7B58", "#B4234E"],
    };
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("aerorelief_theme", theme);
    els.themeBtn.textContent = theme === "dark" ? "Mode Terang" : "Mode Malam";
    renderAll();
  }

  function syncSliderLabels() {
    els.numDronesVal.textContent = `${els.numDronesRange.value} UAV`;
    els.popSizeVal.textContent = els.popSizeRange.value;
    els.generationsVal.textContent = els.generationsRange.value;
    els.batteryVal.textContent = `${els.batteryRange.value} km`;
    els.payloadVal.textContent = `${Number(els.payloadRange.value).toFixed(1)} kg`;
  }

  async function checkBackend() {
    try {
      const resp = await fetch("/api/health");
      if (resp.ok) {
        state.serverOnline = true;
        els.badge.textContent = "Server Python Aktif";
        return;
      }
    } catch (_) {
      // Fallback to precomputed mode
    }
    state.serverOnline = false;
    els.badge.textContent = "Mode Pratinjau Statis";
  }

  async function loadPrecomputed() {
    if (state.precomputed) return state.precomputed;
    try {
      const resp = await fetch("/static/precomputed.json");
      if (resp.ok) {
        state.precomputed = await resp.json();
      }
    } catch (_) {
      state.precomputed = null;
    }
    return state.precomputed;
  }

  async function runSolver(overridePayload) {
    els.loadingBanner.classList.remove("hidden");
    els.errorBanner.classList.add("hidden");

    const payload = overridePayload || {
      scenario_id: state.scenarioId,
      path_algorithm: els.pathAlgoSelect.value,
      routing_algorithm: els.routingAlgoSelect.value,
      num_drones: Number(els.numDronesRange.value),
      pop_size: Number(els.popSizeRange.value),
      generations: Number(els.generationsRange.value),
      max_battery_km: Number(els.batteryRange.value),
      max_payload_kg: Number(els.payloadRange.value),
      custom_camps: state.customCamps,
      custom_obstacles: state.customObstacles,
    };

    try {
      if (state.serverOnline) {
        const resp = await fetch("/api/solve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await resp.json();
        applyMissionData(data);
      } else {
        const bundle = await loadPrecomputed();
        if (bundle && bundle[state.scenarioId]) {
          applyMissionData(bundle[state.scenarioId]);
        }
      }
    } catch (err) {
      els.errorBanner.classList.remove("hidden");
      els.errorMessage.textContent = "Gagal terhubung ke mesin Python: " + String(err);
    } finally {
      els.loadingBanner.classList.add("hidden");
    }
  }

  function applyMissionData(data) {
    state.mission = data;
    state.focusedDroneId = null;
    els.clearFocusDroneBtn.classList.add("hidden");
    if (data.scenario && data.scenario.description) {
      els.scenarioDesc.textContent = data.scenario.description;
    }

    if (data.empty) {
      els.emptyOverlay.classList.remove("hidden");
      els.kpiDistance.textContent = "0.0 km";
      els.kpiMakespan.textContent = "0.0 mnt";
      els.kpiOnTime.textContent = "0%";
      state.playing = false;
      els.playPauseBtn.textContent = "Putar";
      renderAll();
      return;
    }

    els.emptyOverlay.classList.add("hidden");
    if (!data.reachable) {
      els.errorBanner.classList.remove("hidden");
      els.errorMessage.textContent = data.message || "Posko tidak terjangkau oleh armada drone.";
      state.playing = false;
      els.playPauseBtn.textContent = "Putar";
      renderAll();
      return;
    }

    els.errorBanner.classList.add("hidden");
    const evalData = data.routing.active.evaluation;
    els.kpiDistance.textContent = `${evalData.total_distance_km.toFixed(1)} km`;
    els.kpiMakespan.textContent = `${evalData.makespan_min.toFixed(1)} mnt`;
    els.kpiOnTime.textContent = `${evalData.on_time_pct.toFixed(0)}%`;

    state.progress = 0.0;
    state.playing = true;
    state.lastFrameTime = performance.now();
    els.playPauseBtn.textContent = "Jeda";
    renderAll();
  }

  function getMapGeometry() {
    const canvas = els.mapCanvas;
    const m = state.mission;
    const gw = m ? m.scenario.grid_width : 36;
    const gh = m ? m.scenario.grid_height : 26;
    const pad = { l: 42, r: 18, t: 18, b: 32 };
    const cw = (canvas.width - pad.l - pad.r) / gw;
    const ch = (canvas.height - pad.t - pad.b) / gh;
    return {
      gw, gh, pad, cw, ch,
      toPx(gx, gy) {
        return [pad.l + (gx + 0.5) * cw, canvas.height - pad.b - (gy + 0.5) * ch];
      },
      toGrid(px, py) {
        const gx = Math.floor((px - pad.l) / cw);
        const gy = Math.floor((canvas.height - pad.b - py) / ch);
        if (gx < 0 || gx >= gw || gy < 0 || gy >= gh) return null;
        return [gx, gy];
      },
    };
  }

  function renderMap() {
    const canvas = els.mapCanvas;
    const ctx = canvas.getContext("2d");
    const colors = getThemeColors();
    const m = state.mission;

    ctx.fillStyle = colors.panel;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (!m) return;
    const g = getMapGeometry();

    // Elevation heatmap
    const elev = m.elevation || [];
    let maxElev = 1;
    for (let y = 0; y < elev.length; y++) {
      for (let x = 0; x < elev[y].length; x++) {
        if (elev[y][x] > maxElev) maxElev = elev[y][x];
      }
    }

    for (let gy = 0; gy < g.gh; gy++) {
      for (let gx = 0; gx < g.gw; gx++) {
        const v = elev[gy] ? elev[gy][gx] / maxElev : 0;
        const px = g.pad.l + gx * g.cw;
        const py = canvas.height - g.pad.b - (gy + 1) * g.ch;
        if (colors.isDark) {
          ctx.fillStyle = `rgb(${Math.round(16 + v * 22)}, ${Math.round(28 + v * 46)}, ${Math.round(40 + v * 32)})`;
        } else {
          ctx.fillStyle = `rgb(${Math.round(244 - v * 34)}, ${Math.round(243 - v * 16)}, ${Math.round(236 - v * 28)})`;
        }
        ctx.fillRect(px, py, g.cw + 0.6, g.ch + 0.6);
      }
    }

    // Explored nodes overlay
    if (m.reachable && !m.empty && els.showExploredChk.checked && m.pathfinding && m.pathfinding.explored_union) {
      ctx.fillStyle = colors.explored;
      for (const [nx, ny] of m.pathfinding.explored_union) {
        const px = g.pad.l + nx * g.cw + 2;
        const py = canvas.height - g.pad.b - (ny + 1) * g.ch + 2;
        ctx.fillRect(px, py, Math.max(2, g.cw - 4), Math.max(2, g.ch - 4));
      }
    }

    // Grid lines
    ctx.strokeStyle = colors.gridLine;
    ctx.lineWidth = 1;
    for (let gx = 0; gx <= g.gw; gx++) {
      const x = g.pad.l + gx * g.cw;
      ctx.beginPath();
      ctx.moveTo(x, g.pad.t);
      ctx.lineTo(x, canvas.height - g.pad.b);
      ctx.stroke();
    }
    for (let gy = 0; gy <= g.gh; gy++) {
      const y = canvas.height - g.pad.b - gy * g.ch;
      ctx.beginPath();
      ctx.moveTo(g.pad.l, y);
      ctx.lineTo(canvas.width - g.pad.r, y);
      ctx.stroke();
    }

    // Axis ticks
    ctx.fillStyle = colors.muted;
    ctx.font = "600 11px 'IBM Plex Mono', monospace";
    ctx.textAlign = "center";
    for (let gx = 0; gx <= g.gw; gx += 5) {
      ctx.fillText(String(gx), g.pad.l + gx * g.cw, canvas.height - 12);
    }
    ctx.textAlign = "right";
    for (let gy = 0; gy <= g.gh; gy += 5) {
      ctx.fillText(String(gy), g.pad.l - 8, canvas.height - g.pad.b - gy * g.ch + 4);
    }

    // Obstacles
    for (const [ox, oy] of m.obstacles || []) {
      const px = g.pad.l + ox * g.cw;
      const py = canvas.height - g.pad.b - (oy + 1) * g.ch;
      ctx.fillStyle = colors.hazardFill;
      ctx.fillRect(px, py, g.cw, g.ch);
      ctx.strokeStyle = colors.hazardStroke;
      ctx.lineWidth = 1;
      ctx.strokeRect(px + 0.5, py + 0.5, g.cw - 1, g.ch - 1);
    }

    // Hover highlight
    if (state.hoverCell) {
      const [hx, hy] = state.hoverCell;
      const px = g.pad.l + hx * g.cw;
      const py = canvas.height - g.pad.b - (hy + 1) * g.ch;
      ctx.strokeStyle = colors.accent;
      ctx.lineWidth = 2;
      ctx.strokeRect(px, py, g.cw, g.ch);
    }

    // Routes
    const campArrivals = {};
    let makespan = 0;
    let schedules = [];
    if (m.reachable && !m.empty && m.routing) {
      const evalData = m.routing.active.evaluation;
      schedules = evalData.drone_schedules;
      makespan = evalData.makespan_min;
      for (const ds of schedules) {
        for (const d of ds.deliveries) {
          campArrivals[d.camp_id] = d.arrival_min;
        }
      }
      schedules.forEach((ds, idx) => {
        if (state.focusedDroneId !== null && state.focusedDroneId !== ds.drone_id) return;
        const col = colors.uavs[idx % colors.uavs.length];
        for (const seg of ds.segments) {
          if (!seg.path || seg.path.length < 2) continue;
          ctx.beginPath();
          ctx.strokeStyle = col;
          ctx.lineWidth = seg.is_reload_trip ? 2 : 3.2;
          ctx.setLineDash(seg.is_reload_trip ? [6, 5] : []);
          seg.path.forEach((pt, i) => {
            const [px, py] = g.toPx(pt[0], pt[1]);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          });
          ctx.stroke();
          ctx.setLineDash([]);
        }
      });
    }

    const simTime = state.progress * makespan;
    els.clockReadout.textContent = `${simTime.toFixed(1).padStart(4, "0")} / ${makespan.toFixed(1).padStart(4, "0")} mnt`;
    els.timeScrubber.value = (state.progress * 100).toFixed(1);

    // Depot
    const [dx, dy] = g.toPx(m.depot[0], m.depot[1]);
    ctx.fillStyle = colors.accent;
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = 2.5;
    ctx.fillRect(dx - 11, dy - 11, 22, 22);
    ctx.strokeRect(dx - 11, dy - 11, 22, 22);
    ctx.fillStyle = colors.ink;
    ctx.textAlign = "left";
    ctx.font = "700 12px 'Plus Jakarta Sans', sans-serif";
    ctx.fillText("DEPOT", dx + 15, dy + 4);

    // Camps
    for (const c of m.camps || []) {
      const [cx, cy] = g.toPx(c.x, c.y);
      const delivered = m.reachable && makespan > 0 && simTime >= (campArrivals[c.id] || 9999);
      let fill = c.urgency === "KRITIS" ? colors.crit : (c.urgency === "TINGGI" ? colors.warn : "#3B82F6");
      if (delivered) fill = colors.ok;

      ctx.beginPath();
      ctx.arc(cx, cy, 8.5, 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#FFFFFF";
      ctx.stroke();

      ctx.fillStyle = colors.ink;
      ctx.font = "600 11px 'Plus Jakarta Sans', sans-serif";
      const tag = delivered ? `P${c.id} [OK]` : `P${c.id}`;
      ctx.fillText(tag, cx + 11, cy + 4);
    }

    // Animated UAVs
    if (m.reachable && !m.empty && schedules.length > 0) {
      schedules.forEach((ds, idx) => {
        if (state.focusedDroneId !== null && state.focusedDroneId !== ds.drone_id) return;
        const col = colors.uavs[idx % colors.uavs.length];
        let pos = m.depot;
        let heading = 0;

        for (const seg of ds.segments) {
          if (simTime >= seg.start_min && simTime <= seg.end_min && seg.path && seg.path.length >= 2) {
            const span = Math.max(seg.end_min - seg.start_min, 1e-6);
            const frac = (simTime - seg.start_min) / span;
            const fi = frac * (seg.path.length - 1);
            const i0 = Math.floor(fi);
            const i1 = Math.min(i0 + 1, seg.path.length - 1);
            const alpha = fi - i0;
            pos = [
              seg.path[i0][0] * (1 - alpha) + seg.path[i1][0] * alpha,
              seg.path[i0][1] * (1 - alpha) + seg.path[i1][1] * alpha,
            ];
            heading = Math.atan2(-(seg.path[i1][1] - seg.path[i0][1]), seg.path[i1][0] - seg.path[i0][0]);
            break;
          }
        }

        const [ux, uy] = g.toPx(pos[0], pos[1]);
        ctx.save();
        ctx.translate(ux, uy);
        ctx.rotate(heading);
        ctx.beginPath();
        ctx.moveTo(13, 0);
        ctx.lineTo(-9, -8);
        ctx.lineTo(-5, 0);
        ctx.lineTo(-9, 8);
        ctx.closePath();
        ctx.fillStyle = col;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#FFFFFF";
        ctx.stroke();
        ctx.restore();

        ctx.fillStyle = colors.ink;
        ctx.font = "700 11px 'IBM Plex Mono', monospace";
        ctx.fillText(ds.callsign.split(" ")[0], ux + 14, uy - 8);
      });
    }
  }

  function renderChartsAndManifest() {
    const m = state.mission;
    const colors = getThemeColors();

    // Benchmark Chart
    const bCanvas = els.benchChartCanvas;
    const bCtx = bCanvas.getContext("2d");
    bCtx.fillStyle = colors.panel;
    bCtx.fillRect(0, 0, bCanvas.width, bCanvas.height);

    // Convergence Chart
    const cCanvas = els.convChartCanvas;
    const cCtx = cCanvas.getContext("2d");
    cCtx.fillStyle = colors.panel;
    cCtx.fillRect(0, 0, cCanvas.width, cCanvas.height);

    if (!m || !m.reachable || m.empty) {
      els.benchSummaryTable.innerHTML = "";
      els.convSummaryNote.textContent = "Data analitik tampil setelah optimasi selesai.";
      els.manifestBody.innerHTML = "";
      return;
    }

    // 1. Benchmark Bar Chart
    const bench = m.pathfinding.benchmark || [];
    const maxExp = Math.max(...bench.map((b) => b.total_explored_nodes), 1);
    const pad = { l: 55, r: 24, t: 28, b: 44 };
    const cw = bCanvas.width - pad.l - pad.r;
    const ch = bCanvas.height - pad.t - pad.b;

    bCtx.strokeStyle = colors.gridLine;
    bCtx.beginPath();
    bCtx.moveTo(pad.l, pad.t);
    bCtx.lineTo(pad.l, pad.t + ch);
    bCtx.lineTo(pad.l + cw, pad.t + ch);
    bCtx.stroke();

    const barColors = [colors.uavs[0], colors.muted, colors.accent];
    const barW = Math.min(82, cw / Math.max(1, bench.length * 2));
    bench.forEach((row, i) => {
      const cx = pad.l + ((i + 0.5) / bench.length) * cw;
      const bh = (row.total_explored_nodes / maxExp) * (ch - 20);
      const x = cx - barW / 2;
      const y = pad.t + ch - bh;
      bCtx.fillStyle = barColors[i % barColors.length];
      bCtx.fillRect(x, y, barW, bh);

      bCtx.fillStyle = colors.ink;
      bCtx.font = "700 12px 'IBM Plex Mono', monospace";
      bCtx.textAlign = "center";
      bCtx.fillText(`${row.total_explored_nodes}`, cx, y - 6);

      bCtx.fillStyle = colors.muted;
      bCtx.font = "600 11px 'Plus Jakarta Sans', sans-serif";
      const shortName = row.algorithm === "astar" ? "A* Search" : (row.algorithm === "ucs" ? "UCS (Dijkstra)" : "Greedy BFS");
      bCtx.fillText(shortName, cx, pad.t + ch + 20);
    });

    els.benchSummaryTable.innerHTML = `
      <table class="mini-table">
        <thead><tr><th>Algoritma</th><th>Simpul Dieksplorasi</th><th>Waktu</th><th>Selisih Optimal</th></tr></thead>
        <tbody>
          ${bench.map((r) => `
            <tr>
              <td><strong>${r.label}</strong></td>
              <td class="mono">${r.total_explored_nodes.toLocaleString("id-ID")}</td>
              <td class="mono">${r.total_runtime_ms.toFixed(2)} ms</td>
              <td class="mono">${r.optimality_gap_pct.toFixed(2)}%</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;

    // 2. Convergence Chart (GA vs SA)
    const gaHist = m.routing.ga_summary.history || [];
    const saHist = m.routing.sa_summary.history || [];
    if (gaHist.length >= 2) {
      const vals = gaHist.map((h) => h.best_objective).concat(saHist.map((h) => h.best_objective));
      const vmin = Math.min(...vals) * 0.96;
      const vmax = Math.max(...vals) * 1.03;

      cCtx.strokeStyle = colors.gridLine;
      cCtx.beginPath();
      cCtx.moveTo(pad.l, pad.t);
      cCtx.lineTo(pad.l, pad.t + ch);
      cCtx.lineTo(pad.l + cw, pad.t + ch);
      cCtx.stroke();

      const drawCurve = (hist, strokeCol, dashed) => {
        cCtx.beginPath();
        cCtx.strokeStyle = strokeCol;
        cCtx.lineWidth = 2.6;
        cCtx.setLineDash(dashed ? [6, 4] : []);
        hist.forEach((h, i) => {
          const x = pad.l + (i / Math.max(1, hist.length - 1)) * cw;
          const y = pad.t + ch - ((h.best_objective - vmin) / Math.max(1e-5, vmax - vmin)) * (ch - 12);
          if (i === 0) cCtx.moveTo(x, y);
          else cCtx.lineTo(x, y);
        });
        cCtx.stroke();
        cCtx.setLineDash([]);
      };

      drawCurve(saHist, colors.accent, true);
      drawCurve(gaHist, colors.uavs[0], false);

      cCtx.fillStyle = colors.ink;
      cCtx.font = "600 11px 'IBM Plex Mono', monospace";
      cCtx.textAlign = "left";
      cCtx.fillText(`Biru Solid: GA (${m.routing.ga_summary.objective.toFixed(1)})  |  Oranye Putus: SA (${m.routing.sa_summary.objective.toFixed(1)})`, pad.l + 8, pad.t + 10);
      cCtx.fillText(`Generasi 1`, pad.l, pad.t + ch + 20);
      cCtx.textAlign = "right";
      cCtx.fillText(`Generasi ${gaHist.length}`, pad.l + cw, pad.t + ch + 20);
    }

    els.convSummaryNote.textContent =
      `Genetic Algorithm mencapai objektif ${m.routing.ga_summary.objective.toFixed(1)} (${m.routing.ga_summary.runtime_ms} ms) vs Simulated Annealing ${m.routing.sa_summary.objective.toFixed(1)} (${m.routing.sa_summary.runtime_ms} ms).`;

    // 3. Manifest Table
    const schedules = m.routing.active.evaluation.drone_schedules || [];
    els.manifestBody.innerHTML = schedules
      .map((ds, idx) => {
        const col = colors.uavs[idx % colors.uavs.length];
        const selectedCls = state.focusedDroneId === ds.drone_id ? "selected-row" : "";
        return `
          <tr class="${selectedCls}" data-drone-id="${ds.drone_id}" tabindex="0">
            <td><span class="drone-dot" style="background:${col}"></span><strong>${ds.callsign}</strong></td>
            <td>${ds.route_labels.join(" -> ")}</td>
            <td class="mono">${ds.total_payload_kg.toFixed(1)} kg</td>
            <td class="mono">${ds.total_distance_km.toFixed(1)} km (${ds.reloads}x reload)</td>
            <td class="mono">${ds.total_time_min.toFixed(1)} mnt</td>
            <td><span class="badge-status">${ds.status}</span></td>
          </tr>
        `;
      })
      .join("");

    els.manifestBody.querySelectorAll("tr").forEach((tr) => {
      const toggleFocus = () => {
        const did = Number(tr.getAttribute("data-drone-id"));
        state.focusedDroneId = state.focusedDroneId === did ? null : did;
        els.clearFocusDroneBtn.classList.toggle("hidden", state.focusedDroneId === null);
        renderChartsAndManifest();
        renderMap();
      };
      tr.addEventListener("click", toggleFocus);
      tr.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggleFocus();
        }
      });
    });
  }

  function renderAll() {
    renderMap();
    renderChartsAndManifest();
  }

  function animationLoop(now) {
    if (state.playing && state.mission && state.mission.reachable && !state.mission.empty) {
      const dt = (now - state.lastFrameTime) / 1000.0;
      const makespan = Math.max(state.mission.routing.active.evaluation.makespan_min, 1.0);
      // 1x plays 10 mission minutes per 1 real second
      state.progress += (dt * 10.0 * state.speed) / makespan;
      if (state.progress >= 1.0) {
        state.progress = 1.0;
        state.playing = false;
        els.playPauseBtn.textContent = "Putar";
      }
      renderMap();
    }
    state.lastFrameTime = now;
    requestAnimationFrame(animationLoop);
  }

  function initEvents() {
    els.themeBtn.addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme");
      applyTheme(cur === "dark" ? "light" : "dark");
    });

    [
      els.numDronesRange,
      els.popSizeRange,
      els.generationsRange,
      els.batteryRange,
      els.payloadRange,
    ].forEach((input) => input.addEventListener("input", syncSliderLabels));

    els.scenarioSelect.addEventListener("change", () => {
      state.scenarioId = els.scenarioSelect.value;
      state.customCamps = null;
      state.customObstacles = null;
      runSolver();
    });

    els.solveBtn.addEventListener("click", () => runSolver());
    els.showExploredChk.addEventListener("change", () => renderMap());

    const resetAction = () => {
      state.customCamps = null;
      state.customObstacles = null;
      runSolver();
    };
    els.resetScenarioBtn.addEventListener("click", resetAction);
    els.emptyReloadBtn.addEventListener("click", resetAction);
    els.errorResetBtn.addEventListener("click", resetAction);

    els.clearCampsBtn.addEventListener("click", () => {
      state.customCamps = [];
      runSolver();
    });

    document.querySelectorAll(".tool-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tool-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.activeTool = btn.getAttribute("data-tool");
      });
    });

    els.mapCanvas.addEventListener("mousemove", (e) => {
      if (!state.mission) return;
      const rect = els.mapCanvas.getBoundingClientRect();
      const px = ((e.clientX - rect.left) / rect.width) * els.mapCanvas.width;
      const py = ((e.clientY - rect.top) / rect.height) * els.mapCanvas.height;
      const cell = getMapGeometry().toGrid(px, py);
      state.hoverCell = cell;
      if (!cell) {
        els.mapTooltip.classList.add("hidden");
        renderMap();
        return;
      }
      const [gx, gy] = cell;
      const elev = state.mission.elevation && state.mission.elevation[gy] ? state.mission.elevation[gy][gx] : 0;
      const camp = (state.mission.camps || []).find((c) => c.x === gx && c.y === gy);
      let info = `Grid (${gx}, ${gy}) | Elevasi: ${elev.toFixed(0)} m`;
      if (camp) {
        info = `${camp.name} (${camp.urgency}) | Muatan: ${camp.demand_kg} kg | Batas: ${camp.time_window_min} mnt`;
      }
      els.mapTooltip.textContent = info;
      els.mapTooltip.style.left = `${Math.min(e.clientX - rect.left + 12, rect.width - 210)}px`;
      els.mapTooltip.style.top = `${Math.max(8, e.clientY - rect.top - 34)}px`;
      els.mapTooltip.classList.remove("hidden");
      renderMap();
    });

    els.mapCanvas.addEventListener("mouseleave", () => {
      state.hoverCell = null;
      els.mapTooltip.classList.add("hidden");
      renderMap();
    });

    els.mapCanvas.addEventListener("click", (e) => {
      if (!state.mission || state.activeTool === "inspect") return;
      if (!state.serverOnline) return;
      const rect = els.mapCanvas.getBoundingClientRect();
      const px = ((e.clientX - rect.left) / rect.width) * els.mapCanvas.width;
      const py = ((e.clientY - rect.top) / rect.height) * els.mapCanvas.height;
      const cell = getMapGeometry().toGrid(px, py);
      if (!cell) return;
      const [gx, gy] = cell;

      if (state.activeTool === "add_camp") {
        const list = state.customCamps ? [...state.customCamps] : [...state.mission.camps];
        const nextId = list.reduce((mx, c) => Math.max(mx, c.id), 0) + 1;
        list.push({
          id: nextId,
          name: `Posko Tambahan ${nextId}`,
          x: gx,
          y: gy,
          urgency: "TINGGI",
          demand_kg: 1.8,
          time_window_min: 50,
          supply_type: "Paket Medis",
        });
        state.customCamps = list;
        runSolver();
      } else if (state.activeTool === "add_obstacle") {
        const obs = state.customObstacles ? [...state.customObstacles] : [...state.mission.obstacles];
        if (!obs.some((o) => o[0] === gx && o[1] === gy)) {
          obs.push([gx, gy]);
          state.customObstacles = obs;
          runSolver();
        }
      } else if (state.activeTool === "erase_obstacle") {
        const obs = (state.customObstacles || state.mission.obstacles).filter(
          (o) => !(o[0] === gx && o[1] === gy)
        );
        state.customObstacles = obs;
        runSolver();
      }
    });

    const togglePlay = () => {
      if (state.progress >= 1.0) state.progress = 0.0;
      state.playing = !state.playing;
      state.lastFrameTime = performance.now();
      els.playPauseBtn.textContent = state.playing ? "Jeda" : "Putar";
    };

    els.playPauseBtn.addEventListener("click", togglePlay);
    els.replayBtn.addEventListener("click", () => {
      state.progress = 0.0;
      state.playing = true;
      state.lastFrameTime = performance.now();
      els.playPauseBtn.textContent = "Jeda";
      renderMap();
    });

    els.timeScrubber.addEventListener("input", () => {
      state.playing = false;
      els.playPauseBtn.textContent = "Putar";
      state.progress = Number(els.timeScrubber.value) / 100.0;
      renderMap();
    });

    document.querySelectorAll(".speed-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".speed-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.speed = Number(btn.getAttribute("data-speed"));
      });
    });

    els.clearFocusDroneBtn.addEventListener("click", () => {
      state.focusedDroneId = null;
      els.clearFocusDroneBtn.classList.add("hidden");
      renderChartsAndManifest();
      renderMap();
    });

    // Video modal + Escape + Space shortcuts
    const openModal = () => {
      els.videoModal.classList.remove("hidden");
      els.closeVideoModalBtn.focus();
    };
    const closeModal = () => {
      els.videoModal.classList.add("hidden");
      els.modalDemoVideo.pause();
    };
    els.openVideoModalBtn.addEventListener("click", openModal);
    els.closeVideoModalBtn.addEventListener("click", closeModal);
    els.videoModal.addEventListener("click", (e) => {
      if (e.target === els.videoModal) closeModal();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !els.videoModal.classList.contains("hidden")) {
        closeModal();
      } else if (
        e.code === "Space" &&
        !["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(document.activeElement.tagName)
      ) {
        e.preventDefault();
        togglePlay();
      }
    });
  }

  async function boot() {
    const savedTheme = localStorage.getItem("aerorelief_theme") || "light";
    document.documentElement.setAttribute("data-theme", savedTheme);
    els.themeBtn.textContent = savedTheme === "dark" ? "Mode Terang" : "Mode Malam";
    syncSliderLabels();
    initEvents();
    await checkBackend();
    await runSolver();
    requestAnimationFrame(animationLoop);
  }

  boot();
})();
