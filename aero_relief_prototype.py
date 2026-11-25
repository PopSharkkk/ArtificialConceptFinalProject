"""
AeroRelief: AI Simulation Engine (A* Pathfinding + Genetic Algorithm VRPTW-BL)
Final Project - Konsep Kecerdasan Artifisial (EK234201) - Teknik Informatika ITS

This module provides both backward-compatible prototype classes and the full
production solver entrypoint using the modular `aerorelief` package.
"""

import math
from typing import List, Tuple
from aerorelief import (
    TopographicEnvironment,
    astar_search as _pkg_astar,
    solve_mission,
)
from aerorelief.models import Camp
from aerorelief.routing import GeneticDroneOptimizer
from aerorelief.scenarios import build_drone_fleet
from aerorelief.pathfinding import compute_distance_matrices


class GridEnvironment(TopographicEnvironment):
    """Backward-compatible wrapper around TopographicEnvironment."""

    def __init__(self, width: int = 30, height: int = 30):
        super().__init__(width=width, height=height)

    def get_neighbors(self, pos: Tuple[int, int]):
        return [(nxt, cost) for nxt, cost, _ in super().get_neighbors(pos)]


def astar_search(env: TopographicEnvironment, start: Tuple[int, int], goal: Tuple[int, int]):
    """Backward-compatible helper returning (path, cost)."""
    res = _pkg_astar(env, start, goal)
    return res.path, res.cost


class GeneticDroneRouter:
    """Backward-compatible wrapper around GeneticDroneOptimizer."""

    def __init__(
        self,
        depot: Tuple[int, int],
        camps: List[Tuple[int, int]],
        distance_matrix: dict,
        num_drones: int = 2,
        pop_size: int = 30,
        generations: int = 50,
    ):
        self.depot = depot
        self.camp_objs = [
            Camp(id=i + 1, name=f"Posko {i + 1}", x=c[0], y=c[1])
            for i, c in enumerate(camps)
        ]
        self.drones = build_drone_fleet(num_drones=num_drones)
        self.distance_matrix = distance_matrix
        self.pop_size = pop_size
        self.generations = generations

    def run(self):
        opt = GeneticDroneOptimizer(
            camps=self.camp_objs,
            drones=self.drones,
            cost_matrix=self.distance_matrix,
            dist_matrix=self.distance_matrix,
            pop_size=self.pop_size,
            generations=self.generations,
        )
        res = opt.run()
        ordered_camps = [g for g in res["best_chromosome"] if g >= 0]
        return ordered_camps, res["evaluation"]["total_distance_km"]


def run_cli_demo() -> None:
    print("=== AeroRelief AI Simulation Engine (Erupsi Gunung Semeru) ===")
    mission = solve_mission({"scenario_id": "semeru", "num_drones": 3, "generations": 80})
    if not mission.get("reachable"):
        print("Error:", mission.get("message"))
        return

    print(f"Skenario     : {mission['scenario']['title']}")
    print(f"Base Depot   : {mission['scenario']['depot_name']} {tuple(mission['depot'])}")
    print(f"Posko Target : {len(mission['camps'])} posko darurat\n")

    print("--- Benchmark Pencarian Jalur (Informed vs Uninformed) ---")
    for row in mission["pathfinding"]["benchmark"]:
        print(
            f"  {row['label']:<34} | Simpul: {row['total_explored_nodes']:>6} | "
            f"Waktu: {row['total_runtime_ms']:>6.2f} ms | Rata-rata Cost: {row['avg_path_cost']:.3f} | "
            f"Gap: {row['optimality_gap_pct']:.2f}%"
        )

    active = mission["routing"]["active"]["evaluation"]
    print("\n--- Hasil Optimasi Rute Multi-Drone (Genetic Algorithm VRPTW-BL) ---")
    print(
        f"Total Jarak: {active['total_distance_km']:.2f} km | "
        f"Makespan: {active['makespan_min']:.2f} menit | "
        f"Ketepatan Waktu: {active['on_time_pct']:.1f}%\n"
    )
    for ds in active["drone_schedules"]:
        route_str = " -> ".join(ds["route_labels"])
        print(
            f"  {ds['callsign']:<16} | {ds['total_distance_km']:>5.2f} km | "
            f"{ds['total_time_min']:>5.2f} mnt | Reload: {ds['reloads']}x | {route_str}"
        )

    replan_log = mission.get("dynamic", {}).get("replan_log", [])
    if replan_log:
        print("\n--- Log Adaptasi Rintangan Dinamis (Mid-Flight A* Re-planning) ---")
        for item in replan_log:
            print(f"  * {item['summary']}")


if __name__ == "__main__":
    run_cli_demo()
