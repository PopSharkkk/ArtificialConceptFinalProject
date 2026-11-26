"""
AeroRelief 2.5D Interactive Simulator Dashboard (Streamlit)
Implements PRD.md:
- Custom Grid up to 100x100 with consistent horizontal & 10m-step elevation scaling
- Multi-Depot VRPTW-BL Genetic Algorithm (Battery, Payload, Time Windows, Urgency)
- Dynamic Obstacles: Moving Weather Storm Cell & Spreading Wildfire (Karhutla)
- Real-Time Animation, Live Hazard Injection, Event-Driven A* Re-routing & Telemetry
"""

from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Tuple

import matplotlib.patches as patches
import matplotlib.pyplot as plt
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
)

st.set_page_config(
    page_title="AeroRelief 2.5D Simulator — PRD Mockup",
    layout="wide",
    page_icon="🚁",
)

DRONE_COLORS = ["#1d4ed8", "#059669", "#7c3aed", "#db2777", "#0891b2", "#ca8a04"]
URGENCY_COLORS = {
    "CRITICAL": "#dc2626",
    "HIGH": "#ea580c",
    "NORMAL": "#2563eb",
}


@st.cache_data(show_spinner="Menghitung matriks jalur A* 2.5D & optimasi armada GA...")
def solve_initial_plan(
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

    for d in depots:
        env.static_obstacles[d.position[1], d.position[0]] = False
        env.elevation_grid[d.position[1], d.position[0]] = min(env.elevation_grid[d.position[1], d.position[0]], max_altitude_m - 20.0)
    for c in camps:
        env.static_obstacles[c.position[1], c.position[0]] = False
        env.elevation_grid[c.position[1], c.position[0]] = min(env.elevation_grid[c.position[1], c.position[0]], max_altitude_m - 10.0)
        for f in env.wildfires:
            f.active_fire_cells.discard(c.position)

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

    points: Dict[str, Tuple[int, int]] = {f"D{d.id}": d.position for d in depots}
    for c in camps:
        points[f"C{c.id}"] = c.position

    t0 = time.perf_counter()
    cost_matrix, dist_matrix, paths = compute_route_matrix(
        env, points, climb_penalty=climb_penalty, descent_penalty=0.4
    )
    t_matrix_ms = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    ga = MultiDepotVRPTWGA(
        env=env,
        depots=depots,
        camps=camps,
        drones=drones,
        cost_matrix=cost_matrix,
        dist_matrix=dist_matrix,
        paths=paths,
        pop_size=pop_size,
        generations=generations,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
    )
    routes, ga_metrics = ga.run()
    t_ga_ms = (time.perf_counter() - t1) * 1000.0

    return {
        "env": env,
        "depots": depots,
        "camps": camps,
        "drones": drones,
        "routes": routes,
        "paths": paths,
        "ga_metrics": ga_metrics,
        "t_matrix_ms": t_matrix_ms,
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


def render_map_figure(sim: AeroReliefSimulator) -> plt.Figure:
    env = sim.env
    fig, ax = plt.subplots(figsize=(8.6, 7.6), dpi=130)

    # 2.5D Elevation Heatmap + Contours
    im = ax.imshow(
        env.elevation_grid,
        origin="lower",
        cmap="YlGn",
        alpha=0.55,
        vmin=0.0,
        vmax=max(160.0, float(env.elevation_grid.max())),
        extent=[-0.5, env.width - 0.5, -0.5, env.height - 0.5],
    )
    if float(env.elevation_grid.max()) > 10.0:
        ax.contour(
            np.arange(env.width),
            np.arange(env.height),
            env.elevation_grid,
            levels=6,
            colors="#15803d",
            alpha=0.35,
            linewidths=0.7,
        )
    cbar = fig.colorbar(im, ax=ax, fraction=0.036, pad=0.02)
    cbar.set_label("Elevasi Medan (m)", fontsize=9)

    # Static No-Fly Zones
    nfz_y, nfz_x = np.where(env.static_obstacles)
    if len(nfz_x) > 0:
        ax.scatter(nfz_x, nfz_y, marker="s", s=38, color="#475569", alpha=0.85, label="No-Fly Zone Statis")

    # Exceeding ceiling zones
    ceil_y, ceil_x = np.where(env.elevation_grid > env.max_altitude_m)
    if len(ceil_x) > 0:
        ax.scatter(ceil_x, ceil_y, marker="^", s=26, color="#78350f", alpha=0.75, label="Elevasi > Plafon")

    # Wildfire / Karhutla cells
    burned_x, burned_y, fire_x, fire_y = [], [], [], []
    for f in env.wildfires:
        if not f.active:
            continue
        for cx, cy in f.burned_cells:
            burned_x.append(cx)
            burned_y.append(cy)
        for cx, cy in f.active_fire_cells:
            fire_x.append(cx)
            fire_y.append(cy)
    if burned_x:
        ax.scatter(burned_x, burned_y, marker="s", s=34, color="#64748b", alpha=0.6, label="Karhutla (Hangus/Asap)")
    if fire_x:
        ax.scatter(fire_x, fire_y, marker="s", s=42, color="#f97316", edgecolors="#b91c1c", linewidths=0.7, alpha=0.92, label="Karhutla (Api Aktif)")

    # Moving Weather Storm Cells
    for idx, storm in enumerate(env.storms):
        if not storm.active:
            continue
        turb_circle = patches.Circle(
            storm.center,
            storm.turbulence_radius,
            edgecolor="#2563eb",
            facecolor="#60a5fa",
            alpha=0.18,
            linestyle="--",
            linewidth=1.5,
            label="Turbulensi Cuaca" if idx == 0 else "",
        )
        core_circle = patches.Circle(
            storm.center,
            storm.core_radius,
            edgecolor="#1e3a8a",
            facecolor="#1d4ed8",
            alpha=0.45,
            linewidth=1.8,
            label="Inti Cuaca Buruk" if idx == 0 else "",
        )
        ax.add_patch(turb_circle)
        ax.add_patch(core_circle)
        ax.annotate(
            "",
            xy=(storm.center[0] + storm.velocity[0] * 4.0, storm.center[1] + storm.velocity[1] * 4.0),
            xytext=storm.center,
            arrowprops=dict(arrowstyle="->", color="#1e3a8a", lw=2.0),
        )

    # Wind Direction Indicator (top-left)
    wx, wy, w_spd = env.wind_vector
    wn = math.hypot(wx, wy)
    if wn > 1e-6:
        ux, uy = wx / wn, wy / wn
        ox, oy = env.width * 0.08, env.height * 0.92
        ax.annotate(
            f"Angin {w_spd:.0f} m/s",
            xy=(ox + ux * env.width * 0.08, oy + uy * env.height * 0.08),
            xytext=(ox, oy),
            arrowprops=dict(arrowstyle="->", color="#0f172a", lw=2.0),
            fontsize=8,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#cbd5e1", alpha=0.85),
        )

    # Planned vs Flown Trails + Drones
    for did, ds in sim.drone_states.items():
        col = DRONE_COLORS[(did - 1) % len(DRONE_COLORS)]
        if ds.planned_full_path:
            px = [p[0] for p in ds.planned_full_path]
            py = [p[1] for p in ds.planned_full_path]
            ax.plot(px, py, linestyle=":", linewidth=1.3, color=col, alpha=0.45)

        if ds.active_waypoints and ds.waypoint_idx < len(ds.active_waypoints):
            rem = ds.active_waypoints[ds.waypoint_idx :]
            ax.plot([p[0] for p in rem], [p[1] for p in rem], linestyle="--", linewidth=1.8, color=col, alpha=0.75)

        if len(ds.trail) >= 2:
            tx = [p[0] for p in ds.trail]
            ty = [p[1] for p in ds.trail]
            ax.plot(tx, ty, linestyle="-", linewidth=2.5, color=col, label=f"Drone #{did} ({ds.state})")

        # Drone Marker
        is_dead = ds.state == "Out of Battery"
        is_holding = ds.state in ("Stay at Depot", "Stay at Posko")
        marker_shape = "X" if is_dead else ("s" if is_holding else "^")
        marker_col = "#dc2626" if is_dead else ("#d97706" if is_holding else col)
        badge_lbl = f"D{did} [0%]" if is_dead else (f"D{did} [STAY]" if is_holding else f"D{did}")
        ax.scatter(
            [ds.current_pos[0]],
            [ds.current_pos[1]],
            marker=marker_shape,
            s=165 if is_dead else 140,
            color=marker_col,
            edgecolors="white",
            linewidths=1.4,
            zorder=8,
        )
        ax.text(
            ds.current_pos[0],
            ds.current_pos[1] - max(1.2, env.height * 0.032),
            badge_lbl,
            fontsize=8,
            fontweight="bold",
            color="white",
            ha="center",
            bbox=dict(boxstyle="round,pad=0.18", fc=marker_col, ec="none", alpha=0.9),
            zorder=9,
        )

    # Depots
    for d in sim.depots.values():
        ax.scatter(
            [d.position[0]],
            [d.position[1]],
            marker="s",
            s=150,
            color="#0f172a",
            edgecolors="#facc15",
            linewidths=1.8,
            zorder=7,
        )
        ax.text(
            d.position[0],
            d.position[1] - max(1.3, env.height * 0.035),
            d.name,
            fontsize=8,
            fontweight="bold",
            ha="center",
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="#0f172a", alpha=0.85),
            zorder=7,
        )

    # Camps
    for c in sim.camps.values():
        uc = URGENCY_COLORS.get(c.urgency, "#2563eb")
        if c.status.startswith("Delivered"):
            marker_face = "#16a34a"
        elif c.status == "Unreachable":
            marker_face = "#6b7280"
        else:
            marker_face = uc
        ax.scatter(
            [c.position[0]],
            [c.position[1]],
            marker="o",
            s=95,
            color=marker_face,
            edgecolors="white",
            linewidths=1.3,
            zorder=6,
        )
        ax.text(
            c.position[0],
            c.position[1] + max(0.9, env.height * 0.024),
            f"P{c.id} [{c.urgency[0]}]",
            fontsize=8,
            fontweight="bold",
            ha="center",
            color="#0f172a",
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec=marker_face, alpha=0.8),
            zorder=6,
        )

    ax.set_xlim(-0.5, env.width - 0.5)
    ax.set_ylim(-0.5, env.height - 0.5)
    ax.set_xlabel(f"Koordinat X ({env.cell_size_m:.0f} m/petak — Lebar {env.width * env.cell_size_m / 1000:.1f} km)")
    ax.set_ylabel(f"Koordinat Y ({env.cell_size_m:.0f} m/petak — Tinggi {env.height * env.cell_size_m / 1000:.1f} km)")
    ax.set_title(f"Peta Operasi 2.5D AeroRelief | Waktu Simulasi t = {sim.sim_time_min:.1f} menit", fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(loc="upper right", fontsize=7.5, framealpha=0.9)
    plt.tight_layout()
    return fig


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
        for d in sim.depots.values():
            fire.active_fire_cells.discard(d.position)
        for c in sim.camps.values():
            fire.active_fire_cells.discard(c.position)
        sim.env.add_wildfire(fire)
        sim.events.append(f"[t={sim.sim_time_min:.1f}m] INJEKSI: Titik Api Karhutla baru muncul di {label}!")

    # Immediately run re-routing check so the user sees instant response even when paused
    for did, ds in sim.drone_states.items():
        if ds.state not in ("Standby", "Completed", "Out of Battery"):
            sim._check_and_reroute(ds, sim.drones_cfg[did])


# ==============================================================================
# UI HEADER & SIDEBAR CONFIGURATION
# ==============================================================================
st.title("🚁 AeroRelief 2.5D: Emergency Medical Drone Logistics Simulator")
st.caption("Implementasi PRD.md — A* 2.5D + Multi-Depot VRPTW-BL Genetic Algorithm + Dynamic Weather & Wildfire Re-routing")

with st.sidebar:
    st.header("1. Lingkungan & Skala 2.5D")
    if "terrain_seed" not in st.session_state:
        st.session_state.terrain_seed = 42

    grid_size = st.slider("Ukuran Grid (N × N, maks 100)", min_value=20, max_value=100, value=50, step=10)
    cell_scale_label = st.selectbox(
        "Skala Horizontal per Petak",
        options=["100 m/petak", "200 m/petak", "500 m/petak", "1000 m/petak (1 km)"],
        index=1,
    )
    cell_size_m = float(cell_scale_label.split()[0])
    max_altitude_m = st.slider("Plafon Terbang Maksimum (m)", min_value=80, max_value=250, value=160, step=10)

    if st.button("🎲 Acak Peta Perlin Noise", width="stretch"):
        st.session_state.terrain_seed = random.randint(1, 99999)
        st.rerun()
    terrain_seed = int(st.session_state.terrain_seed)
    st.caption(f"Peta Elevasi Perlin Noise (kelipatan 10 m) — Seed #{terrain_seed}")

    c_w1, c_w2, c_w3 = st.columns(3)
    wind_dx = c_w1.number_input("Angin dX", value=1.0, step=0.2, format="%.1f")
    wind_dy = c_w2.number_input("Angin dY", value=0.4, step=0.2, format="%.1f")
    wind_speed = c_w3.number_input("Laju (m/s)", min_value=0.0, max_value=25.0, value=9.0, step=1.0)

    st.header("2. Dynamic Obstacles Awal")
    storm_on = st.checkbox("Aktifkan Cuaca Buruk Bergerak", value=True)
    storm_pen = st.slider("Penalti Turbulensi Badai", 1.2, 3.0, 1.85, 0.05) if storm_on else 1.85
    fire_on = st.checkbox("Aktifkan Daerah Api / Karhutla", value=True)
    if fire_on:
        fire_prob = st.slider("Laju Rambat Api Karhutla", 0.10, 0.60, 0.28, 0.02)
        fire_max_cells = st.slider("Batas Maksimum Area Api (petak)", 8, 40, 18, 2)
        fire_dir_choice = st.selectbox("Arah Gerak Api Karhutla", ["Kanan (+X)", "Kiri (-X)", "Ikuti Angin"], index=0)
    else:
        fire_prob, fire_max_cells, fire_dir_choice = 0.28, 18, "Kanan (+X)"

    st.header("3. Armada Drone & Parameter GA")
    num_drones = st.slider("Jumlah Armada Drone", min_value=1, max_value=6, value=3)
    max_battery_wh = st.slider("Kapasitas Baterai (Wh)", min_value=40, max_value=800, value=350, step=10)
    max_payload_kg = st.slider("Muatan Maksimal / Drone (kg)", min_value=2.0, max_value=15.0, value=8.0, step=0.5)
    speed_mps = st.slider("Kecepatan Jelajah Drone (m/s)", min_value=8.0, max_value=30.0, value=18.0, step=1.0)
    climb_penalty = st.slider("Bobot Penalti Menanjak (A*)", min_value=0.5, max_value=5.0, value=2.5, step=0.25)

    pop_size = st.slider("Populasi GA", 20, 120, 50, 10)
    generations = st.slider("Generasi GA", 20, 150, 70, 10)
    alpha = st.number_input("Bobot α (Jarak/Energi)", value=1.0, min_value=0.1, step=0.5)
    beta = st.number_input("Bobot β (Keterlambatan)", value=2.5, min_value=0.1, step=0.5)
    gamma = st.number_input("Bobot γ (Pelanggaran Kapasitas)", value=15.0, min_value=1.0, step=1.0)


# Interactive Editor for Depots and Camps (Static NFZ disabled per user request)
def _sx(frac: float) -> int:
    return max(1, min(grid_size - 2, int(round(frac * (grid_size - 1)))))


def _sy(frac: float) -> int:
    return max(1, min(grid_size - 2, int(round(frac * (grid_size - 1)))))


with st.expander("🗺️ Editor Peta Interaktif: Multi-Depot & Posko (Urgensi & Time Window)", expanded=False):
    tab_depots, tab_camps = st.tabs(["Depot / Basecamp", "Posko Bencana"])

    default_depots_df = pd.DataFrame(
        [
            {"id": 1, "nama": "Depot Barat", "x": _sx(0.08), "y": _sy(0.10)},
            {"id": 2, "nama": "Depot Timur", "x": _sx(0.90), "y": _sy(0.14)},
        ]
    )
    default_camps_df = pd.DataFrame(
        [
            {"id": 1, "nama": "Posko 1", "x": _sx(0.18), "y": _sy(0.76), "demand_kg": 2.5, "urgency": "CRITICAL", "time_window_min": 14.0},
            {"id": 2, "nama": "Posko 2", "x": _sx(0.42), "y": _sy(0.84), "demand_kg": 2.0, "urgency": "HIGH", "time_window_min": 22.0},
            {"id": 3, "nama": "Posko 3", "x": _sx(0.82), "y": _sy(0.82), "demand_kg": 2.5, "urgency": "CRITICAL", "time_window_min": 16.0},
            {"id": 4, "nama": "Posko 4", "x": _sx(0.14), "y": _sy(0.44), "demand_kg": 1.5, "urgency": "NORMAL", "time_window_min": 30.0},
            {"id": 5, "nama": "Posko 5", "x": _sx(0.56), "y": _sy(0.18), "demand_kg": 2.0, "urgency": "HIGH", "time_window_min": 20.0},
            {"id": 6, "nama": "Posko 6", "x": _sx(0.78), "y": _sy(0.56), "demand_kg": 2.0, "urgency": "HIGH", "time_window_min": 24.0},
            {"id": 7, "nama": "Posko 7", "x": _sx(0.32), "y": _sy(0.24), "demand_kg": 1.5, "urgency": "NORMAL", "time_window_min": 28.0},
            {"id": 8, "nama": "Posko 8", "x": _sx(0.62), "y": _sy(0.72), "demand_kg": 2.5, "urgency": "CRITICAL", "time_window_min": 18.0},
        ]
    )

    with tab_depots:
        depots_df = st.data_editor(default_depots_df, num_rows="dynamic", key=f"depots_ed_{grid_size}", width="stretch")
    with tab_camps:
        camps_df = st.data_editor(
            default_camps_df,
            num_rows="dynamic",
            key=f"camps_ed_{grid_size}",
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
    depots_tuple = ((1, "Depot Default", _sx(0.1), _sy(0.1)),)

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

storm_cfg = (storm_on, float(_sx(0.22)), float(_sy(0.32)), max(2.0, grid_size * 0.055), max(4.0, grid_size * 0.11), storm_pen)
fire_cfg = (fire_on, _sx(0.64), _sy(0.46), fire_prob, fire_max_cells, fire_move_dir)

plan_key = (
    grid_size, grid_size, cell_size_m, max_altitude_m, terrain_seed,
    wind_dx, wind_dy, wind_speed, depots_tuple, camps_tuple, nfz_tuple,
    storm_cfg, fire_cfg, num_drones, max_battery_wh, max_payload_kg,
    speed_mps, climb_penalty, pop_size, generations, alpha, beta, gamma,
)

plan = solve_initial_plan(*plan_key)

if st.session_state.get("plan_key") != plan_key or "sim" not in st.session_state:
    st.session_state.plan_key = plan_key
    st.session_state.sim = clone_simulator_from_plan(plan)
    st.session_state.playing = False

sim: AeroReliefSimulator = st.session_state.sim

# ==============================================================================
# SIMULATION CONTROLS & KPI BAR
# ==============================================================================
ctrl_cols = st.columns([1.1, 1.0, 1.1, 1.1, 1.6, 1.8])
if ctrl_cols[0].button("▶️ Play" if not st.session_state.playing else "⏸️ Pause", width="stretch"):
    st.session_state.playing = not st.session_state.playing
    st.rerun()
if ctrl_cols[1].button("⏭️ +1 Tick", width="stretch"):
    st.session_state.playing = False
    sim.step(dt_min=0.5)
if ctrl_cols[2].button("⏩ +5 Ticks", width="stretch"):
    st.session_state.playing = False
    for _ in range(5):
        sim.step(dt_min=0.5)
if ctrl_cols[3].button("🔄 Reset", width="stretch"):
    st.session_state.playing = False
    st.session_state.sim = clone_simulator_from_plan(plan)
    st.rerun()
if ctrl_cols[4].button("⛈️ Suntik Badai di Jalur", width="stretch"):
    inject_hazard_ahead_of_drone(sim, "storm")
if ctrl_cols[5].button("🔥 Suntik Api Karhutla di Jalur", width="stretch"):
    inject_hazard_ahead_of_drone(sim, "fire")

# KPI Cards
delivered_on_time = sum(1 for c in sim.camps.values() if c.status == "Delivered On-Time")
delivered_late = sum(1 for c in sim.camps.values() if c.status == "Delivered Late")
total_reroutes = sum(ds.reroute_count for ds in sim.drone_states.values())

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Waktu Simulasi", f"{sim.sim_time_min:.1f} mnt")
k2.metric("Terkirim (On-Time / Late)", f"{delivered_on_time} / {delivered_late}", f"dari {len(sim.camps)} posko")
k3.metric("Estimasi Jarak Awal GA", f"{plan['ga_metrics']['total_dist_km']:.2f} km")
k4.metric("Re-routing A* Terpicu", f"{total_reroutes}×")
k5.metric("Komputasi Awal (A* / GA)", f"{plan['t_matrix_ms']:.0f} / {plan['t_ga_ms']:.0f} ms")

# ==============================================================================
# MAIN LAYOUT: MAP (LEFT) & TELEMETRY (RIGHT)
# ==============================================================================
col_map, col_tel = st.columns([1.45, 1.0])

with col_map:
    fig = render_map_figure(sim)
    st.pyplot(fig, width="stretch")
    plt.close(fig)

with col_tel:
    st.subheader("📡 Telemetri Armada Drone")
    for did, ds in sim.drone_states.items():
        bat_pct = ds.remaining_battery_pct
        target_lbl = ds.current_target_key or "Selesai / Standby"
        with st.container(border=True):
            c_a, c_b = st.columns([2, 1])
            c_a.markdown(f"**Drone #{did}** — `{ds.state}` (Depot {ds.home_depot_id})")
            c_b.markdown(f"Target: **{target_lbl}** | ETA: **{ds.eta_min:.1f} mnt**")
            st.progress(int(round(bat_pct)), text=f"Baterai: {bat_pct:.1f}% ({ds.remaining_battery_wh:.0f}/{ds.max_battery_wh:.0f} Wh) | Muatan: {ds.current_payload_kg:.1f}/{ds.max_payload_kg:.1f} kg | Re-route: {ds.reroute_count}×")

    st.subheader("🏥 Status Pengiriman Posko")
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
    st.dataframe(pd.DataFrame(camp_rows), hide_index=True, width="stretch")

    st.subheader("📜 Log Kejadian Misi")
    st.text_area(
        "Event Log",
        value="\n".join(reversed(sim.events[-12:])),
        height=160,
        label_visibility="collapsed",
    )

# Auto-step loop when playing
if st.session_state.playing:
    if sim.is_finished():
        st.session_state.playing = False
    else:
        sim.step(dt_min=0.5)
        time.sleep(0.18)
        st.rerun()
