"""AeroRelief core package: Python AI Search & Multi-Drone Dynamic Routing Engine."""

from .models import Camp, DroneSpec, DynamicHazardEvent, HazardZone, Hill, Scenario
from .environment import TopographicEnvironment
from .pathfinding import (
    PathResult,
    astar_search,
    ucs_search,
    greedy_bfs_search,
    compute_distance_matrices,
    benchmark_pathfinding_algorithms,
)
from .routing import (
    GeneticDroneOptimizer,
    SimulatedAnnealingOptimizer,
    decode_and_evaluate,
)
from .dynamic import (
    active_dynamic_obstacles_at,
    event_cells,
    replan_drone_from_midair,
    simulate_dynamic_mission,
)
from .scenarios import SCENARIOS, get_scenario, list_scenarios
from .solver import solve_mission

__all__ = [
    "Camp",
    "DroneSpec",
    "DynamicHazardEvent",
    "HazardZone",
    "Hill",
    "Scenario",
    "TopographicEnvironment",
    "PathResult",
    "astar_search",
    "ucs_search",
    "greedy_bfs_search",
    "compute_distance_matrices",
    "benchmark_pathfinding_algorithms",
    "GeneticDroneOptimizer",
    "SimulatedAnnealingOptimizer",
    "decode_and_evaluate",
    "active_dynamic_obstacles_at",
    "event_cells",
    "replan_drone_from_midair",
    "simulate_dynamic_mission",
    "SCENARIOS",
    "get_scenario",
    "list_scenarios",
    "solve_mission",
]
