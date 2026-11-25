"""Multi-Drone VRPTW-BL optimizers: Genetic Algorithm and Simulated Annealing."""

import math
import random
import time
from typing import Any, Dict, List, Optional, Tuple
from .models import Camp, DroneSpec

URGENCY_WEIGHTS = {
    "KRITIS": 4.0,
    "TINGGI": 2.0,
    "SEDANG": 1.0,
}


def decode_and_evaluate(
    chromosome: List[int],
    camps: List[Camp],
    drones: List[DroneSpec],
    cost_matrix: Dict[Tuple[int, int], float],
    dist_matrix: Dict[Tuple[int, int], float],
    path_matrix: Optional[Dict[Tuple[int, int], List[Tuple[int, int]]]] = None,
) -> Dict[str, Any]:
    """Decode delimiter-based permutation into drone sorties and compute VRPTW-BL fitness."""
    num_drones = len(drones)
    drone_assignments: List[List[int]] = [[] for _ in range(num_drones)]

    d_idx = 0
    for gene in chromosome:
        if gene <= -100:
            d_idx = min(d_idx + 1, num_drones - 1)
        else:
            drone_assignments[d_idx].append(gene)

    total_cost = 0.0
    total_distance_km = 0.0
    makespan_min = 0.0
    weighted_late_min = 0.0
    infeasible_penalty = 0.0
    on_time_count = 0
    drone_schedules: List[Dict[str, Any]] = []

    for d in range(num_drones):
        spec = drones[d]
        assigned = drone_assignments[d]
        speed_km_per_min = max(spec.speed_kmh / 60.0, 0.1)
        rem_payload = spec.max_payload_kg
        rem_battery = spec.max_battery_km
        curr_node = -1  # Depot
        time_min = 0.0
        drone_dist = 0.0
        drone_cost = 0.0
        reloads = 0
        segments: List[Dict[str, Any]] = []
        deliveries: List[Dict[str, Any]] = []
        route_labels: List[str] = ["Depot"]
        battery_violation = False
        payload_violation = False

        for camp_idx in assigned:
            camp = camps[camp_idx]
            if camp.demand_kg > spec.max_payload_kg:
                payload_violation = True
                infeasible_penalty += 5000.0

            depot_to_camp_dist = dist_matrix.get((-1, camp_idx), float("inf"))
            camp_to_depot_dist = dist_matrix.get((camp_idx, -1), float("inf"))
            if depot_to_camp_dist + camp_to_depot_dist > spec.max_battery_km:
                battery_violation = True
                infeasible_penalty += 5000.0

            need_reload = False
            if curr_node != -1:
                leg_dist = dist_matrix.get((curr_node, camp_idx), float("inf"))
                if (
                    camp.demand_kg > rem_payload
                    or (leg_dist + camp_to_depot_dist) > rem_battery
                ):
                    need_reload = True

            if need_reload:
                ret_dist = dist_matrix.get((curr_node, -1), 0.0)
                ret_cost = cost_matrix.get((curr_node, -1), 0.0)
                ret_dur = ret_dist / speed_km_per_min
                seg_path = path_matrix.get((curr_node, -1), []) if path_matrix else []
                segments.append(
                    {
                        "from_id": curr_node,
                        "to_id": -1,
                        "from_label": camps[curr_node].name,
                        "to_label": "Depot (Isi Ulang)",
                        "distance_km": round(ret_dist, 3),
                        "cost": round(ret_cost, 3),
                        "start_min": round(time_min, 2),
                        "end_min": round(time_min + ret_dur, 2),
                        "is_reload_trip": True,
                        "path": seg_path,
                    }
                )
                time_min += ret_dur + 5.0  # 5 min battery swap + cargo reload
                drone_dist += ret_dist
                drone_cost += ret_cost
                rem_payload = spec.max_payload_kg
                rem_battery = spec.max_battery_km
                curr_node = -1
                reloads += 1
                route_labels.append("Depot (Reload)")

            fly_dist = dist_matrix.get((curr_node, camp_idx), float("inf"))
            fly_cost = cost_matrix.get((curr_node, camp_idx), float("inf"))
            if math.isinf(fly_dist):
                infeasible_penalty += 10000.0
                continue

            fly_dur = fly_dist / speed_km_per_min
            seg_path = path_matrix.get((curr_node, camp_idx), []) if path_matrix else []
            segments.append(
                {
                    "from_id": curr_node,
                    "to_id": camp_idx,
                    "from_label": "Depot" if curr_node == -1 else camps[curr_node].name,
                    "to_label": camp.name,
                    "distance_km": round(fly_dist, 3),
                    "cost": round(fly_cost, 3),
                    "start_min": round(time_min, 2),
                    "end_min": round(time_min + fly_dur, 2),
                    "is_reload_trip": False,
                    "path": seg_path,
                }
            )
            time_min += fly_dur
            arrival_min = time_min
            time_min += 2.0  # 2 min medical package drop-off

            late_min = max(0.0, arrival_min - camp.time_window_min)
            if late_min <= 0.01:
                on_time_count += 1
            weighted_late_min += late_min * URGENCY_WEIGHTS.get(camp.urgency, 1.0)

            drone_dist += fly_dist
            drone_cost += fly_cost
            rem_payload -= camp.demand_kg
            rem_battery -= fly_dist
            curr_node = camp_idx
            route_labels.append(camp.name)

            deliveries.append(
                {
                    "camp_index": camp_idx,
                    "camp_id": camp.id,
                    "camp_name": camp.name,
                    "urgency": camp.urgency,
                    "demand_kg": camp.demand_kg,
                    "arrival_min": round(arrival_min, 2),
                    "time_window_min": camp.time_window_min,
                    "late_min": round(late_min, 2),
                    "battery_remaining_pct": round(
                        max(0.0, (rem_battery / spec.max_battery_km) * 100.0), 1
                    ),
                }
            )

        if curr_node != -1:
            ret_dist = dist_matrix.get((curr_node, -1), 0.0)
            ret_cost = cost_matrix.get((curr_node, -1), 0.0)
            ret_dur = ret_dist / speed_km_per_min
            seg_path = path_matrix.get((curr_node, -1), []) if path_matrix else []
            segments.append(
                {
                    "from_id": curr_node,
                    "to_id": -1,
                    "from_label": camps[curr_node].name,
                    "to_label": "Depot",
                    "distance_km": round(ret_dist, 3),
                    "cost": round(ret_cost, 3),
                    "start_min": round(time_min, 2),
                    "end_min": round(time_min + ret_dur, 2),
                    "is_reload_trip": False,
                    "path": seg_path,
                }
            )
            time_min += ret_dur
            drone_dist += ret_dist
            drone_cost += ret_cost
            rem_battery -= ret_dist
            route_labels.append("Depot")

        if battery_violation:
            status = "MELEBIHI JARAK BATERAI"
        elif payload_violation:
            status = "MELEBIHI MUATAN"
        elif not assigned:
            status = "STANDBY"
        else:
            status = "OPTIMAL"

        total_cost += drone_cost
        total_distance_km += drone_dist
        makespan_min = max(makespan_min, time_min)

        total_payload_delivered = sum(camps[i].demand_kg for i in assigned)
        battery_used_pct = (
            min(100.0, (drone_dist / (spec.max_battery_km * (reloads + 1))) * 100.0)
            if assigned
            else 0.0
        )

        drone_schedules.append(
            {
                "drone_id": spec.id,
                "callsign": spec.callsign,
                "color": spec.color,
                "assigned_camp_indices": assigned,
                "route_labels": route_labels,
                "total_distance_km": round(drone_dist, 2),
                "total_cost": round(drone_cost, 2),
                "total_time_min": round(time_min, 2),
                "total_payload_kg": round(total_payload_delivered, 2),
                "reloads": reloads,
                "battery_used_pct": round(battery_used_pct, 1),
                "status": status,
                "deliveries": deliveries,
                "segments": segments,
            }
        )

    objective = (
        total_cost
        + 0.35 * makespan_min
        + 2.5 * weighted_late_min
        + infeasible_penalty
    )
    on_time_pct = (on_time_count / len(camps) * 100.0) if camps else 100.0

    return {
        "objective": round(objective, 4),
        "fitness": round(1.0 / (objective + 1e-6), 6),
        "total_cost": round(total_cost, 2),
        "total_distance_km": round(total_distance_km, 2),
        "makespan_min": round(makespan_min, 2),
        "weighted_late_min": round(weighted_late_min, 2),
        "on_time_pct": round(on_time_pct, 1),
        "feasible": infeasible_penalty == 0.0,
        "drone_schedules": drone_schedules,
    }


def _order_crossover(parent1: List[int], parent2: List[int], rng: random.Random) -> List[int]:
    size = len(parent1)
    if size < 2:
        return list(parent1)
    c1, c2 = sorted(rng.sample(range(size), 2))
    child = [None] * size
    child[c1 : c2 + 1] = parent1[c1 : c2 + 1]
    used = set(child[c1 : c2 + 1])
    fill_idx = 0
    for gene in parent2:
        if gene not in used:
            while child[fill_idx] is not None:
                fill_idx += 1
            child[fill_idx] = gene
            used.add(gene)
    return child  # type: ignore[return-value]


def _mutate_chromosome(chrom: List[int], rng: random.Random) -> List[int]:
    res = list(chrom)
    if len(res) < 2:
        return res
    if rng.random() < 0.5:
        # Swap mutation
        i, j = rng.sample(range(len(res)), 2)
        res[i], res[j] = res[j], res[i]
    else:
        # 2-opt segment inversion
        i, j = sorted(rng.sample(range(len(res)), 2))
        res[i : j + 1] = reversed(res[i : j + 1])
    return res


class GeneticDroneOptimizer:
    """Genetic Algorithm (Tournament + Order Crossover + Swap/2-opt Mutation) for VRPTW-BL."""

    def __init__(
        self,
        camps: List[Camp],
        drones: List[DroneSpec],
        cost_matrix: Dict[Tuple[int, int], float],
        dist_matrix: Dict[Tuple[int, int], float],
        path_matrix: Optional[Dict[Tuple[int, int], List[Tuple[int, int]]]] = None,
        pop_size: int = 50,
        generations: int = 80,
        mutation_rate: float = 0.25,
        seed: int = 42,
    ):
        self.camps = camps
        self.drones = drones
        self.cost_matrix = cost_matrix
        self.dist_matrix = dist_matrix
        self.path_matrix = path_matrix
        self.pop_size = max(10, pop_size)
        self.generations = max(5, generations)
        self.mutation_rate = mutation_rate
        self.rng = random.Random(seed)

    def _base_genes(self) -> List[int]:
        camp_genes = list(range(len(self.camps)))
        delimiters = [-100 - d for d in range(max(0, len(self.drones) - 1))]
        return camp_genes + delimiters

    def run(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        if not self.camps:
            empty_eval = decode_and_evaluate(
                [], self.camps, self.drones, self.cost_matrix, self.dist_matrix, self.path_matrix
            )
            return {
                "algorithm": "ga",
                "label": "Genetic Algorithm",
                "best_chromosome": [],
                "evaluation": empty_eval,
                "history": [],
                "runtime_ms": 0.0,
            }

        base = self._base_genes()
        population: List[List[int]] = []
        for _ in range(self.pop_size):
            c = list(base)
            self.rng.shuffle(c)
            population.append(c)

        best_chrom = list(population[0])
        best_eval = decode_and_evaluate(
            best_chrom, self.camps, self.drones, self.cost_matrix, self.dist_matrix, None
        )
        history: List[Dict[str, Any]] = []

        for gen in range(1, self.generations + 1):
            evaluated = [
                (
                    chrom,
                    decode_and_evaluate(
                        chrom, self.camps, self.drones, self.cost_matrix, self.dist_matrix, None
                    ),
                )
                for chrom in population
            ]
            evaluated.sort(key=lambda item: item[1]["objective"])

            if evaluated[0][1]["objective"] < best_eval["objective"]:
                best_chrom = list(evaluated[0][0])
                best_eval = evaluated[0][1]

            mean_obj = sum(e["objective"] for _, e in evaluated) / len(evaluated)
            history.append(
                {
                    "gen": gen,
                    "best_objective": round(best_eval["objective"], 2),
                    "mean_objective": round(mean_obj, 2),
                    "total_distance_km": best_eval["total_distance_km"],
                    "makespan_min": best_eval["makespan_min"],
                    "on_time_pct": best_eval["on_time_pct"],
                }
            )

            # Elitism = 2
            new_pop: List[List[int]] = [list(evaluated[0][0]), list(evaluated[1][0])]
            while len(new_pop) < self.pop_size:
                k = min(3, len(evaluated))
                p1 = min(self.rng.sample(evaluated, k), key=lambda x: x[1]["objective"])[0]
                p2 = min(self.rng.sample(evaluated, k), key=lambda x: x[1]["objective"])[0]
                child = _order_crossover(p1, p2, self.rng)
                if self.rng.random() < self.mutation_rate:
                    child = _mutate_chromosome(child, self.rng)
                new_pop.append(child)
            population = new_pop

        final_eval = decode_and_evaluate(
            best_chrom,
            self.camps,
            self.drones,
            self.cost_matrix,
            self.dist_matrix,
            self.path_matrix,
        )
        return {
            "algorithm": "ga",
            "label": "Genetic Algorithm",
            "best_chromosome": best_chrom,
            "evaluation": final_eval,
            "history": history,
            "runtime_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        }


class SimulatedAnnealingOptimizer:
    """Simulated Annealing comparative Local Search optimizer for VRPTW-BL."""

    def __init__(
        self,
        camps: List[Camp],
        drones: List[DroneSpec],
        cost_matrix: Dict[Tuple[int, int], float],
        dist_matrix: Dict[Tuple[int, int], float],
        path_matrix: Optional[Dict[Tuple[int, int], List[Tuple[int, int]]]] = None,
        generations: int = 80,
        steps_per_checkpoint: int = 20,
        seed: int = 42,
    ):
        self.camps = camps
        self.drones = drones
        self.cost_matrix = cost_matrix
        self.dist_matrix = dist_matrix
        self.path_matrix = path_matrix
        self.generations = max(5, generations)
        self.steps_per_checkpoint = max(5, steps_per_checkpoint)
        self.rng = random.Random(seed + 101)

    def run(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        if not self.camps:
            empty_eval = decode_and_evaluate(
                [], self.camps, self.drones, self.cost_matrix, self.dist_matrix, self.path_matrix
            )
            return {
                "algorithm": "sa",
                "label": "Simulated Annealing",
                "best_chromosome": [],
                "evaluation": empty_eval,
                "history": [],
                "runtime_ms": 0.0,
            }

        camp_genes = list(range(len(self.camps)))
        delimiters = [-100 - d for d in range(max(0, len(self.drones) - 1))]
        current = camp_genes + delimiters
        self.rng.shuffle(current)

        curr_eval = decode_and_evaluate(
            current, self.camps, self.drones, self.cost_matrix, self.dist_matrix, None
        )
        best_chrom = list(current)
        best_eval = curr_eval

        total_steps = self.generations * self.steps_per_checkpoint
        temp = 35.0
        cooling = (0.05 / temp) ** (1.0 / max(total_steps, 1))
        history: List[Dict[str, Any]] = []

        for gen in range(1, self.generations + 1):
            for _ in range(self.steps_per_checkpoint):
                candidate = _mutate_chromosome(current, self.rng)
                cand_eval = decode_and_evaluate(
                    candidate, self.camps, self.drones, self.cost_matrix, self.dist_matrix, None
                )
                delta = cand_eval["objective"] - curr_eval["objective"]
                if delta <= 0 or self.rng.random() < math.exp(-delta / max(temp, 1e-6)):
                    current = candidate
                    curr_eval = cand_eval
                    if curr_eval["objective"] < best_eval["objective"]:
                        best_chrom = list(current)
                        best_eval = curr_eval
                temp *= cooling

            history.append(
                {
                    "gen": gen,
                    "best_objective": round(best_eval["objective"], 2),
                    "mean_objective": round(curr_eval["objective"], 2),
                    "total_distance_km": best_eval["total_distance_km"],
                    "makespan_min": best_eval["makespan_min"],
                    "on_time_pct": best_eval["on_time_pct"],
                }
            )

        final_eval = decode_and_evaluate(
            best_chrom,
            self.camps,
            self.drones,
            self.cost_matrix,
            self.dist_matrix,
            self.path_matrix,
        )
        return {
            "algorithm": "sa",
            "label": "Simulated Annealing",
            "best_chromosome": best_chrom,
            "evaluation": final_eval,
            "history": history,
            "runtime_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        }
