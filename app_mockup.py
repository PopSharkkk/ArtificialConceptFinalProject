"""
AeroRelief 2.5D Interactive Simulator Dashboard (Streamlit)
Implements PRD.md:
- Custom Grid up to 100x100 with consistent horizontal & 10m-step elevation scaling
- Multi-Depot VRPTW-BL Genetic Algorithm (Battery, Payload, Time Windows, Urgency)
- Dynamic Obstacles: Moving Weather Storm Cell & Spreading Wildfire (Karhutla)
- Real-Time Animation, Live Hazard Injection, Event-Driven A* Re-routing & Telemetry
"""

from __future__ import annotations

import base64
import math
import random
import time
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from aerorelief_engine import (
    AeroReliefSimulator,
    Depot,
    DisasterCamp,
    DroneConfig,
    GridEnvironment25D,
    MultiDepotVRPTWGA,
    WeatherStormCell,
    WildfireHazard,
    compute_route_matrix,
    generate_random_scenario_layout,
)

st.set_page_config(
    page_title="AeroRelief 2.5D | Emergency Drone Routing",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Calm, accessible operational palette (neutral slate base + cobalt accent + semantic alerts)
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    .ar-header {
        margin-bottom: 0.75rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #E2E8F0;
    }
    .ar-title {
        font-size: 1.65rem;
        font-weight: 700;
        color: #0F172A;
        letter-spacing: -0.02em;
        margin: 0;
        line-height: 1.25;
    }
    .ar-subtitle {
        font-size: 0.92rem;
        color: #475569;
        margin: 0.25rem 0 0 0;
    }
    .ar-section-label {
        font-size: 0.78rem;
        font-weight: 600;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin: 0.25rem 0 0.4rem 0;
    }
    .ar-drone-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 0.75rem 0.9rem;
        margin-bottom: 0.55rem;
    }
    .ar-drone-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.35rem;
        font-variant-numeric: tabular-nums;
    }
    .ar-drone-name {
        font-weight: 600;
        color: #0F172A;
        font-size: 0.92rem;
    }
    .ar-drone-meta {
        font-size: 0.82rem;
        color: #475569;
        font-variant-numeric: tabular-nums;
    }
    .ar-status-pill {
        display: inline-block;
        padding: 0.14rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .ar-pill-active { background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; }
    .ar-pill-ok     { background: #F0FDF4; color: #166534; border: 1px solid #BBF7D0; }
    .ar-pill-warn   { background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A; }
    .ar-pill-danger { background: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; }
    .ar-pill-muted  { background: #F8FAFC; color: #475569; border: 1px solid #CBD5E1; }

    /* Accessible tap target & keyboard focus ring */
    .stButton > button {
        min-height: 44px;
        border-radius: 6px;
        font-weight: 500;
        cursor: pointer;
    }
    .stButton > button:focus-visible,
    button:focus-visible,
    input:focus-visible,
    select:focus-visible {
        outline: 2px solid #1D4ED8 !important;
        outline-offset: 2px !important;
    }
    div[data-testid="stMetricValue"] {
        font-variant-numeric: tabular-nums;
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            transition-duration: 0.01ms !important;
            animation-duration: 0.01ms !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

DRONE_COLORS = ["#1D4ED8", "#0F766E", "#7C3AED", "#BE185D", "#B45309", "#0369A1"]
URGENCY_COLORS = {
    "CRITICAL": "#DC2626",
    "HIGH": "#B45309",
    "NORMAL": "#1D4ED8",
}


@st.cache_data(show_spinner=False)
def compute_cached_route_matrix(
    width: int,
    height: int,
    cell_size_m: float,
    max_altitude_m: float,
    terrain_seed: int,
    wind_dx: float,
    wind_dy: float,
    wind_speed: float,
    depots_tuple: Tuple[Tuple[int, str, int, int], ...],
    camps_tuple: Tuple[Tuple[int, str, int, int, float, str, float], ...],
    nfz_tuple: Tuple[Tuple[int, int, int, int], ...],
    storm_cfg: Tuple[bool, float, float, float, float, float],
    fire_cfg: Tuple[bool, int, int, float, int, float],
    climb_penalty: float,
):
    env = GridEnvironment25D(
        width=width,
        height=height,
        cell_size_m=cell_size_m,
        max_altitude_m=max_altitude_m,
        wind_vector=(wind_dx, wind_dy, wind_speed),
    )
    env.set_elevation_perlin(seed=terrain_seed, max_terrain_m=170.0)

    for x0, x1, y0, y1 in nfz_tuple:
        env.add_static_obstacle_zone(x0, x1, y0, y1)

    storm_on, sx, sy, s_core, s_turb, s_pen = storm_cfg
    if storm_on:
        env.add_storm(
            WeatherStormCell(
                id=1,
                name="Badai Utama",
                center=(sx, sy),
                core_radius=s_core,
                turbulence_radius=s_turb,
                velocity=(wind_dx * 0.45, wind_dy * 0.45),
                penalty_multiplier=s_pen,
                active=True,
            )
        )

    fire_on, fx, fy, f_prob, f_max_cells, f_move_dir = fire_cfg
    if fire_on:
        fire = WildfireHazard(
            id=1,
            name="Karhutla Awal",
            base_spread_prob=f_prob,
            wind_bias=0.50,
            slope_bias=0.30,
            burn_duration_min=8.0,
            spread_interval_min=1.0,
            max_active_cells=f_max_cells,
            max_burned_cells=f_max_cells * 2,
            move_dir_x=f_move_dir,
            active=True,
        )
        fire.ignite_zone(fx - 1, fx + 1, fy - 1, fy + 1, width, height)
        env.add_wildfire(fire)

    depots = [Depot(id=d[0], name=d[1], position=(d[2], d[3])) for d in depots_tuple]
    camps = [
        DisasterCamp(
            id=c[0], name=c[1], position=(c[2], c[3]), demand_kg=c[4], urgency=c[5], time_window_end_min=c[6]
        )
        for c in camps_tuple
    ]

    env.clear_protected_entities(
        depots,
        camps,
        max_depot_elev=max_altitude_m - 20.0,
        max_camp_elev=max_altitude_m - 10.0,
    )

    points: Dict[str, Tuple[int, int]] = {f"D{d.id}": d.position for d in depots}
    for c in camps:
        points[f"C{c.id}"] = c.position

    t0 = time.perf_counter()
    cost_matrix, dist_matrix, paths = compute_route_matrix(
        env, points, climb_penalty=climb_penalty, descent_penalty=0.4
    )
    t_matrix_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "env": env,
        "depots": depots,
        "camps": camps,
        "cost_matrix": cost_matrix,
        "dist_matrix": dist_matrix,
        "paths": paths,
        "t_matrix_ms": t_matrix_ms,
    }


@st.cache_data(show_spinner=False)
def solve_cached_ga_plan(
    env_key: tuple,
    _route_data: dict,
    num_drones: int,
    max_battery_wh: float,
    max_payload_kg: float,
    speed_mps: float,
    climb_penalty: float,
    pop_size: int,
    generations: int,
    alpha: float,
    beta: float,
    gamma: float,
):
    del env_key  # Included in cache key so GA invalidates when route_data changes
    depots = _route_data["depots"]
    drones = [
        DroneConfig(
            id=i + 1,
            home_depot_id=depots[i % len(depots)].id,
            max_battery_wh=max_battery_wh,
            max_payload_kg=max_payload_kg,
            speed_mps=speed_mps,
            climb_penalty_factor=climb_penalty,
            descent_penalty_factor=0.4,
        )
        for i in range(num_drones)
    ]

    t1 = time.perf_counter()
    ga = MultiDepotVRPTWGA(
        env=_route_data["env"],
        depots=depots,
        camps=_route_data["camps"],
        drones=drones,
        cost_matrix=_route_data["cost_matrix"],
        dist_matrix=_route_data["dist_matrix"],
        paths=_route_data["paths"],
        pop_size=pop_size,
        generations=generations,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
    )
    routes, ga_metrics = ga.run()
    t_ga_ms = (time.perf_counter() - t1) * 1000.0

    return {
        "drones": drones,
        "routes": routes,
        "ga_metrics": ga_metrics,
        "t_ga_ms": t_ga_ms,
    }


def clone_simulator_from_plan(plan: dict) -> AeroReliefSimulator:
    src_env: GridEnvironment25D = plan["env"]
    env = GridEnvironment25D(
        width=src_env.width,
        height=src_env.height,
        cell_size_m=src_env.cell_size_m,
        max_altitude_m=src_env.max_altitude_m,
        wind_vector=src_env.wind_vector,
    )
    env.elevation_grid = src_env.elevation_grid.copy()
    env.static_obstacles = src_env.static_obstacles.copy()
    env.storms = [
        WeatherStormCell(
            id=s.id,
            name=s.name,
            center=s.center,
            core_radius=s.core_radius,
            turbulence_radius=s.turbulence_radius,
            velocity=s.velocity,
            penalty_multiplier=s.penalty_multiplier,
            active=s.active,
        )
        for s in src_env.storms
    ]
    env.wildfires = [
        WildfireHazard(
            id=f.id,
            name=f.name,
            active_fire_cells=set(f.active_fire_cells),
            burned_cells=set(f.burned_cells),
            fire_age=dict(f.fire_age),
            base_spread_prob=f.base_spread_prob,
            wind_bias=f.wind_bias,
            slope_bias=f.slope_bias,
            burn_duration_min=f.burn_duration_min,
            spread_interval_min=f.spread_interval_min,
            max_active_cells=f.max_active_cells,
            max_burned_cells=f.max_burned_cells,
            move_dir_x=f.move_dir_x,
            time_since_last_spread=f.time_since_last_spread,
            active=f.active,
            _burned_order=list(f._burned_order),
        )
        for f in src_env.wildfires
    ]
    return AeroReliefSimulator(
        env=env,
        depots=plan["depots"],
        camps=plan["camps"],
        drones=plan["drones"],
        routes=plan["routes"],
        initial_paths=plan["paths"],
    )


_MAP_CANVAS_HTML = """
<div class="ar-map-shell">
  <canvas id="ar-map" width="760" height="670"></canvas>
</div>
"""

_MAP_CANVAS_CSS = """
.ar-map-shell {
  width: 100%;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 6px;
  box-sizing: border-box;
}
#ar-map {
  display: block;
  width: 100%;
  height: auto;
  aspect-ratio: 760 / 670;
}
"""

_MAP_CANVAS_JS = """
function elevColor(elevM, maxElev) {
  const t = Math.max(0, Math.min(1, elevM / Math.max(160, maxElev)));
  const stops = [
    [248, 250, 252],
    [232, 239, 234],
    [200, 215, 205],
    [159, 181, 167],
  ];
  const scaled = t * (stops.length - 1);
  const idx = Math.min(stops.length - 2, Math.floor(scaled));
  const f = scaled - idx;
  const a = stops[idx], b = stops[idx + 1];
  const r = Math.round(a[0] + (b[0] - a[0]) * f);
  const g = Math.round(a[1] + (b[1] - a[1]) * f);
  const bl = Math.round(a[2] + (b[2] - a[2]) * f);
  return `rgb(${r},${g},${bl})`;
}

function drawRoundedRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function drawLabel(ctx, text, cx, cy, bg, border, fg) {
  ctx.font = "600 10.5px system-ui, -apple-system, sans-serif";
  const padX = 5;
  const tw = ctx.measureText(text).width;
  const bw = tw + padX * 2;
  const bh = 16;
  const bx = cx - bw / 2;
  const by = cy - bh / 2;
  drawRoundedRect(ctx, bx, by, bw, bh, 4);
  ctx.fillStyle = bg;
  ctx.fill();
  if (border) {
    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    ctx.stroke();
  }
  ctx.fillStyle = fg;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, cx, cy + 0.5);
}

function drawArrow(ctx, x1, y1, x2, y2, color, lw) {
  const dx = x2 - x1, dy = y2 - y1;
  const ang = Math.atan2(dy, dx);
  const head = 6;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = lw;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - head * Math.cos(ang - Math.PI / 6), y2 - head * Math.sin(ang - Math.PI / 6));
  ctx.lineTo(x2 - head * Math.cos(ang + Math.PI / 6), y2 - head * Math.sin(ang + Math.PI / 6));
  ctx.closePath();
  ctx.fill();
}

function buildTerrainLayer(data, w, h, dpr, plot) {
  const off = document.createElement("canvas");
  off.width = Math.round(w * dpr);
  off.height = Math.round(h * dpr);
  const ctx = off.getContext("2d");
  ctx.scale(dpr, dpr);

  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(0, 0, w, h);

  const gw = data.width, gh = data.height;
  const cellW = plot.w / gw;
  const cellH = plot.h / gh;
  const binStr = atob(data.elev_b64);

  for (let gy = 0; gy < gh; gy++) {
    const py = plot.y + (gh - 1 - gy) * cellH;
    for (let gx = 0; gx < gw; gx++) {
      const elevM = binStr.charCodeAt(gy * gw + gx) * 10;
      const px = plot.x + gx * cellW;
      ctx.fillStyle = elevColor(elevM, data.max_elev);
      ctx.fillRect(px, py, Math.ceil(cellW), Math.ceil(cellH));
      if (elevM > data.max_alt) {
        ctx.fillStyle = "rgba(120, 113, 108, 0.72)";
        ctx.beginPath();
        ctx.moveTo(px + cellW * 0.5, py + cellH * 0.18);
        ctx.lineTo(px + cellW * 0.82, py + cellH * 0.82);
        ctx.lineTo(px + cellW * 0.18, py + cellH * 0.82);
        ctx.closePath();
        ctx.fill();
      }
    }
  }

  // Subtle grid lines every ~5 cells
  const step = gw >= 70 ? 10 : 5;
  ctx.strokeStyle = "rgba(148, 163, 184, 0.28)";
  ctx.lineWidth = 0.8;
  for (let gx = 0; gx <= gw; gx += step) {
    const px = plot.x + gx * cellW;
    ctx.beginPath();
    ctx.moveTo(px, plot.y);
    ctx.lineTo(px, plot.y + plot.h);
    ctx.stroke();
  }
  for (let gy = 0; gy <= gh; gy += step) {
    const py = plot.y + (gh - gy) * cellH;
    ctx.beginPath();
    ctx.moveTo(plot.x, py);
    ctx.lineTo(plot.x + plot.w, py);
    ctx.stroke();
  }

  // Plot frame & axis labels
  ctx.strokeStyle = "#CBD5E1";
  ctx.lineWidth = 1;
  ctx.strokeRect(plot.x, plot.y, plot.w, plot.h);

  ctx.fillStyle = "#475569";
  ctx.font = "500 10.5px system-ui, -apple-system, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (let gx = 0; gx < gw; gx += step * 2) {
    const cx = plot.x + (gx + 0.5) * cellW;
    ctx.fillText(String(gx), cx, plot.y + plot.h + 5);
  }
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let gy = 0; gy < gh; gy += step * 2) {
    const cy = plot.y + (gh - 0.5 - gy) * cellH;
    ctx.fillText(String(gy), plot.x - 6, cy);
  }

  ctx.fillStyle = "#334155";
  ctx.font = "600 11px system-ui, -apple-system, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const kmW = ((gw * data.cell_size_m) / 1000).toFixed(1);
  const kmH = ((gh * data.cell_size_m) / 1000).toFixed(1);
  ctx.fillText(`Koordinat X (${Math.round(data.cell_size_m)} m/petak, lebar ${kmW} km)`, plot.x + plot.w / 2, plot.y + plot.h + 22);

  ctx.save();
  ctx.translate(16, plot.y + plot.h / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillText(`Koordinat Y (tinggi ${kmH} km)`, 0, 0);
  ctx.restore();

  // Elevation colorbar
  const cbX = plot.x + plot.w + 14;
  const cbW = 12;
  for (let i = 0; i < 60; i++) {
    const frac = 1 - i / 59;
    ctx.fillStyle = elevColor(frac * Math.max(160, data.max_elev), data.max_elev);
    ctx.fillRect(cbX, plot.y + (i / 60) * plot.h, cbW, Math.ceil(plot.h / 60) + 1);
  }
  ctx.strokeStyle = "#CBD5E1";
  ctx.strokeRect(cbX, plot.y, cbW, plot.h);
  ctx.fillStyle = "#475569";
  ctx.font = "500 10px system-ui, -apple-system, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText(`${Math.round(Math.max(160, data.max_elev))}m`, cbX + cbW + 4, plot.y + 4);
  ctx.fillText("0m", cbX + cbW + 4, plot.y + plot.h - 4);

  return off;
}

export default function(component) {
  const { parentElement, data } = component;
  const canvas = parentElement.querySelector("#ar-map");
  if (!canvas || !data) return;

  const w = 760, h = 670;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const targetW = Math.round(w * dpr);
  const targetH = Math.round(h * dpr);
  if (canvas.width !== targetW || canvas.height !== targetH) {
    canvas.width = targetW;
    canvas.height = targetH;
  }

  const plot = { x: 52, y: 34, w: 636, h: 552 };
  const gw = data.width, gh = data.height;
  const cellW = plot.w / gw;
  const cellH = plot.h / gh;
  const toX = (gx) => plot.x + (gx + 0.5) * cellW;
  const toY = (gy) => plot.y + (gh - 0.5 - gy) * cellH;

  const cache = canvas._arCache || (canvas._arCache = {
    terrainKey: null,
    terrainCanvas: null,
    prevDrones: {},
    prevStorms: {},
    rafId: null,
  });

  if (cache.rafId) {
    cancelAnimationFrame(cache.rafId);
    cache.rafId = null;
  }

  if (cache.terrainKey !== data.terrain_key || !cache.terrainCanvas) {
    cache.terrainCanvas = buildTerrainLayer(data, w, h, dpr, plot);
    cache.terrainKey = data.terrain_key;
    cache.prevDrones = {};
    cache.prevStorms = {};
  }

  const startDrones = {};
  for (const d of data.drones) {
    startDrones[d.id] = (!data.snap && cache.prevDrones[d.id]) ? cache.prevDrones[d.id] : d.pos;
  }
  const startStorms = {};
  for (const s of data.storms) {
    startStorms[s.id] = (!data.snap && cache.prevStorms[s.id]) ? cache.prevStorms[s.id] : s.center;
  }

  const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const duration = (data.playing && !data.snap && !reducedMotion) ? Math.max(80, data.interp_ms || 380) : 0;
  const tStart = performance.now();

  const renderFrame = (now) => {
    const p = duration > 0 ? Math.min(1, (now - tStart) / duration) : 1;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.drawImage(cache.terrainCanvas, 0, 0, w, h);

    // Header bar
    ctx.fillStyle = "#0F172A";
    ctx.font = "700 13px system-ui, -apple-system, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(`Peta Operasi 2.5D | t = ${data.sim_time_min.toFixed(2)} menit`, plot.x, 17);

    // Burned & active fire cells
    ctx.fillStyle = "rgba(148, 163, 184, 0.55)";
    for (const [fx, fy] of data.burned) {
      ctx.fillRect(plot.x + fx * cellW + 0.5, plot.y + (gh - 1 - fy) * cellH + 0.5, Math.max(3, cellW - 1), Math.max(3, cellH - 1));
    }
    ctx.fillStyle = "rgba(234, 88, 12, 0.90)";
    ctx.strokeStyle = "#9A3412";
    ctx.lineWidth = 1;
    for (const [fx, fy] of data.fires) {
      const rx = plot.x + fx * cellW + 0.5;
      const ry = plot.y + (gh - 1 - fy) * cellH + 0.5;
      const rw = Math.max(4, cellW - 1);
      const rh = Math.max(4, cellH - 1);
      ctx.fillRect(rx, ry, rw, rh);
      ctx.strokeRect(rx, ry, rw, rh);
    }

    // Storms (interpolated)
    for (const s of data.storms) {
      const s0 = startStorms[s.id] || s.center;
      const sx = s0[0] + (s.center[0] - s0[0]) * p;
      const sy = s0[1] + (s.center[1] - s0[1]) * p;
      cache.prevStorms[s.id] = [sx, sy];
      const px = toX(sx), py = toY(sy);

      ctx.save();
      ctx.beginPath();
      ctx.ellipse(px, py, s.turb_r * cellW, s.turb_r * cellH, 0, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(147, 197, 253, 0.16)";
      ctx.fill();
      ctx.setLineDash([5, 4]);
      ctx.strokeStyle = "#3B82F6";
      ctx.lineWidth = 1.3;
      ctx.stroke();
      ctx.restore();

      ctx.beginPath();
      ctx.ellipse(px, py, s.core_r * cellW, s.core_r * cellH, 0, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(29, 78, 216, 0.36)";
      ctx.fill();
      ctx.strokeStyle = "#1E3A8A";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      drawArrow(ctx, px, py, toX(sx + s.vx * 3.5), toY(sy + s.vy * 3.5), "#1E3A8A", 1.6);
    }

    // Wind badge (top-left of plot)
    const wn = Math.hypot(data.wind[0], data.wind[1]);
    if (wn > 1e-6) {
      const ux = data.wind[0] / wn, uy = data.wind[1] / wn;
      const wx0 = plot.x + 16, wy0 = plot.y + 30;
      drawLabel(ctx, `Angin ${Math.round(data.wind[2])} m/s`, plot.x + 48, plot.y + 14, "rgba(255,255,255,0.92)", "#CBD5E1", "#0F172A");
      drawArrow(ctx, wx0, wy0, wx0 + ux * 24, wy0 - uy * 24, "#334155", 1.7);
    }

    // Drone paths & markers
    for (const d of data.drones) {
      const d0 = startDrones[d.id] || d.pos;
      const dx = d0[0] + (d.pos[0] - d0[0]) * p;
      const dy = d0[1] + (d.pos[1] - d0[1]) * p;
      cache.prevDrones[d.id] = [dx, dy];

      if (d.planned.length >= 2) {
        ctx.save();
        ctx.setLineDash([2, 4]);
        ctx.strokeStyle = d.color;
        ctx.globalAlpha = 0.30;
        ctx.lineWidth = 1.3;
        ctx.beginPath();
        ctx.moveTo(toX(d.planned[0][0]), toY(d.planned[0][1]));
        for (let i = 1; i < d.planned.length; i++) ctx.lineTo(toX(d.planned[i][0]), toY(d.planned[i][1]));
        ctx.stroke();
        ctx.restore();
      }
      if (d.rem.length >= 2) {
        ctx.save();
        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = d.color;
        ctx.globalAlpha = 0.72;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(toX(dx), toY(dy));
        for (let i = 1; i < d.rem.length; i++) ctx.lineTo(toX(d.rem[i][0]), toY(d.rem[i][1]));
        ctx.stroke();
        ctx.restore();
      }
      if (d.trail.length >= 1) {
        ctx.strokeStyle = d.color;
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        ctx.moveTo(toX(d.trail[0][0]), toY(d.trail[0][1]));
        for (let i = 1; i < d.trail.length; i++) ctx.lineTo(toX(d.trail[i][0]), toY(d.trail[i][1]));
        ctx.lineTo(toX(dx), toY(dy));
        ctx.stroke();
      }
    }

    // Depots
    for (const dep of data.depots) {
      const px = toX(dep.x), py = toY(dep.y);
      ctx.fillStyle = "#0F172A";
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1.8;
      ctx.fillRect(px - 6, py - 6, 12, 12);
      ctx.strokeRect(px - 6, py - 6, 12, 12);
      drawLabel(ctx, dep.name, px, py + 16, "rgba(255,255,255,0.92)", "#94A3B8", "#0F172A");
    }

    // Camps
    for (const c of data.camps) {
      const px = toX(c.x), py = toY(c.y);
      ctx.beginPath();
      ctx.arc(px, py, 5.5, 0, Math.PI * 2);
      ctx.fillStyle = c.color;
      ctx.fill();
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1.4;
      ctx.stroke();
      drawLabel(ctx, `P${c.id} (${c.urg_short})`, px, py - 14, "rgba(255,255,255,0.90)", c.color, "#0F172A");
    }

    // Drones on top
    for (const d of data.drones) {
      const cur = cache.prevDrones[d.id] || d.pos;
      const px = toX(cur[0]), py = toY(cur[1]);
      const isDead = d.state === "Out of Battery";
      const isHold = d.state === "Stay at Depot" || d.state === "Stay at Posko";
      const col = isDead ? "#B91C1C" : (isHold ? "#B45309" : d.color);
      const badge = isDead ? `D${d.id} 0%` : (isHold ? `D${d.id} HOLD` : `D${d.id}`);

      ctx.fillStyle = col;
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1.5;
      if (isDead) {
        ctx.beginPath();
        ctx.moveTo(px - 6, py - 6); ctx.lineTo(px + 6, py + 6);
        ctx.moveTo(px + 6, py - 6); ctx.lineTo(px - 6, py + 6);
        ctx.strokeStyle = col;
        ctx.lineWidth = 3;
        ctx.stroke();
      } else if (isHold) {
        ctx.fillRect(px - 5.5, py - 5.5, 11, 11);
        ctx.strokeRect(px - 5.5, py - 5.5, 11, 11);
      } else {
        ctx.beginPath();
        ctx.moveTo(px, py - 7.5);
        ctx.lineTo(px + 6.5, py + 5.5);
        ctx.lineTo(px - 6.5, py + 5.5);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
      drawLabel(ctx, badge, px, py + 15, col, null, "#FFFFFF");
    }

    // Compact legend footer
    const legendItems = [
      ["#0F172A", "Depot"],
      ["#DC2626", "Posko Kritis"],
      ["#15803D", "Terkirim"],
      ["#1D4ED8", "Inti Badai"],
      ["#EA580C", "Api Aktif"],
      ["#94A3B8", "Bekas Api"],
    ];
    let lx = plot.x;
    const ly = h - 14;
    ctx.font = "500 10.5px system-ui, -apple-system, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    for (const [col, lbl] of legendItems) {
      ctx.fillStyle = col;
      ctx.fillRect(lx, ly - 4, 9, 9);
      ctx.fillStyle = "#334155";
      ctx.fillText(lbl, lx + 13, ly + 0.5);
      lx += 13 + ctx.measureText(lbl).width + 16;
    }

    if (p < 1) {
      cache.rafId = requestAnimationFrame(renderFrame);
    } else {
      cache.rafId = null;
    }
  };

  cache.rafId = requestAnimationFrame(renderFrame);

  return () => {
    if (cache.rafId) {
      cancelAnimationFrame(cache.rafId);
      cache.rafId = null;
    }
  };
}
"""

MAP_CANVAS = st.components.v2.component(
    "aerorelief_map_canvas",
    html=_MAP_CANVAS_HTML,
    css=_MAP_CANVAS_CSS,
    js=_MAP_CANVAS_JS,
)


def build_map_payload(
    sim: AeroReliefSimulator,
    terrain_key: str,
    playing: bool,
    interp_ms: int,
    snap: bool,
) -> dict:
    env = sim.env
    elev_bytes = (env.elevation_grid / 10.0).clip(0, 255).astype(np.uint8).tobytes()
    elev_b64 = base64.b64encode(elev_bytes).decode("ascii")

    burned: List[List[int]] = []
    fires: List[List[int]] = []
    for f in env.wildfires:
        if not f.active:
            continue
        for cx, cy in f.burned_cells:
            burned.append([int(cx), int(cy)])
        for cx, cy in f.active_fire_cells:
            fires.append([int(cx), int(cy)])

    storms = [
        {
            "id": s.id,
            "center": [float(s.center[0]), float(s.center[1])],
            "core_r": float(s.core_radius),
            "turb_r": float(s.turbulence_radius),
            "vx": float(s.velocity[0]),
            "vy": float(s.velocity[1]),
        }
        for s in env.storms
        if s.active
    ]

    drones = []
    for did, ds in sim.drone_states.items():
        rem = ds.active_waypoints[ds.waypoint_idx :] if ds.active_waypoints else []
        drones.append(
            {
                "id": did,
                "pos": [int(ds.current_pos[0]), int(ds.current_pos[1])],
                "state": ds.state,
                "color": DRONE_COLORS[(did - 1) % len(DRONE_COLORS)],
                "planned": [[int(p[0]), int(p[1])] for p in ds.planned_full_path],
                "rem": [[int(p[0]), int(p[1])] for p in rem],
                "trail": [[int(p[0]), int(p[1])] for p in ds.trail],
            }
        )

    camps = []
    for c in sim.camps.values():
        if c.status.startswith("Delivered"):
            col = "#15803D"
        elif c.status == "Unreachable":
            col = "#64748B"
        else:
            col = URGENCY_COLORS.get(c.urgency, "#1D4ED8")
        camps.append(
            {
                "id": c.id,
                "x": int(c.position[0]),
                "y": int(c.position[1]),
                "urg_short": c.urgency[0],
                "color": col,
            }
        )

    depots = [
        {"id": d.id, "name": d.name, "x": int(d.position[0]), "y": int(d.position[1])}
        for d in sim.depots.values()
    ]

    return {
        "terrain_key": terrain_key,
        "width": int(env.width),
        "height": int(env.height),
        "cell_size_m": float(env.cell_size_m),
        "max_alt": float(env.max_altitude_m),
        "max_elev": float(env.elevation_grid.max()) if env.elevation_grid.size else 160.0,
        "elev_b64": elev_b64,
        "wind": [float(env.wind_vector[0]), float(env.wind_vector[1]), float(env.wind_vector[2])],
        "sim_time_min": float(sim.sim_time_min),
        "burned": burned,
        "fires": fires,
        "storms": storms,
        "drones": drones,
        "camps": camps,
        "depots": depots,
        "playing": bool(playing),
        "interp_ms": int(interp_ms),
        "snap": bool(snap),
    }


def inject_hazard_ahead_of_drone(sim: AeroReliefSimulator, hazard_type: str) -> None:
    """Injects a Storm Cell or Wildfire directly ahead of an active flying drone to demonstrate A* re-routing."""
    target_ds = None
    for ds in sim.drone_states.values():
        if ds.state in ("Flying", "Returning", "Re-routing") and ds.active_waypoints:
            if len(ds.active_waypoints) - ds.waypoint_idx > 4:
                target_ds = ds
                break
    if target_ds is None:
        cx, cy = sim.env.width // 2, sim.env.height // 2
        label = "tengah peta"
    else:
        ahead_idx = min(len(target_ds.active_waypoints) - 2, target_ds.waypoint_idx + max(3, (len(target_ds.active_waypoints) - target_ds.waypoint_idx) // 2))
        cx, cy = target_ds.active_waypoints[ahead_idx]
        label = f"jalur Drone #{target_ds.drone_id} ({cx},{cy})"

    if hazard_type == "storm":
        new_id = len(sim.env.storms) + 1
        wx, wy, _ = sim.env.wind_vector
        sim.env.add_storm(
            WeatherStormCell(
                id=new_id,
                name=f"Badai Dadakan #{new_id}",
                center=(float(cx), float(cy)),
                core_radius=max(2.0, sim.env.width * 0.05),
                turbulence_radius=max(3.5, sim.env.width * 0.09),
                velocity=(wx * 0.4, wy * 0.4),
                penalty_multiplier=1.9,
                active=True,
            )
        )
        sim.events.append(f"[t={sim.sim_time_min:.1f}m] INJEKSI: Cuaca Buruk baru muncul di {label}!")
    else:
        new_id = len(sim.env.wildfires) + 1
        fire = WildfireHazard(
            id=new_id,
            name=f"Karhutla Baru #{new_id}",
            base_spread_prob=0.30,
            wind_bias=0.50,
            slope_bias=0.30,
            burn_duration_min=8.0,
            spread_interval_min=1.0,
            max_active_cells=16,
            max_burned_cells=32,
            move_dir_x=1.0 if sim.env.wind_vector[0] >= 0 else -1.0,
            active=True,
        )
        fire.ignite_zone(cx - 1, cx + 1, cy - 1, cy + 1, sim.env.width, sim.env.height)
        protected = {d.position for d in sim.depots.values()} | {c.position for c in sim.camps.values()}
        fire.active_fire_cells.difference_update(protected)
        sim.env.add_wildfire(fire)
        sim.events.append(f"[t={sim.sim_time_min:.1f}m] INJEKSI: Titik Api Karhutla baru muncul di {label}!")

    # Immediately run re-routing check so the user sees instant response even when paused
    for did, ds in sim.drone_states.items():
        if ds.state not in ("Standby", "Completed", "Out of Battery", "Stay at Depot", "Stay at Posko"):
            sim._check_and_reroute(ds, sim.drones_cfg[did])


# ==============================================================================
# UI HEADER & SIDEBAR CONFIGURATION
# ==============================================================================
st.markdown(
    """
    <div class="ar-header">
        <h1 class="ar-title">AeroRelief 2.5D</h1>
        <p class="ar-subtitle">Simulasi distribusi logistik medis multi-depot dengan jalur A* 2.5D dan optimasi rute GA.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Peta & Penempatan")
    if "terrain_seed" not in st.session_state:
        st.session_state.terrain_seed = random.randint(1, 99999)
    if "layout_seed" not in st.session_state:
        st.session_state.layout_seed = random.randint(1, 99999)

    grid_size = st.slider("Ukuran Grid (N x N)", min_value=20, max_value=100, value=50, step=10)
    cell_scale_label = st.selectbox(
        "Skala per Petak",
        options=["100 m/petak", "200 m/petak", "500 m/petak", "1000 m/petak (1 km)"],
        index=1,
    )
    cell_size_m = float(cell_scale_label.split()[0])
    max_altitude_m = st.slider("Plafon Terbang (m)", min_value=80, max_value=250, value=160, step=10)

    c_rand1, c_rand2 = st.columns(2)
    if c_rand1.button("Acak Peta", width="stretch"):
        st.session_state.terrain_seed = random.randint(1, 99999)
        st.rerun()
    if c_rand2.button("Acak Posisi", width="stretch"):
        st.session_state.layout_seed = random.randint(1, 99999)
        st.rerun()
    if st.button("Acak Semua (Peta & Posisi)", width="stretch"):
        st.session_state.terrain_seed = random.randint(1, 99999)
        st.session_state.layout_seed = random.randint(1, 99999)
        st.rerun()
    terrain_seed = int(st.session_state.terrain_seed)
    layout_seed = int(st.session_state.layout_seed)
    st.caption(f"Seed peta: #{terrain_seed} | Seed posisi: #{layout_seed}")

    st.divider()
    st.subheader("Obstacle Dinamis Awal")
    storm_on = st.checkbox("Badai bergerak", value=True)
    storm_pen = st.slider("Penalti turbulensi", 1.2, 3.0, 1.85, 0.05) if storm_on else 1.85
    fire_on = st.checkbox("Api Karhutla", value=True)
    if fire_on:
        fire_prob = st.slider("Laju rambat api", 0.10, 0.60, 0.28, 0.02)
        fire_max_cells = st.slider("Batas area api (petak)", 8, 40, 18, 2)
        fire_dir_choice = st.selectbox("Arah gerak api", ["Kanan (+X)", "Kiri (-X)", "Ikuti Angin"], index=0)
    else:
        fire_prob, fire_max_cells, fire_dir_choice = 0.28, 18, "Kanan (+X)"

    storm_core_r = max(2.0, grid_size * 0.055)
    storm_turb_r = max(4.0, grid_size * 0.11)
    initial_layout = generate_random_scenario_layout(
        width=grid_size,
        height=grid_size,
        seed=layout_seed,
        storm_core_radius=storm_core_r,
        storm_turb_radius=storm_turb_r,
    )
    init_storm_x, init_storm_y = initial_layout["storm_center"]
    init_fire_x, init_fire_y = initial_layout["fire_center"]
    st.caption(
        f"Posisi awal: badai ({int(init_storm_x)}, {int(init_storm_y)}), api ({init_fire_x}, {init_fire_y})"
    )

    st.divider()
    st.subheader("Armada Drone")
    num_drones = st.slider("Jumlah Drone", min_value=1, max_value=6, value=3)
    max_battery_wh = st.slider("Kapasitas Baterai (Wh)", min_value=40, max_value=800, value=350, step=10)
    max_payload_kg = st.slider("Muatan Maksimal (kg)", min_value=2.0, max_value=15.0, value=8.0, step=0.5)
    speed_mps = st.slider("Kecepatan Jelajah (m/s)", min_value=8.0, max_value=30.0, value=18.0, step=1.0)

    with st.expander("Parameter Lanjutan A* & GA", expanded=False):
        c_w1, c_w2, c_w3 = st.columns(3)
        wind_dx = c_w1.number_input("Angin dX", value=1.0, step=0.2, format="%.1f")
        wind_dy = c_w2.number_input("Angin dY", value=0.4, step=0.2, format="%.1f")
        wind_speed = c_w3.number_input("Laju (m/s)", min_value=0.0, max_value=25.0, value=9.0, step=1.0)
        climb_penalty = st.slider("Penalti Menanjak (A*)", min_value=0.5, max_value=5.0, value=2.5, step=0.25)
        pop_size = st.slider("Populasi GA", 20, 120, 50, 10)
        generations = st.slider("Generasi GA", 20, 150, 70, 10)
        alpha = st.number_input("Bobot Alpha (Jarak/Energi)", value=1.0, min_value=0.1, step=0.5)
        beta = st.number_input("Bobot Beta (Keterlambatan)", value=2.5, min_value=0.1, step=0.5)
        gamma = st.number_input("Bobot Gamma (Pelanggaran)", value=15.0, min_value=1.0, step=1.0)


with st.expander("Konfigurasi Depot & Posko (Koordinat, Muatan, Urgensi)", expanded=False):
    tab_depots, tab_camps = st.tabs(["Depot / Basecamp", "Posko Bencana"])

    default_depots_df = pd.DataFrame(
        [
            {"id": d.id, "nama": d.name, "x": d.position[0], "y": d.position[1]}
            for d in initial_layout["depots"]
        ]
    )
    default_camps_df = pd.DataFrame(
        [
            {
                "id": c.id,
                "nama": f"Posko {c.id}",
                "x": c.position[0],
                "y": c.position[1],
                "demand_kg": c.demand_kg,
                "urgency": c.urgency,
                "time_window_min": c.time_window_end_min,
            }
            for c in initial_layout["camps"]
        ]
    )

    with tab_depots:
        depots_df = st.data_editor(
            default_depots_df,
            num_rows="dynamic",
            key=f"depots_ed_{grid_size}_{layout_seed}",
            width="stretch",
        )
    with tab_camps:
        camps_df = st.data_editor(
            default_camps_df,
            num_rows="dynamic",
            key=f"camps_ed_{grid_size}_{layout_seed}",
            column_config={
                "urgency": st.column_config.SelectboxColumn("Urgensi", options=["CRITICAL", "HIGH", "NORMAL"], required=True),
            },
            width="stretch",
        )


def _clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


depots_tuple = tuple(
    (int(row["id"]), str(row["nama"]), _clamp(row["x"], 0, grid_size - 1), _clamp(row["y"], 0, grid_size - 1))
    for _, row in depots_df.dropna().iterrows()
)
if not depots_tuple:
    fallback_xy = max(1, grid_size // 10)
    depots_tuple = ((1, "Depot Default", fallback_xy, fallback_xy),)

camps_tuple = tuple(
    (
        int(row["id"]),
        str(row["nama"]),
        _clamp(row["x"], 0, grid_size - 1),
        _clamp(row["y"], 0, grid_size - 1),
        float(row["demand_kg"]),
        str(row["urgency"]),
        float(row["time_window_min"]),
    )
    for _, row in camps_df.dropna().iterrows()
)

nfz_tuple: Tuple[Tuple[int, int, int, int], ...] = ()  # Static No-Fly Zone disabled

if fire_dir_choice == "Kanan (+X)":
    fire_move_dir = 1.0
elif fire_dir_choice == "Kiri (-X)":
    fire_move_dir = -1.0
else:
    fire_move_dir = 1.0 if wind_dx >= 0 else -1.0

storm_cfg = (storm_on, float(init_storm_x), float(init_storm_y), storm_core_r, storm_turb_r, storm_pen)
fire_cfg = (fire_on, int(init_fire_x), int(init_fire_y), fire_prob, fire_max_cells, fire_move_dir)

plan_key = (
    grid_size, grid_size, cell_size_m, max_altitude_m, terrain_seed,
    wind_dx, wind_dy, wind_speed, depots_tuple, camps_tuple, nfz_tuple,
    storm_cfg, fire_cfg, num_drones, max_battery_wh, max_payload_kg,
    speed_mps, climb_penalty, pop_size, generations, alpha, beta, gamma,
)

if st.session_state.get("plan_key") != plan_key or "plan" not in st.session_state or "sim" not in st.session_state:
    with st.spinner("Menghitung matriks jalur A* 2.5D & optimasi armada GA..."):
        env_key = (
            grid_size, grid_size, cell_size_m, max_altitude_m, terrain_seed,
            wind_dx, wind_dy, wind_speed, depots_tuple, camps_tuple, nfz_tuple,
            storm_cfg, fire_cfg, climb_penalty,
        )
        route_data = compute_cached_route_matrix(*env_key)
        ga_data = solve_cached_ga_plan(
            env_key,
            route_data,
            num_drones,
            max_battery_wh,
            max_payload_kg,
            speed_mps,
            climb_penalty,
            pop_size,
            generations,
            alpha,
            beta,
            gamma,
        )
        plan = {
            "env": route_data["env"],
            "depots": route_data["depots"],
            "camps": route_data["camps"],
            "drones": ga_data["drones"],
            "routes": ga_data["routes"],
            "paths": route_data["paths"],
            "ga_metrics": ga_data["ga_metrics"],
            "t_matrix_ms": route_data["t_matrix_ms"],
            "t_ga_ms": ga_data["t_ga_ms"],
        }
    st.session_state.plan_key = plan_key
    st.session_state.plan = plan
    st.session_state.sim = clone_simulator_from_plan(plan)
    st.session_state.playing = False


# ==============================================================================
# SIMULATION VIEWPORT FRAGMENT (Client-side Canvas: zero image reload or flicker)
# ==============================================================================
PLAY_INTERVAL_S = 0.45


def _status_pill_class(state: str) -> str:
    if state in ("Flying", "Re-routing", "Returning"):
        return "ar-pill-active"
    if state == "Completed":
        return "ar-pill-ok"
    if state in ("Stay at Depot", "Stay at Posko", "Low Battery"):
        return "ar-pill-warn"
    if state == "Out of Battery":
        return "ar-pill-danger"
    return "ar-pill-muted"


@st.fragment(run_every=PLAY_INTERVAL_S if st.session_state.get("playing") else None)
def render_simulation_viewport() -> None:
    plan: dict = st.session_state.plan
    sim: AeroReliefSimulator = st.session_state.sim
    avg_speed = sum(c.speed_mps for c in sim.drones_cfg.values()) / max(1, len(sim.drones_cfg))
    tick_dt_min = max(0.03, min(0.5, (0.65 * sim.env.cell_size_m / max(1.0, avg_speed)) / 60.0))

    manual_action = False
    snap_frame = False
    ctrl_cols = st.columns([1.15, 1.0, 1.0, 0.95, 1.45, 1.45])
    if ctrl_cols[0].button(
        "Pause" if st.session_state.playing else "Play",
        type="primary",
        width="stretch",
    ):
        st.session_state.playing = not st.session_state.playing
        st.rerun()
    if ctrl_cols[1].button("+1 Tick", width="stretch"):
        was_playing = st.session_state.playing
        st.session_state.playing = False
        manual_action = True
        sim.step(dt_min=tick_dt_min)
        if was_playing:
            st.rerun()
    if ctrl_cols[2].button("+5 Ticks", width="stretch"):
        was_playing = st.session_state.playing
        st.session_state.playing = False
        manual_action = True
        snap_frame = True
        for _ in range(5):
            sim.step(dt_min=tick_dt_min)
        if was_playing:
            st.rerun()
    if ctrl_cols[3].button("Reset", width="stretch"):
        was_playing = st.session_state.playing
        st.session_state.playing = False
        manual_action = True
        snap_frame = True
        st.session_state.sim = clone_simulator_from_plan(plan)
        sim = st.session_state.sim
        if was_playing:
            st.rerun()
    if ctrl_cols[4].button("Suntik Badai", width="stretch"):
        manual_action = True
        snap_frame = True
        inject_hazard_ahead_of_drone(sim, "storm")
    if ctrl_cols[5].button("Suntik Api", width="stretch"):
        manual_action = True
        snap_frame = True
        inject_hazard_ahead_of_drone(sim, "fire")

    if st.session_state.playing and not manual_action:
        if sim.is_finished():
            st.session_state.playing = False
            st.rerun()
        else:
            sim.step(dt_min=tick_dt_min)

    if not sim.camps:
        st.info("Belum ada posko bencana pada daftar. Tambahkan minimal satu baris posko pada panel Konfigurasi Depot & Posko.")
        return

    unreachable_count = sum(1 for c in sim.camps.values() if c.status == "Unreachable")
    if unreachable_count > 0:
        st.warning(f"{unreachable_count} posko tidak memiliki jalur aman dari depot saat ini dan ditandai Unreachable.")

    # KPI Strip (4 concise operational metrics)
    delivered_on_time = sum(1 for c in sim.camps.values() if c.status == "Delivered On-Time")
    delivered_late = sum(1 for c in sim.camps.values() if c.status == "Delivered Late")
    total_reroutes = sum(ds.reroute_count for ds in sim.drone_states.values())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Waktu Simulasi", f"{sim.sim_time_min:.2f} mnt")
    k2.metric(
        "Posko Terkirim",
        f"{delivered_on_time + delivered_late} / {len(sim.camps)}",
        f"Tepat waktu: {delivered_on_time} | Terlambat: {delivered_late}",
    )
    k3.metric("Jarak Rencana GA", f"{plan['ga_metrics']['total_dist_km']:.2f} km")
    k4.metric(
        "Re-routing A*",
        f"{total_reroutes} kali",
        f"A*: {plan['t_matrix_ms']:.0f} ms | GA: {plan['t_ga_ms']:.0f} ms",
    )

    # MAIN WORKSPACE: MAP (LEFT) & TABBED CONSOLE (RIGHT)
    col_map, col_tel = st.columns([1.5, 1.0], gap="medium")

    with col_map:
        terrain_sig = f"{sim.env.width}x{sim.env.height}_{sim.env.cell_size_m}_{sim.env.max_altitude_m}_{hash(st.session_state.plan_key[:6])}"
        MAP_CANVAS(
            key="aerorelief_map",
            data=build_map_payload(
                sim,
                terrain_key=terrain_sig,
                playing=st.session_state.playing,
                interp_ms=int(PLAY_INTERVAL_S * 880),
                snap=snap_frame or sim.sim_time_min == 0.0,
            ),
        )

    with col_tel:
        tab_fleet, tab_camps_status, tab_log = st.tabs(["Armada", "Posko", "Log Misi"])

        with tab_fleet:
            if not sim.drone_states:
                st.info("Tidak ada drone aktif pada armada.")
            for did, ds in sim.drone_states.items():
                bat_pct = ds.remaining_battery_pct
                target_lbl = ds.current_target_key or "Selesai / Standby"
                pill_cls = _status_pill_class(ds.state)
                st.markdown(
                    f"""
                    <div class="ar-drone-card">
                        <div class="ar-drone-head">
                            <span class="ar-drone-name">Drone #{did} (Depot {ds.home_depot_id})</span>
                            <span class="ar-status-pill {pill_cls}">{ds.state}</span>
                        </div>
                        <div class="ar-drone-meta">
                            Target: <strong>{target_lbl}</strong> | ETA: {ds.eta_min:.1f} mnt | Re-route: {ds.reroute_count}x
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.progress(
                    int(round(bat_pct)),
                    text=f"Baterai {bat_pct:.1f}% ({ds.remaining_battery_wh:.0f}/{ds.max_battery_wh:.0f} Wh) | Muatan {ds.current_payload_kg:.1f}/{ds.max_payload_kg:.1f} kg",
                )

        with tab_camps_status:
            camp_rows = [
                {
                    "Posko": c.name,
                    "Urgensi": c.urgency,
                    "Muatan": f"{c.demand_kg:.1f} kg",
                    "Batas": f"{c.time_window_end_min:.0f} mnt",
                    "Status": c.status,
                    "Tiba": f"{c.delivered_at_min:.1f} mnt" if c.delivered_at_min is not None else "-",
                }
                for c in sim.camps.values()
            ]
            st.dataframe(pd.DataFrame(camp_rows), hide_index=True, width="stretch", height=420)

        with tab_log:
            if not sim.events:
                st.info("Belum ada kejadian misi yang tercatat.")
            else:
                st.text_area(
                    "Log Kejadian Misi",
                    value="\n".join(reversed(sim.events[-20:])),
                    height=380,
                    label_visibility="collapsed",
                )


render_simulation_viewport()
