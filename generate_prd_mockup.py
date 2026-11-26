"""
Generate high-resolution PNG and animated GIF mockups of AeroRelief 2.5D
matching PRD.md for PPT progress & documentation.
Outputs:
- mockup_prd_dashboard.png
- mockup_prd_animation.gif
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import List

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from aerorelief_engine import (
    AeroReliefSimulator,
    MultiDepotVRPTWGA,
    WeatherStormCell,
    WildfireHazard,
    compute_route_matrix,
    create_default_scenario,
)

DRONE_COLORS = ["#1d4ed8", "#059669", "#7c3aed"]
URGENCY_COLORS = {"CRITICAL": "#dc2626", "HIGH": "#ea580c", "NORMAL": "#2563eb"}


def build_prd_demo_simulator() -> tuple[AeroReliefSimulator, dict, float, float]:
    env, depots, camps, drones = create_default_scenario(
        width=60,
        height=60,
        cell_size_m=200.0,
        terrain_seed=42,
        num_drones=3,
        wind_vector=(1.0, 0.45, 10.0),
    )
    points = {f"D{d.id}": d.position for d in depots}
    for c in camps:
        points[f"C{c.id}"] = c.position

    import time
    t0 = time.perf_counter()
    cost_matrix, dist_matrix, paths = compute_route_matrix(env, points, climb_penalty=2.5, descent_penalty=0.4)
    t_mat = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    ga = MultiDepotVRPTWGA(
        env=env,
        depots=depots,
        camps=camps,
        drones=drones,
        cost_matrix=cost_matrix,
        dist_matrix=dist_matrix,
        paths=paths,
        pop_size=50,
        generations=70,
    )
    routes, metrics = ga.run()
    t_ga = (time.perf_counter() - t1) * 1000.0

    sim = AeroReliefSimulator(env, depots, camps, drones, routes, paths, seed=7)
    return sim, metrics, t_mat, t_ga


def draw_dashboard_frame(sim: AeroReliefSimulator, t_mat_ms: float, t_ga_ms: float, out_path: Path | None = None) -> Image.Image:
    env = sim.env
    fig = plt.figure(figsize=(15.5, 8.8), dpi=130, facecolor="#f8fafc")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.55, 1.0], wspace=0.14, left=0.05, right=0.97, top=0.90, bottom=0.08)

    fig.suptitle(
        "AeroRelief 2.5D — Simulasi Rute Multi-Drone Pasca Bencana (Sesuai PRD.md)",
        fontsize=16,
        fontweight="bold",
        color="#0f172a",
        y=0.96,
    )

    ax = fig.add_subplot(gs[0, 0])
    im = ax.imshow(
        env.elevation_grid,
        origin="lower",
        cmap="YlGn",
        alpha=0.58,
        vmin=0.0,
        vmax=max(160.0, float(env.elevation_grid.max())),
        extent=[-0.5, env.width - 0.5, -0.5, env.height - 0.5],
    )
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
    cbar.set_label("Elevasi Medan 2.5D (meter)", fontsize=9)

    # Static NFZ
    nfz_y, nfz_x = np.where(env.static_obstacles)
    if len(nfz_x) > 0:
        ax.scatter(nfz_x, nfz_y, marker="s", s=34, color="#475569", alpha=0.85, label="No-Fly Zone Statis")

    # Wildfire / Karhutla
    bx, by, fx, fy = [], [], [], []
    for f in env.wildfires:
        for cx, cy in f.burned_cells:
            bx.append(cx); by.append(cy)
        for cx, cy in f.active_fire_cells:
            fx.append(cx); fy.append(cy)
    if bx:
        ax.scatter(bx, by, marker="s", s=30, color="#64748b", alpha=0.58, label="Karhutla (Hangus/Asap)")
    if fx:
        ax.scatter(fx, fy, marker="s", s=40, color="#f97316", edgecolors="#b91c1c", linewidths=0.7, alpha=0.94, label="Karhutla (Api Aktif)")

    # Storm Cells
    for idx, storm in enumerate(env.storms):
        if not storm.active:
            continue
        ax.add_patch(
            patches.Circle(
                storm.center, storm.turbulence_radius,
                edgecolor="#2563eb", facecolor="#60a5fa", alpha=0.18, linestyle="--", lw=1.5,
                label="Turbulensi Cuaca" if idx == 0 else "",
            )
        )
        ax.add_patch(
            patches.Circle(
                storm.center, storm.core_radius,
                edgecolor="#1e3a8a", facecolor="#1d4ed8", alpha=0.45, lw=1.8,
                label="Inti Cuaca Buruk" if idx == 0 else "",
            )
        )
        ax.annotate(
            "",
            xy=(storm.center[0] + storm.velocity[0] * 5.0, storm.center[1] + storm.velocity[1] * 5.0),
            xytext=storm.center,
            arrowprops=dict(arrowstyle="->", color="#1e3a8a", lw=2.0),
        )

    # Wind box
    wx, wy, wspd = env.wind_vector
    wn = math.hypot(wx, wy)
    if wn > 1e-6:
        ux, uy = wx / wn, wy / wn
        ox, oy = env.width * 0.04, env.height * 0.93
        ax.text(
            ox, oy,
            f"Angin ({wspd:.0f} m/s)",
            fontsize=8.5,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#94a3b8", alpha=0.92),
        )
        ax.annotate(
            "",
            xy=(ox + ux * 5.0, oy - 3.2 + uy * 3.0),
            xytext=(ox, oy - 3.2),
            arrowprops=dict(arrowstyle="->", color="#0f172a", lw=2.2),
        )

    # Drone routes & current positions
    for did, ds in sim.drone_states.items():
        col = DRONE_COLORS[(did - 1) % len(DRONE_COLORS)]
        if ds.planned_full_path:
            ax.plot([p[0] for p in ds.planned_full_path], [p[1] for p in ds.planned_full_path], ":", lw=1.2, color=col, alpha=0.4)
        if ds.active_waypoints and ds.waypoint_idx < len(ds.active_waypoints):
            rem = ds.active_waypoints[ds.waypoint_idx :]
            ax.plot([p[0] for p in rem], [p[1] for p in rem], "--", lw=1.8, color=col, alpha=0.8)
        if len(ds.trail) >= 2:
            ax.plot([p[0] for p in ds.trail], [p[1] for p in ds.trail], "-", lw=2.6, color=col, label=f"Drone #{did} ({ds.state})")
        is_dead = ds.state == "Out of Battery"
        is_holding = ds.state in ("Stay at Depot", "Stay at Posko")
        marker_shape = "X" if is_dead else ("s" if is_holding else "^")
        badge_col = "#dc2626" if is_dead else ("#d97706" if is_holding else col)
        badge_lbl = f"D{did} [0%]" if is_dead else (f"D{did} [STAY]" if is_holding else f"D{did}")
        ax.scatter(
            [ds.current_pos[0]],
            [ds.current_pos[1]],
            marker=marker_shape,
            s=165 if is_dead else 145,
            color=badge_col,
            edgecolors="white",
            lw=1.5,
            zorder=8,
        )
        ax.text(
            ds.current_pos[0], ds.current_pos[1] - 2.2, badge_lbl,
            fontsize=8, fontweight="bold", color="white", ha="center",
            bbox=dict(boxstyle="round,pad=0.18", fc=badge_col, ec="none"), zorder=9,
        )

    # Depots & Camps
    for d in sim.depots.values():
        ax.scatter([d.position[0]], [d.position[1]], marker="s", s=140, color="#0f172a", edgecolors="#facc15", lw=1.8, zorder=7)
        ax.text(
            d.position[0], d.position[1] - 2.5, d.name,
            fontsize=8, fontweight="bold", ha="center",
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="#0f172a", alpha=0.9), zorder=7,
        )
    for c in sim.camps.values():
        fc = "#16a34a" if c.status.startswith("Delivered") else ("#6b7280" if c.status == "Unreachable" else URGENCY_COLORS[c.urgency])
        ax.scatter([c.position[0]], [c.position[1]], marker="o", s=90, color=fc, edgecolors="white", lw=1.3, zorder=6)
        ax.text(
            c.position[0], c.position[1] + 1.4, f"P{c.id} [{c.urgency[0]}]",
            fontsize=7.8, fontweight="bold", ha="center",
            bbox=dict(boxstyle="round,pad=0.14", fc="white", ec=fc, alpha=0.85), zorder=6,
        )

    ax.set_xlim(-0.5, env.width - 0.5)
    ax.set_ylim(-0.5, env.height - 0.5)
    ax.set_xlabel(f"Koordinat X ({env.cell_size_m:.0f} m/petak — Area {env.width * env.cell_size_m / 1000:.1f}×{env.height * env.cell_size_m / 1000:.1f} km)", fontsize=9.5)
    ax.set_ylabel("Koordinat Y (grid)", fontsize=9.5)
    ax.set_title(f"Peta Operasi 2.5D Real-Time | Simulasi t = {sim.sim_time_min:.1f} menit", fontsize=11.5, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(loc="upper right", fontsize=7.5, framealpha=0.92)

    # Right Side: Telemetry & Status Panel
    ax_tel = fig.add_subplot(gs[0, 1])
    ax_tel.set_axis_off()
    ax_tel.set_xlim(-0.025, 1.025)
    ax_tel.set_ylim(-0.025, 1.015)

    delivered_ok = sum(1 for c in sim.camps.values() if c.status == "Delivered On-Time")
    delivered_late = sum(1 for c in sim.camps.values() if c.status == "Delivered Late")
    reroutes = sum(ds.reroute_count for ds in sim.drone_states.values())

    # Top KPI box
    ax_tel.add_patch(patches.FancyBboxPatch((0.0, 0.87), 1.0, 0.12, boxstyle="round,pad=0.012", fc="#ffffff", ec="#cbd5e1", lw=1.2))
    ax_tel.text(0.03, 0.96, "RINGKASAN MISI & PERFORMA ALGORITMA", fontsize=10, fontweight="bold", color="#0f172a")
    ax_tel.text(
        0.03, 0.895,
        f"Terkirim: {delivered_ok} On-Time, {delivered_late} Late / {len(sim.camps)} Posko   |   "
        f"Re-route A*: {reroutes}x\nMatriks A* 2.5D: {t_mat_ms:.0f} ms   |   GA Multi-Depot: {t_ga_ms:.0f} ms",
        fontsize=8.7, color="#334155", linespacing=1.45,
    )

    # Drone Telemetry Cards
    ax_tel.text(0.0, 0.835, "TELEMETRI ARMADA DRONE", fontsize=10, fontweight="bold", color="#0f172a")
    y_top = 0.735
    for did, ds in sim.drone_states.items():
        col = DRONE_COLORS[(did - 1) % len(DRONE_COLORS)]
        ax_tel.add_patch(patches.FancyBboxPatch((0.0, y_top), 1.0, 0.08, boxstyle="round,pad=0.010", fc="#ffffff", ec=col, lw=1.5))
        tgt = ds.current_target_key or "Selesai"
        ax_tel.text(
            0.03, y_top + 0.052,
            f"Drone #{did} (Depot {ds.home_depot_id}) — [{ds.state}]   |   Target: {tgt}   |   ETA: {ds.eta_min:.1f} mnt",
            fontsize=8.6, fontweight="bold", color="#0f172a",
        )
        ax_tel.text(
            0.03, y_top + 0.017,
            f"Baterai: {ds.remaining_battery_pct:.1f}% ({ds.remaining_battery_wh:.0f} Wh)   |   Muatan: {ds.current_payload_kg:.1f}/{ds.max_payload_kg:.1f} kg   |   Re-route: {ds.reroute_count}x",
            fontsize=8.2, color="#475569",
        )
        y_top -= 0.102

    # Camp Status Table
    ax_tel.text(0.0, 0.44, "STATUS POSKO PENERIMA LOGISTIK", fontsize=10, fontweight="bold", color="#0f172a")
    ax_tel.add_patch(patches.FancyBboxPatch((0.0, 0.195), 1.0, 0.225, boxstyle="round,pad=0.010", fc="#ffffff", ec="#cbd5e1", lw=1.2))
    cy = 0.395
    for c in sim.camps.values():
        sc = "#16a34a" if c.status == "Delivered On-Time" else ("#dc2626" if c.status in ("Delivered Late", "Unreachable") else "#334155")
        ax_tel.text(0.025, cy, f"{c.name:<18} | {c.urgency:<8} | {c.demand_kg:.1f} kg | Batas {c.time_window_end_min:.0f}m", fontsize=7.9, family="monospace", color="#1e293b")
        ax_tel.text(0.73, cy, c.status, fontsize=7.9, fontweight="bold", color=sc)
        cy -= 0.026

    # Event Log
    ax_tel.text(0.0, 0.148, "LOG KEJADIAN DINAMIS (CUACA & KARHUTLA)", fontsize=10, fontweight="bold", color="#0f172a")
    ax_tel.add_patch(patches.FancyBboxPatch((0.0, 0.005), 1.0, 0.125, boxstyle="round,pad=0.010", fc="#0f172a", ec="#334155", lw=1.2))
    recent_events = sim.events[-4:]
    ey = 0.095
    for ev in recent_events:
        ax_tel.text(0.025, ey, ev[:78], fontsize=7.6, family="monospace", color="#e2e8f0")
        ey -= 0.026

    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba())
    img = Image.fromarray(rgba).convert("RGB")
    if out_path is not None:
        img.save(out_path, dpi=(130, 130))
    plt.close(fig)
    return img


def main() -> None:
    sim, _, t_mat_ms, t_ga_ms = build_prd_demo_simulator()
    frames: List[Image.Image] = []
    snapshot_saved = False

    # Run 32 ticks (16.0 simulated minutes) capturing frames + injecting a storm/fire mid-flight
    for tick in range(32):
        if tick == 8:
            # Inject an extra fire hotspot ahead of Drone #1 or #2 if not yet rerouted
            for ds in sim.drone_states.values():
                if ds.active_waypoints and len(ds.active_waypoints) - ds.waypoint_idx > 5:
                    idx = ds.waypoint_idx + 4
                    fx, fy = ds.active_waypoints[idx]
                    fire = WildfireHazard(
                        id=2, name="Karhutla Susulan", base_spread_prob=0.30,
                        wind_bias=0.50, slope_bias=0.30, burn_duration_min=8.0, spread_interval_min=1.0,
                        max_active_cells=14, max_burned_cells=28, move_dir_x=-1.0,
                    )
                    fire.ignite_zone(fx - 1, fx + 1, fy - 1, fy + 1, sim.env.width, sim.env.height)
                    for d in sim.depots.values():
                        fire.active_fire_cells.discard(d.position)
                    for c in sim.camps.values():
                        fire.active_fire_cells.discard(c.position)
                    sim.env.add_wildfire(fire)
                    sim.events.append(f"[t={sim.sim_time_min:.1f}m] Titik Api Karhutla baru muncul di ({fx},{fy})!")
                    sim._check_and_reroute(ds, sim.drones_cfg[ds.drone_id])
                    break

        frame = draw_dashboard_frame(sim, t_mat_ms, t_ga_ms)
        frames.append(frame)

        if tick == 14:
            frame.save(Path("mockup_prd_dashboard.png"))
            snapshot_saved = True

        if sim.is_finished():
            break
        sim.step(dt_min=0.5)

    if not snapshot_saved and frames:
        frames[min(len(frames) - 1, len(frames) // 2)].save(Path("mockup_prd_dashboard.png"))

    if frames:
        frames[0].save(
            Path("mockup_prd_animation.gif"),
            save_all=True,
            append_images=frames[1:],
            duration=260,
            loop=0,
        )
    print(f"Generated mockup_prd_dashboard.png and mockup_prd_animation.gif ({len(frames)} frames).")


if __name__ == "__main__":
    main()
