"""AeroRelief core package: Python AI Search & Multi-Drone Routing Engine."""

from .models import Camp, DroneSpec, HazardZone, Hill, Scenario
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
from .scenarios import SCENARIOS, get_scenario, list_scenarios
from .solver import solve_mission

__all__ = [
    "Camp",
    "DroneSpec",
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
    "SCENARIOS",
    "get_scenario",
    "list_scenarios",
    "solve_mission",
]
