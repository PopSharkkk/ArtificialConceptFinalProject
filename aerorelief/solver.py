"""Mission orchestration solver for AeroRelief Web API, Video Generator, and CLI."""

import json
import math
from typing import Any, Dict, List, Tuple
from .dynamic import simulate_dynamic_mission
from .environment import TopographicEnvironment
from .models import Camp, DynamicHazardEvent, HazardZone
from .pathfinding import (
    benchmark_pathfinding_algorithms,
    compute_distance_matrices,
)
from .routing import GeneticDroneOptimizer, SimulatedAnnealingOptimizer
from .scenarios import build_drone_fleet, get_scenario


def _build_timeline_frames(
    drone_schedules: List[Dict[str, Any]], total_duration_min: float, steps: int = 140
) -> List[Dict[str, Any]]:
    """Build sampled timeline keyframes for deterministic playback synchronization."""
    if total_duration_min <= 0:
        return []
    frames: List[Dict[str, Any]] = []
    for s in range(steps + 1):
        t = (s / steps) * total_duration_min
        drone_positions = []
        for ds in drone_schedules:
            pos = None
            state = "STANDBY"
            for seg in ds["segments"]:
                if seg["start_min"] <= t <= seg["end_min"] and seg["path"]:
                    span = max(seg["end_min"] - seg["start_min"], 1e-6)
                    frac = (t - seg["start_min"]) / span
                    path = seg["path"]
                    f_idx = frac * (len(path) - 1)
                    i0 = int(math.floor(f_idx))
                    i1 = min(i0 + 1, len(path) - 1)
                    alpha = f_idx - i0
                    x = path[i0][0] * (1 - alpha) + path[i1][0] * alpha
                    y = path[i0][1] * (1 - alpha) + path[i1][1] * alpha
                    pos = [round(x, 3), round(y, 3)]
                    state = "RELOAD" if seg["is_reload_trip"] else "TERBANG"
                    break
            if pos is None and ds["segments"]:
                if t >= ds["segments"][-1]["end_min"]:
                    last_pt = ds["segments"][-1]["path"][-1]
                    pos = [last_pt[0], last_pt[1]]
                    state = "SELESAI"
                else:
                    for seg in ds["segments"]:
                        if t < seg["start_min"] and seg["path"]:
                            pt = seg["path"][0]
                            pos = [pt[0], pt[1]]
                            state = "DROP-OFF"
                            break
            drone_positions.append({"drone_id": ds["drone_id"], "pos": pos, "state": state})
        frames.append({"t_min": round(t, 2), "drones": drone_positions})
    return frames


def _parse_injected_events(raw_events: List[Dict[str, Any]]) -> List[DynamicHazardEvent]:
    parsed: List[DynamicHazardEvent] = []
    for i, ev in enumerate(raw_events):
        cells = None
        if ev.get("cells"):
            cells = [(int(c[0]), int(c[1])) for c in ev["cells"]]
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
        else:
            x_min = int(ev.get("x_min", 0))
            x_max = int(ev.get("x_max", x_min))
            y_min = int(ev.get("y_min", 0))
            y_max = int(ev.get("y_max", y_min))

        expire_val = ev.get("expire_min")
        parsed.append(
            DynamicHazardEvent(
                id=str(ev.get("id", f"injected_{i + 1}")),
                name=str(ev.get("name", f"Rintangan Mendadak #{i + 1}")),
                trigger_min=float(ev.get("trigger_min", 10.0)),
                expire_min=float(expire_val) if expire_val is not None else None,
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                hazard_type=str(ev.get("hazard_type", "Rintangan Baru")),
                cells=cells,
            )
        )
    return parsed


def solve_mission(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Solve two-tier optimization plus dynamic mid-flight obstacle re-planning."""
    req = payload or {}
    scenario_id = str(req.get("scenario_id", "semeru"))
    scenario = get_scenario(scenario_id)

    if "custom_camps" in req and req["custom_camps"] is not None:
        camps: List[Camp] = []
        for idx, c in enumerate(req["custom_camps"]):
            camps.append(
                Camp(
                    id=int(c.get("id", idx + 1)),
                    name=str(c.get("name", f"Posko {idx + 1}")),
                    x=int(c["x"]),
                    y=int(c["y"]),
                    urgency=str(c.get("urgency", "TINGGI")),
                    demand_kg=float(c.get("demand_kg", 2.0)),
                    time_window_min=float(c.get("time_window_min", 45.0)),
                    supply_type=str(c.get("supply_type", "Logistik Medis")),
                )
            )
    else:
        camps = list(scenario.camps)

    depot = tuple(req.get("depot", scenario.depot))
    depot_coord = (int(depot[0]), int(depot[1]))

    if "custom_obstacles" in req and req["custom_obstacles"] is not None:
        hazard_zones: List[HazardZone] = []
        extra_obstacles: List[Tuple[int, int]] = [
            (int(p[0]), int(p[1])) for p in req["custom_obstacles"]
        ]
    else:
        hazard_zones = list(scenario.hazard_zones)
        extra_obstacles = []

    env = TopographicEnvironment(
        width=scenario.grid_width,
        height=scenario.grid_height,
        hills=scenario.hills,
        hazard_zones=hazard_zones,
        extra_obstacles=extra_obstacles,
    )

    if len(camps) == 0:
        return {
            "reachable": True,
            "empty": True,
            "scenario": scenario.to_dict(),
            "depot": list(depot_coord),
            "obstacles": [list(o) for o in sorted(env.obstacles)],
            "elevation": env.elevation,
            "camps": [],
            "dynamic": {"enabled": False, "events": [], "replan_log": [], "superseded_routes": []},
            "message": "Tidak ada posko penerima bantuan. Tambahkan posko pada peta atau muat ulang skenario.",
        }

    num_drones = int(req.get("num_drones", len(scenario.default_drones)))
    max_payload_kg = float(req.get("max_payload_kg", 5.0))
    max_battery_km = float(req.get("max_battery_km", 80.0))
    speed_kmh = float(req.get("speed_kmh", 72.0))
    drones = build_drone_fleet(num_drones, max_payload_kg, max_battery_km, speed_kmh)

    path_algorithm = str(req.get("path_algorithm", "astar")).lower()
    routing_algorithm = str(req.get("routing_algorithm", "ga")).lower()
    pop_size = int(req.get("pop_size", 50))
    generations = int(req.get("generations", 80))
    seed = int(req.get("seed", 42))
    enable_dynamic = bool(req.get("enable_dynamic_events", True))
    dynamic_intensity = str(req.get("dynamic_intensity", "high")).lower()
    if dynamic_intensity == "off":
        enable_dynamic = False
    injected_events = _parse_injected_events(req.get("injected_events") or [])

    matrices = compute_distance_matrices(env, depot_coord, camps, algorithm=path_algorithm)
    if matrices["depot_blocked"] or matrices["unreachable_camp_ids"]:
        blocked_names = [
            c.name for c in camps if c.id in matrices["unreachable_camp_ids"]
        ]
        msg = (
            "Base Depot tertutup zona terlarang."
            if matrices["depot_blocked"]
            else f"Posko terisolasi oleh zona terlarang dan tidak dapat dijangkau: {', '.join(blocked_names)}."
        )
        return {
            "reachable": False,
            "empty": False,
            "scenario": scenario.to_dict(),
            "depot": list(depot_coord),
            "obstacles": [list(o) for o in sorted(env.obstacles)],
            "elevation": env.elevation,
            "camps": [c.to_dict() for c in camps],
            "unreachable_camp_ids": matrices["unreachable_camp_ids"],
            "dynamic": {"enabled": enable_dynamic, "events": [], "replan_log": [], "superseded_routes": []},
            "message": msg,
        }

    path_benchmark = benchmark_pathfinding_algorithms(env, depot_coord, camps)

    ga_result = GeneticDroneOptimizer(
        camps=camps,
        drones=drones,
        cost_matrix=matrices["cost_matrix"],
        dist_matrix=matrices["dist_matrix"],
        path_matrix=matrices["path_matrix"],
        pop_size=pop_size,
        generations=generations,
        seed=seed,
    ).run()

    sa_result = SimulatedAnnealingOptimizer(
        camps=camps,
        drones=drones,
        cost_matrix=matrices["cost_matrix"],
        dist_matrix=matrices["dist_matrix"],
        path_matrix=matrices["path_matrix"],
        generations=generations,
        seed=seed,
    ).run()

    active_routing = dict(sa_result if routing_algorithm == "sa" else ga_result)
    initial_eval = active_routing["evaluation"]
    initial_distance_km = initial_eval["total_distance_km"]

    all_dyn_events: List[DynamicHazardEvent] = []
    if enable_dynamic:
        if dynamic_intensity == "medium":
            all_dyn_events.extend(scenario.dynamic_events[:4])
        else:
            all_dyn_events.extend(scenario.dynamic_events)
    all_dyn_events.extend(injected_events)

    replan_log: List[Dict[str, Any]] = []
    superseded_routes: List[Dict[str, Any]] = []

    if all_dyn_events:
        dyn_sim = simulate_dynamic_mission(
            scenario=scenario,
            base_obstacles=env.obstacles,
            depot=depot_coord,
            camps=camps,
            drones=drones,
            initial_eval=initial_eval,
            dynamic_events=all_dyn_events,
            path_algorithm=path_algorithm,
        )
        if not dyn_sim["reachable"]:
            return {
                "reachable": False,
                "empty": False,
                "scenario": scenario.to_dict(),
                "depot": list(depot_coord),
                "obstacles": [list(o) for o in sorted(env.obstacles)],
                "elevation": env.elevation,
                "camps": [c.to_dict() for c in camps],
                "dynamic": {
                    "enabled": enable_dynamic,
                    "events": [e.to_dict() for e in all_dyn_events],
                    "replan_log": dyn_sim.get("replan_log", []),
                    "superseded_routes": dyn_sim.get("superseded_routes", []),
                },
                "message": dyn_sim["message"],
            }
        active_routing["evaluation"] = dyn_sim["evaluation"]
        replan_log = dyn_sim["replan_log"]
        superseded_routes = dyn_sim["superseded_routes"]

    eval_data = active_routing["evaluation"]
    makespan = eval_data["makespan_min"]
    timeline = _build_timeline_frames(eval_data["drone_schedules"], makespan, steps=140)

    return {
        "reachable": True,
        "empty": False,
        "scenario": scenario.to_dict(),
        "depot": list(depot_coord),
        "obstacles": [list(o) for o in sorted(env.obstacles)],
        "elevation": env.elevation,
        "camps": [c.to_dict() for c in camps],
        "drones": [d.to_dict() for d in drones],
        "config": {
            "path_algorithm": path_algorithm,
            "routing_algorithm": routing_algorithm,
            "num_drones": len(drones),
            "pop_size": pop_size,
            "generations": generations,
            "max_payload_kg": max_payload_kg,
            "max_battery_km": max_battery_km,
            "enable_dynamic_events": enable_dynamic,
        },
        "pathfinding": {
            "selected_algorithm": path_algorithm,
            "total_explored": matrices["total_explored"],
            "total_runtime_ms": matrices["total_runtime_ms"],
            "explored_union": [list(pt) for pt in matrices["explored_union"]],
            "benchmark": path_benchmark,
        },
        "routing": {
            "selected_algorithm": routing_algorithm,
            "active": active_routing,
            "ga_summary": {
                "objective": ga_result["evaluation"]["objective"],
                "total_distance_km": ga_result["evaluation"]["total_distance_km"],
                "makespan_min": ga_result["evaluation"]["makespan_min"],
                "on_time_pct": ga_result["evaluation"]["on_time_pct"],
                "runtime_ms": ga_result["runtime_ms"],
                "history": ga_result["history"],
            },
            "sa_summary": {
                "objective": sa_result["evaluation"]["objective"],
                "total_distance_km": sa_result["evaluation"]["total_distance_km"],
                "makespan_min": sa_result["evaluation"]["makespan_min"],
                "on_time_pct": sa_result["evaluation"]["on_time_pct"],
                "runtime_ms": sa_result["runtime_ms"],
                "history": sa_result["history"],
            },
        },
        "dynamic": {
            "enabled": enable_dynamic or len(injected_events) > 0,
            "events": [e.to_dict() for e in all_dyn_events],
            "replan_log": replan_log,
            "superseded_routes": superseded_routes,
            "initial_distance_km": initial_distance_km,
            "adapted_distance_km": eval_data["total_distance_km"],
        },
        "timeline": timeline,
    }


def export_precomputed_json(output_path: str) -> None:
    """Precompute all 3 default scenarios (with dynamic events) for static web fallback."""
    bundle = {}
    for sc_id in ("semeru", "cianjur", "demak"):
        bundle[sc_id] = solve_mission({"scenario_id": sc_id, "enable_dynamic_events": True})
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f)
