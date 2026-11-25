"""Grid search algorithms (A*, Uniform Cost Search, Greedy Best-First Search) in Python."""

import heapq
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from .environment import TopographicEnvironment, Coord
from .models import Camp


@dataclass
class PathResult:
    algorithm: str
    path: Optional[List[Coord]]
    cost: float
    distance_km: float
    explored_nodes: List[Coord] = field(default_factory=list)
    runtime_ms: float = 0.0
    elevation_profile: List[float] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.path is not None and len(self.path) > 0


def heuristic_euclidean(a: Coord, b: Coord) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _reconstruct_path(
    came_from: Dict[Coord, Coord], start: Coord, goal: Coord
) -> List[Coord]:
    path: List[Coord] = []
    curr = goal
    while curr in came_from:
        path.append(curr)
        curr = came_from[curr]
    path.append(start)
    path.reverse()
    return path


def _grid_search(
    env: TopographicEnvironment,
    start: Coord,
    goal: Coord,
    algorithm: str,
) -> PathResult:
    t0 = time.perf_counter()

    if not env.is_passable(start) or not env.is_passable(goal):
        return PathResult(
            algorithm=algorithm,
            path=None,
            cost=float("inf"),
            distance_km=float("inf"),
            explored_nodes=[],
            runtime_ms=(time.perf_counter() - t0) * 1000.0,
            elevation_profile=[],
        )

    if start == goal:
        return PathResult(
            algorithm=algorithm,
            path=[start],
            cost=0.0,
            distance_km=0.0,
            explored_nodes=[start],
            runtime_ms=(time.perf_counter() - t0) * 1000.0,
            elevation_profile=[env.get_elevation(start)],
        )

    counter = 0
    open_heap: List[Tuple[float, int, Coord]] = []
    heapq.heappush(open_heap, (0.0, counter, start))

    came_from: Dict[Coord, Coord] = {}
    g_score: Dict[Coord, float] = {start: 0.0}
    dist_score: Dict[Coord, float] = {start: 0.0}
    closed: set = set()
    explored_order: List[Coord] = []

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        closed.add(current)
        explored_order.append(current)

        if current == goal:
            path = _reconstruct_path(came_from, start, goal)
            elev_profile = [env.get_elevation(p) for p in path]
            return PathResult(
                algorithm=algorithm,
                path=path,
                cost=round(g_score[goal], 4),
                distance_km=round(dist_score[goal], 4),
                explored_nodes=explored_order,
                runtime_ms=round((time.perf_counter() - t0) * 1000.0, 4),
                elevation_profile=elev_profile,
            )

        for neighbor, step_cost, horiz_dist in env.get_neighbors(current):
            if neighbor in closed:
                continue
            tentative_g = g_score[current] + step_cost
            tentative_dist = dist_score[current] + horiz_dist

            if algorithm == "greedy":
                if neighbor not in g_score:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    dist_score[neighbor] = tentative_dist
                    counter += 1
                    priority = heuristic_euclidean(neighbor, goal)
                    heapq.heappush(open_heap, (priority, counter, neighbor))
            else:
                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    dist_score[neighbor] = tentative_dist
                    counter += 1
                    h = heuristic_euclidean(neighbor, goal) if algorithm == "astar" else 0.0
                    heapq.heappush(open_heap, (tentative_g + h, counter, neighbor))

    return PathResult(
        algorithm=algorithm,
        path=None,
        cost=float("inf"),
        distance_km=float("inf"),
        explored_nodes=explored_order,
        runtime_ms=round((time.perf_counter() - t0) * 1000.0, 4),
        elevation_profile=[],
    )


def astar_search(env: TopographicEnvironment, start: Coord, goal: Coord) -> PathResult:
    """Informed Search: A* with admissible Euclidean distance heuristic."""
    return _grid_search(env, start, goal, "astar")


def ucs_search(env: TopographicEnvironment, start: Coord, goal: Coord) -> PathResult:
    """Uninformed Search: Uniform Cost Search (Dijkstra)."""
    return _grid_search(env, start, goal, "ucs")


def greedy_bfs_search(env: TopographicEnvironment, start: Coord, goal: Coord) -> PathResult:
    """Informed Baseline: Greedy Best-First Search using h(n) only."""
    return _grid_search(env, start, goal, "greedy")


def run_search(
    env: TopographicEnvironment, start: Coord, goal: Coord, algorithm: str = "astar"
) -> PathResult:
    alg = algorithm.lower().strip()
    if alg in ("astar", "a*", "a_star"):
        return astar_search(env, start, goal)
    if alg in ("ucs", "dijkstra"):
        return ucs_search(env, start, goal)
    if alg in ("greedy", "greedy_bfs", "gbfs"):
        return greedy_bfs_search(env, start, goal)
    raise ValueError(f"Algoritma pencarian tidak dikenali: {algorithm}")


def compute_distance_matrices(
    env: TopographicEnvironment,
    depot: Coord,
    camps: List[Camp],
    algorithm: str = "astar",
) -> Dict[str, object]:
    """Compute pairwise safe paths and costs between depot (-1) and all camps."""
    point_coords: Dict[int, Coord] = {-1: depot}
    for idx, camp in enumerate(camps):
        point_coords[idx] = (camp.x, camp.y)

    all_ids = [-1] + list(range(len(camps)))
    cost_matrix: Dict[Tuple[int, int], float] = {}
    dist_matrix: Dict[Tuple[int, int], float] = {}
    path_matrix: Dict[Tuple[int, int], List[Coord]] = {}
    explored_union: List[Coord] = []
    explored_seen = set()
    total_explored = 0
    total_runtime_ms = 0.0
    unreachable_ids: List[int] = []

    if not env.is_passable(depot):
        return {
            "cost_matrix": cost_matrix,
            "dist_matrix": dist_matrix,
            "path_matrix": path_matrix,
            "explored_union": [],
            "unreachable_camp_ids": [c.id for c in camps],
            "unreachable_indices": list(range(len(camps))),
            "depot_blocked": True,
            "total_explored": 0,
            "total_runtime_ms": 0.0,
        }

    for p1 in all_ids:
        for p2 in all_ids:
            if p1 == p2:
                cost_matrix[(p1, p2)] = 0.0
                dist_matrix[(p1, p2)] = 0.0
                path_matrix[(p1, p2)] = [point_coords[p1]]
                continue
            res = run_search(env, point_coords[p1], point_coords[p2], algorithm=algorithm)
            cost_matrix[(p1, p2)] = res.cost
            dist_matrix[(p1, p2)] = res.distance_km
            path_matrix[(p1, p2)] = res.path or []
            total_explored += len(res.explored_nodes)
            total_runtime_ms += res.runtime_ms
            # Record explored nodes for depot->camp legs for clean visualization
            if p1 == -1:
                for node in res.explored_nodes:
                    if node not in explored_seen:
                        explored_seen.add(node)
                        explored_union.append(node)

    unreachable_indices: List[int] = []
    for idx, camp in enumerate(camps):
        if math.isinf(cost_matrix.get((-1, idx), float("inf"))) or math.isinf(
            cost_matrix.get((idx, -1), float("inf"))
        ):
            unreachable_ids.append(camp.id)
            unreachable_indices.append(idx)

    return {
        "cost_matrix": cost_matrix,
        "dist_matrix": dist_matrix,
        "path_matrix": path_matrix,
        "explored_union": explored_union,
        "unreachable_camp_ids": unreachable_ids,
        "unreachable_indices": unreachable_indices,
        "depot_blocked": False,
        "total_explored": total_explored,
        "total_runtime_ms": round(total_runtime_ms, 2),
    }


def benchmark_pathfinding_algorithms(
    env: TopographicEnvironment,
    depot: Coord,
    camps: List[Camp],
) -> List[Dict[str, object]]:
    """Benchmark A*, Uniform Cost Search, and Greedy Best-First Search on active pairs."""
    algorithms = [
        ("astar", "A* Search (Informed)"),
        ("ucs", "Uniform Cost Search (Uninformed)"),
        ("greedy", "Greedy Best-First Search"),
    ]
    results: Dict[str, Dict[str, object]] = {}

    if not camps or not env.is_passable(depot):
        return []

    point_coords: Dict[int, Coord] = {-1: depot}
    for idx, camp in enumerate(camps):
        point_coords[idx] = (camp.x, camp.y)

    all_ids = [-1] + list(range(len(camps)))
    ucs_total_cost = 0.0

    for key, label in algorithms:
        total_explored = 0
        total_runtime = 0.0
        total_cost = 0.0
        total_dist = 0.0
        valid_pairs = 0
        depot_leg_explored = 0

        for p1 in all_ids:
            for p2 in all_ids:
                if p1 == p2:
                    continue
                res = run_search(env, point_coords[p1], point_coords[p2], algorithm=key)
                total_explored += len(res.explored_nodes)
                total_runtime += res.runtime_ms
                if p1 == -1:
                    depot_leg_explored += len(res.explored_nodes)
                if res.found:
                    total_cost += res.cost
                    total_dist += res.distance_km
                    valid_pairs += 1

        avg_cost = total_cost / max(valid_pairs, 1)
        avg_dist = total_dist / max(valid_pairs, 1)
        if key == "ucs":
            ucs_total_cost = total_cost

        results[key] = {
            "algorithm": key,
            "label": label,
            "total_explored_nodes": total_explored,
            "depot_leg_explored_nodes": depot_leg_explored,
            "total_runtime_ms": round(total_runtime, 2),
            "avg_path_cost": round(avg_cost, 3),
            "avg_distance_km": round(avg_dist, 3),
            "total_pair_cost": round(total_cost, 3),
            "valid_pairs": valid_pairs,
        }

    ucs_ref = ucs_total_cost if ucs_total_cost > 0 else 1.0
    ordered_output: List[Dict[str, object]] = []
    for key, _ in algorithms:
        entry = results[key]
        gap_pct = ((entry["total_pair_cost"] - ucs_ref) / ucs_ref) * 100.0
        entry["optimality_gap_pct"] = round(max(0.0, gap_pct), 2)
        ordered_output.append(entry)

    return ordered_output
