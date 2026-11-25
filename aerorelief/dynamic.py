"""Dynamic obstacles & real-time mid-flight adaptive A* re-planning engine."""

from collections import deque
import itertools
import math
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .environment import Coord, TopographicEnvironment
from .models import Camp, DroneSpec, DynamicHazardEvent, Scenario
from .pathfinding import run_search
from .routing import URGENCY_WEIGHTS


def event_cells(ev: DynamicHazardEvent, width: int, height: int) -> Set[Coord]:
    cells: Set[Coord] = set()
    if ev.cells:
        for cx, cy in ev.cells:
            x, y = int(cx), int(cy)
            if 0 <= x < width and 0 <= y < height:
                cells.add((x, y))
        return cells
    for x in range(ev.x_min, ev.x_max + 1):
        for y in range(ev.y_min, ev.y_max + 1):
            if 0 <= x < width and 0 <= y < height:
                cells.add((x, y))
    return cells


def active_dynamic_obstacles_at(
    events: Iterable[DynamicHazardEvent],
    t_min: float,
    width: int,
    height: int,
) -> Set[Coord]:
    """Return dynamic obstacle cells active at exact timestamp t_min."""
    blocked: Set[Coord] = set()
    for ev in events:
        if ev.trigger_min <= t_min + 1e-6:
            if ev.expire_min is None or t_min < ev.expire_min - 1e-6:
                blocked |= event_cells(ev, width, height)
    return blocked


def find_nearest_safe_cell(
    env: TopographicEnvironment, pos: Coord
) -> Optional[Coord]:
    """BFS outward from pos to find closest passable grid coordinate."""
    if env.is_passable(pos):
        return pos
    visited = {pos}
    queue = deque([pos])
    dirs = [
        (0, 1), (1, 0), (0, -1), (-1, 0),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    ]
    while queue:
        cx, cy = queue.popleft()
        for dx, dy in dirs:
            nxt = (cx + dx, cy + dy)
            if nxt in visited:
                continue
            if 0 <= nxt[0] < env.width and 0 <= nxt[1] < env.height:
                if env.is_passable(nxt):
                    return nxt
                visited.add(nxt)
                queue.append(nxt)
    return None


def _polyline_distance_and_cost(
    env: TopographicEnvironment, path: List[Coord]
) -> Tuple[float, float]:
    dist = 0.0
    cost = 0.0
    for i in range(len(path) - 1):
        u, v = tuple(path[i]), tuple(path[i + 1])
        dx, dy = abs(v[0] - u[0]), abs(v[1] - u[1])
        horiz = math.hypot(dx, dy)
        elev_diff = env.get_elevation(v) - env.get_elevation(u)
        dist += horiz
        cost += horiz + max(0.0, elev_diff) * 0.004
    return dist, cost


def split_drone_state_at_time(
    ds: Dict[str, Any],
    t_ev: float,
    depot: Coord,
    spec: DroneSpec,
    camps: List[Camp],
    env_ref: TopographicEnvironment,
) -> Dict[str, Any]:
    """Split a drone schedule at t_ev into completed past history and future state."""
    past_segments: List[Dict[str, Any]] = []
    future_waypoints: List[Coord] = []
    curr_pos: Coord = depot
    resume_time_min: float = t_ev

    delivered_deliveries = [
        dict(d) for d in ds["deliveries"] if d["arrival_min"] <= t_ev + 1e-6
    ]
    delivered_indices = {d["camp_index"] for d in delivered_deliveries}
    pending_indices = [
        idx for idx in ds["assigned_camp_indices"] if idx not in delivered_indices
    ]

    rem_payload = spec.max_payload_kg
    rem_battery = spec.max_battery_km
    reloads_done = 0

    segments = ds["segments"]
    for idx, seg in enumerate(segments):
        s_start = seg["start_min"]
        s_end = seg["end_min"]
        raw_path = [tuple(p) for p in seg["path"]]

        if s_end <= t_ev + 1e-6:
            past_segments.append(dict(seg))
            if raw_path:
                curr_pos = raw_path[-1]
            rem_battery -= seg["distance_km"]
            if seg["is_reload_trip"]:
                reloads_done += 1
                # Reload takes 5.0 min after landing at depot
                reload_finish = s_end + 5.0
                if reload_finish > resume_time_min:
                    resume_time_min = reload_finish
                rem_payload = spec.max_payload_kg
                rem_battery = spec.max_battery_km
            elif seg["to_id"] >= 0:
                if seg["to_id"] in delivered_indices:
                    rem_payload -= camps[seg["to_id"]].demand_kg
                dropoff_finish = s_end + 2.0
                if dropoff_finish > resume_time_min and idx < len(segments) - 1:
                    resume_time_min = dropoff_finish

        elif s_start < t_ev < s_end and len(raw_path) >= 2:
            span = max(s_end - s_start, 1e-6)
            frac = (t_ev - s_start) / span
            split_i = min(len(raw_path) - 1, max(0, int(round(frac * (len(raw_path) - 1)))))
            curr_pos = raw_path[split_i]
            past_path = raw_path[: split_i + 1]
            fut_path = raw_path[split_i:]

            if len(past_path) >= 2:
                p_dist, p_cost = _polyline_distance_and_cost(env_ref, past_path)
                past_segments.append(
                    {
                        "from_id": seg["from_id"],
                        "to_id": -2,  # Mid-air waypoint split
                        "from_label": seg["from_label"],
                        "to_label": f"Udara {curr_pos}",
                        "distance_km": round(p_dist, 3),
                        "cost": round(p_cost, 3),
                        "start_min": round(s_start, 2),
                        "end_min": round(t_ev, 2),
                        "is_reload_trip": False,
                        "path": [list(p) for p in past_path],
                    }
                )
                rem_battery -= p_dist
            resume_time_min = t_ev
            future_waypoints.extend(fut_path)
        else:
            # Entirely in the future (s_start >= t_ev)
            future_waypoints.extend(raw_path)

    # Deduplicate consecutive identical future waypoints
    dedup_future: List[Coord] = []
    for pt in future_waypoints:
        if not dedup_future or dedup_future[-1] != pt:
            dedup_future.append(pt)

    return {
        "curr_pos": curr_pos,
        "resume_time_min": resume_time_min,
        "past_segments": past_segments,
        "past_deliveries": delivered_deliveries,
        "pending_indices": pending_indices,
        "rem_payload": max(0.0, rem_payload),
        "rem_battery": max(0.0, rem_battery),
        "reloads_done": reloads_done,
        "future_waypoints": dedup_future,
    }


def replan_drone_from_midair(
    curr_pos: Coord,
    start_time_min: float,
    pending_indices: List[int],
    rem_payload: float,
    rem_battery: float,
    spec: DroneSpec,
    depot: Coord,
    camps: List[Camp],
    env_now: TopographicEnvironment,
    path_algorithm: str = "astar",
) -> Dict[str, Any]:
    """Recompute optimal trajectory from current airborne coordinate avoiding active obstacles."""
    speed_km_per_min = max(spec.speed_kmh / 60.0, 0.1)
    new_segments: List[Dict[str, Any]] = []
    new_deliveries: List[Dict[str, Any]] = []
    explored_count = 0
    runtime_ms = 0.0
    reloads_added = 0
    time_min = start_time_min

    # Emergency escape if obstacle spawned directly over current drone cell
    if not env_now.is_passable(curr_pos):
        safe_pos = find_nearest_safe_cell(env_now, curr_pos)
        if safe_pos is None:
            return {"reachable": False, "reason": "Seluruh peta tertutup rintangan."}
        esc_dist = math.hypot(safe_pos[0] - curr_pos[0], safe_pos[1] - curr_pos[1])
        esc_dur = esc_dist / speed_km_per_min
        new_segments.append(
            {
                "from_id": -2,
                "to_id": -2,
                "from_label": f"Zona Bahaya {curr_pos}",
                "to_label": f"Titik Aman {safe_pos}",
                "distance_km": round(esc_dist, 3),
                "cost": round(esc_dist, 3),
                "start_min": round(time_min, 2),
                "end_min": round(time_min + esc_dur, 2),
                "is_reload_trip": False,
                "is_escape_step": True,
                "path": [list(curr_pos), list(safe_pos)],
            }
        )
        time_min += esc_dur
        rem_battery = max(0.0, rem_battery - esc_dist)
        curr_pos = safe_pos

    # Case 1: No pending camps left -> just return safely from curr_pos to depot
    if not pending_indices:
        if curr_pos != depot:
            res = run_search(env_now, curr_pos, depot, algorithm=path_algorithm)
            explored_count += len(res.explored_nodes)
            runtime_ms += res.runtime_ms
            if not res.found or not res.path:
                return {"reachable": False, "reason": "Jalur kembali ke Depot tertutup penuh."}
            dur = res.distance_km / speed_km_per_min
            new_segments.append(
                {
                    "from_id": -2,
                    "to_id": -1,
                    "from_label": f"Udara {curr_pos}",
                    "to_label": "Depot",
                    "distance_km": round(res.distance_km, 3),
                    "cost": round(res.cost, 3),
                    "start_min": round(time_min, 2),
                    "end_min": round(time_min + dur, 2),
                    "is_reload_trip": False,
                    "path": [list(p) for p in res.path],
                }
            )
        return {
            "reachable": True,
            "segments": new_segments,
            "deliveries": [],
            "reloads_added": 0,
            "explored_count": explored_count,
            "runtime_ms": round(runtime_ms, 3),
        }

    # Precompute fresh paths among {curr_pos (-2), depot (-1), pending_indices}
    nodes: Dict[int, Coord] = {-2: curr_pos, -1: depot}
    for idx in pending_indices:
        nodes[idx] = (camps[idx].x, camps[idx].y)

    pair_res: Dict[Tuple[int, int], Any] = {}
    for u_id, u_pt in nodes.items():
        for v_id, v_pt in nodes.items():
            if u_id == v_id:
                continue
            r = run_search(env_now, u_pt, v_pt, algorithm=path_algorithm)
            explored_count += len(r.explored_nodes)
            runtime_ms += r.runtime_ms
            pair_res[(u_id, v_id)] = r

    # Verify every pending camp is reachable from depot/curr_pos
    for idx in pending_indices:
        if not pair_res[(-1, idx)].found or not pair_res[(idx, -1)].found:
            return {
                "reachable": False,
                "reason": f"{camps[idx].name} terisolasi oleh rintangan baru.",
                "blocked_camp_id": camps[idx].id,
            }

    # Evaluate sequence helper
    def simulate_order(order: Tuple[int, ...]) -> Tuple[float, List[Dict[str, Any]], List[Dict[str, Any]], int]:
        sim_segs: List[Dict[str, Any]] = []
        sim_dels: List[Dict[str, Any]] = []
        t = time_min
        rp = rem_payload
        rb = rem_battery
        c_node = -2
        reloads = 0
        tot_cost = 0.0
        w_late = 0.0

        for c_idx in order:
            camp = camps[c_idx]
            leg = pair_res[(c_node, c_idx)]
            back_depot = pair_res[(c_idx, -1)]
            need_reload = False
            if c_node != -1:
                if (
                    not leg.found
                    or camp.demand_kg > rp
                    or (leg.distance_km + back_depot.distance_km) > rb
                ):
                    need_reload = True

            if need_reload:
                to_dep = pair_res[(c_node, -1)]
                if not to_dep.found:
                    return (float("inf"), [], [], 0)
                dur_dep = to_dep.distance_km / speed_km_per_min
                sim_segs.append(
                    {
                        "from_id": c_node,
                        "to_id": -1,
                        "from_label": f"Udara {curr_pos}" if c_node == -2 else camps[c_node].name,
                        "to_label": "Depot (Isi Ulang)",
                        "distance_km": round(to_dep.distance_km, 3),
                        "cost": round(to_dep.cost, 3),
                        "start_min": round(t, 2),
                        "end_min": round(t + dur_dep, 2),
                        "is_reload_trip": True,
                        "path": [list(p) for p in (to_dep.path or [])],
                    }
                )
                t += dur_dep + 5.0
                tot_cost += to_dep.cost
                rp = spec.max_payload_kg
                rb = spec.max_battery_km
                c_node = -1
                reloads += 1
                leg = pair_res[(-1, c_idx)]

            if not leg.found:
                return (float("inf"), [], [], 0)

            dur_fly = leg.distance_km / speed_km_per_min
            sim_segs.append(
                {
                    "from_id": c_node,
                    "to_id": c_idx,
                    "from_label": (
                        "Depot"
                        if c_node == -1
                        else (f"Re-plan {curr_pos}" if c_node == -2 else camps[c_node].name)
                    ),
                    "to_label": camp.name,
                    "distance_km": round(leg.distance_km, 3),
                    "cost": round(leg.cost, 3),
                    "start_min": round(t, 2),
                    "end_min": round(t + dur_fly, 2),
                    "is_reload_trip": False,
                    "path": [list(p) for p in (leg.path or [])],
                }
            )
            t += dur_fly
            arr = t
            t += 2.0
            late = max(0.0, arr - camp.time_window_min)
            w_late += late * URGENCY_WEIGHTS.get(camp.urgency, 1.0)
            tot_cost += leg.cost
            rp -= camp.demand_kg
            rb -= leg.distance_km
            c_node = c_idx

            sim_dels.append(
                {
                    "camp_index": c_idx,
                    "camp_id": camp.id,
                    "camp_name": camp.name,
                    "urgency": camp.urgency,
                    "demand_kg": camp.demand_kg,
                    "arrival_min": round(arr, 2),
                    "time_window_min": camp.time_window_min,
                    "late_min": round(late, 2),
                    "battery_remaining_pct": round(
                        max(0.0, (rb / spec.max_battery_km) * 100.0), 1
                    ),
                }
            )

        # Final return to depot
        fin_dep = pair_res[(c_node, -1)]
        if not fin_dep.found:
            return (float("inf"), [], [], 0)
        dur_fin = fin_dep.distance_km / speed_km_per_min
        sim_segs.append(
            {
                "from_id": c_node,
                "to_id": -1,
                "from_label": camps[c_node].name,
                "to_label": "Depot",
                "distance_km": round(fin_dep.distance_km, 3),
                "cost": round(fin_dep.cost, 3),
                "start_min": round(t, 2),
                "end_min": round(t + dur_fin, 2),
                "is_reload_trip": False,
                "path": [list(p) for p in (fin_dep.path or [])],
            }
        )
        t += dur_fin
        tot_cost += fin_dep.cost
        score = tot_cost + 0.35 * t + 2.5 * w_late
        return (score, sim_segs, sim_dels, reloads)

    if len(pending_indices) <= 5:
        candidates = list(itertools.permutations(pending_indices))
    else:
        # Greedy urgency + 2-opt swaps
        base_ord = tuple(pending_indices)
        candidates = [base_ord]
        for i in range(len(base_ord)):
            for j in range(i + 1, len(base_ord)):
                lst = list(base_ord)
                lst[i], lst[j] = lst[j], lst[i]
                candidates.append(tuple(lst))

    best_score = float("inf")
    best_segs: List[Dict[str, Any]] = []
    best_dels: List[Dict[str, Any]] = []
    best_reloads = 0

    for cand in candidates:
        sc, s_segs, s_dels, s_rel = simulate_order(cand)
        if sc < best_score:
            best_score = sc
            best_segs = s_segs
            best_dels = s_dels
            best_reloads = s_rel

    if math.isinf(best_score):
        return {"reachable": False, "reason": "Tidak ditemukan urutan rute aman ke posko tersisa."}

    return {
        "reachable": True,
        "segments": new_segments + best_segs,
        "deliveries": best_dels,
        "reloads_added": best_reloads,
        "explored_count": explored_count,
        "runtime_ms": round(runtime_ms, 3),
    }


def _rebuild_route_labels(segments: List[Dict[str, Any]], replanned: bool) -> List[str]:
    if not segments:
        return ["Depot"]
    labels = ["Depot"]
    for seg in segments:
        to_lbl = seg["to_label"]
        if seg["to_id"] == -2 and to_lbl.startswith("Udara"):
            if labels[-1] != "Re-plan A*":
                labels.append("Re-plan A*")
        elif to_lbl not in ("Depot",) or seg == segments[-1]:
            if labels[-1] != to_lbl:
                labels.append(to_lbl)
    if replanned and "Re-plan A*" not in labels and len(labels) >= 2:
        labels.insert(1, "Re-plan A*")
    return labels


def simulate_dynamic_mission(
    scenario: Scenario,
    base_obstacles: Set[Coord],
    depot: Coord,
    camps: List[Camp],
    drones: List[DroneSpec],
    initial_eval: Dict[str, Any],
    dynamic_events: List[DynamicHazardEvent],
    path_algorithm: str = "astar",
) -> Dict[str, Any]:
    """Simulate chronological dynamic obstacle changes and adapt affected UAV trajectories."""
    schedules = [
        {
            **ds,
            "segments": [dict(s) for s in ds["segments"]],
            "deliveries": [dict(d) for d in ds["deliveries"]],
            "route_labels": list(ds["route_labels"]),
        }
        for ds in initial_eval["drone_schedules"]
    ]
    drone_by_id = {d.id: d for d in drones}

    env_ref = TopographicEnvironment(
        width=scenario.grid_width,
        height=scenario.grid_height,
        hills=scenario.hills,
        extra_obstacles=base_obstacles,
    )

    # Collect sorted event trigger timestamps
    trigger_times = sorted({round(ev.trigger_min, 3) for ev in dynamic_events if ev.trigger_min >= 0.0})
    replan_log: List[Dict[str, Any]] = []
    superseded_routes: List[Dict[str, Any]] = []

    for t_ev in trigger_times:
        current_makespan = max((ds["total_time_min"] for ds in schedules), default=0.0)
        if t_ev >= current_makespan - 1e-4:
            continue

        dyn_cells = active_dynamic_obstacles_at(
            dynamic_events, t_ev, scenario.grid_width, scenario.grid_height
        )
        combined_obs = base_obstacles | dyn_cells
        env_now = TopographicEnvironment(
            width=scenario.grid_width,
            height=scenario.grid_height,
            hills=scenario.hills,
            extra_obstacles=combined_obs,
        )

        if not env_now.is_passable(depot):
            return {
                "reachable": False,
                "failed_at_min": t_ev,
                "message": f"Rintangan baru pada menit {t_ev:.1f} menutup Base Depot.",
                "replan_log": replan_log,
                "superseded_routes": superseded_routes,
            }

        triggered_names = [
            ev.name for ev in dynamic_events if abs(ev.trigger_min - t_ev) < 0.05
        ]
        event_label = ", ".join(triggered_names) if triggered_names else f"Perubahan Rintangan (mnt {t_ev:.1f})"

        affected_callsigns: List[str] = []
        event_explored = 0
        event_runtime_ms = 0.0
        delta_dist_total = 0.0

        for idx, ds in enumerate(schedules):
            if not ds["segments"] or ds["total_time_min"] <= t_ev + 1e-5:
                continue

            spec = drone_by_id[ds["drone_id"]]
            split = split_drone_state_at_time(ds, t_ev, depot, spec, camps, env_ref)

            # Causal collision check: react only to obstacles currently active at t_ev
            has_collision = not env_now.is_passable(split["curr_pos"])
            if not has_collision:
                for fut_pt in split["future_waypoints"]:
                    if (int(fut_pt[0]), int(fut_pt[1])) in env_now.obstacles:
                        has_collision = True
                        break

            if not has_collision:
                continue

            old_dist = ds["total_distance_km"]
            if len(split["future_waypoints"]) >= 2:
                superseded_routes.append(
                    {
                        "trigger_min": t_ev,
                        "event_name": event_label,
                        "drone_id": ds["drone_id"],
                        "callsign": ds["callsign"],
                        "path": [list(p) for p in split["future_waypoints"]],
                    }
                )

            replan_res = replan_drone_from_midair(
                curr_pos=split["curr_pos"],
                start_time_min=split["resume_time_min"],
                pending_indices=split["pending_indices"],
                rem_payload=split["rem_payload"],
                rem_battery=split["rem_battery"],
                spec=spec,
                depot=depot,
                camps=camps,
                env_now=env_now,
                path_algorithm=path_algorithm,
            )

            if not replan_res["reachable"]:
                return {
                    "reachable": False,
                    "failed_at_min": t_ev,
                    "message": (
                        f"Pada menit {t_ev:.1f} ({event_label}), {ds['callsign']} gagal menemukan jalur memutar: "
                        f"{replan_res.get('reason', 'Jalur tertutup penuh.')}"
                    ),
                    "replan_log": replan_log,
                    "superseded_routes": superseded_routes,
                }

            combined_segs = split["past_segments"] + replan_res["segments"]
            combined_dels = split["past_deliveries"] + replan_res["deliveries"]
            new_dist = sum(s["distance_km"] for s in combined_segs)
            new_cost = sum(s["cost"] for s in combined_segs)
            new_end = combined_segs[-1]["end_min"] if combined_segs else ds["total_time_min"]
            new_reloads = split["reloads_done"] + replan_res["reloads_added"]

            schedules[idx] = {
                **ds,
                "segments": combined_segs,
                "deliveries": combined_dels,
                "route_labels": _rebuild_route_labels(combined_segs, replanned=True),
                "total_distance_km": round(new_dist, 2),
                "total_cost": round(new_cost, 2),
                "total_time_min": round(new_end, 2),
                "reloads": new_reloads,
                "status": "ADAPTIF (RE-PLAN)",
            }

            affected_callsigns.append(ds["callsign"])
            event_explored += replan_res["explored_count"]
            event_runtime_ms += replan_res["runtime_ms"]
            delta_dist_total += new_dist - old_dist

        if affected_callsigns:
            replan_log.append(
                {
                    "time_min": round(t_ev, 1),
                    "event_name": event_label,
                    "affected_drones": affected_callsigns,
                    "nodes_explored": event_explored,
                    "runtime_ms": round(event_runtime_ms, 2),
                    "detour_delta_km": round(delta_dist_total, 2),
                    "summary": (
                        f"Menit {t_ev:.1f}: {', '.join(affected_callsigns)} mendeteksi '{event_label}' "
                        f"dan menghitung ulang rute aman dari udara ({event_explored} simpul, {event_runtime_ms:.2f} ms)."
                    ),
                }
            )

    # Recompute fleet-level summary metrics after dynamic adaptation
    total_dist = sum(ds["total_distance_km"] for ds in schedules)
    total_cost = sum(ds["total_cost"] for ds in schedules)
    makespan = max((ds["total_time_min"] for ds in schedules), default=0.0)
    on_time_count = 0
    weighted_late = 0.0
    for ds in schedules:
        for d_info in ds["deliveries"]:
            if d_info["late_min"] <= 0.01:
                on_time_count += 1
            weighted_late += d_info["late_min"] * URGENCY_WEIGHTS.get(d_info["urgency"], 1.0)

    on_time_pct = (on_time_count / len(camps) * 100.0) if camps else 100.0
    objective = total_cost + 0.35 * makespan + 2.5 * weighted_late

    adapted_eval = {
        **initial_eval,
        "objective": round(objective, 4),
        "fitness": round(1.0 / (objective + 1e-6), 6),
        "total_cost": round(total_cost, 2),
        "total_distance_km": round(total_dist, 2),
        "makespan_min": round(makespan, 2),
        "weighted_late_min": round(weighted_late, 2),
        "on_time_pct": round(on_time_pct, 1),
        "drone_schedules": schedules,
    }

    return {
        "reachable": True,
        "evaluation": adapted_eval,
        "replan_log": replan_log,
        "superseded_routes": superseded_routes,
    }
