"""
AeroRelief 2.5D AI Simulation & Optimization Engine
Implements PRD.md:
- 2.5D Grid Environment (up to 100x100) with metric scaling & elevation penalties
- Fast A* 2.5D pathfinding & single-source multi-target matrix computation
- Dynamic Obstacles: Moving Weather Storm Cell & Spreading Wildfire (Karhutla)
- Multi-Depot VRPTW-BL Genetic Algorithm (Battery, Payload, Time Windows, Urgency)
- Real-Time Step Simulation with Event-Driven Re-routing & Drone Telemetry
"""

from __future__ import annotations

import heapq
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

SQRT2 = math.sqrt(2.0)

URGENCY_WEIGHTS = {
    "CRITICAL": 3.0,
    "HIGH": 2.0,
    "NORMAL": 1.0,
}


@dataclass
class Depot:
    id: int
    name: str
    position: Tuple[int, int]


@dataclass
class DisasterCamp:
    id: int
    name: str
    position: Tuple[int, int]
    demand_kg: float = 2.0
    urgency: str = "HIGH"  # CRITICAL | HIGH | NORMAL
    time_window_end_min: float = 45.0
    status: str = "Pending"  # Pending | In Transit | Delivered On-Time | Delivered Late | Unreachable
    delivered_at_min: Optional[float] = None


@dataclass
class DroneConfig:
    id: int
    home_depot_id: int
    max_battery_wh: float = 350.0
    max_payload_kg: float = 8.0
    speed_mps: float = 18.0
    climb_penalty_factor: float = 2.5
    descent_penalty_factor: float = 0.4
    base_wh_per_km: float = 18.0
    climb_wh_per_10m: float = 2.2


@dataclass
class WeatherStormCell:
    id: int
    name: str
    center: Tuple[float, float]
    core_radius: float = 3.0
    turbulence_radius: float = 6.0
    velocity: Tuple[float, float] = (0.35, 0.20)  # grid cells per minute
    penalty_multiplier: float = 1.85
    active: bool = True

    def step(self, dt_min: float, width: int, height: int) -> None:
        if not self.active:
            return
        nx = self.center[0] + self.velocity[0] * dt_min
        ny = self.center[1] + self.velocity[1] * dt_min
        # Bounce gently within outer bounds so storm stays observable in scenario
        vx, vy = self.velocity
        if nx < 1 or nx > width - 2:
            vx = -vx
            nx = max(1.0, min(float(width - 2), nx))
        if ny < 1 or ny > height - 2:
            vy = -vy
            ny = max(1.0, min(float(height - 2), ny))
        self.center = (nx, ny)
        self.velocity = (vx, vy)


@dataclass
class WildfireHazard:
    id: int
    name: str
    active_fire_cells: Set[Tuple[int, int]] = field(default_factory=set)
    burned_cells: Set[Tuple[int, int]] = field(default_factory=set)
    fire_age: Dict[Tuple[int, int], float] = field(default_factory=dict)
    base_spread_prob: float = 0.28
    wind_bias: float = 0.45
    slope_bias: float = 0.25
    burn_duration_min: float = 8.0
    spread_interval_min: float = 1.0
    max_active_cells: int = 18
    max_burned_cells: int = 36
    move_dir_x: float = 1.0  # +1.0 moves right, -1.0 moves left
    time_since_last_spread: float = 0.0
    active: bool = True
    _burned_order: List[Tuple[int, int]] = field(default_factory=list)

    def _extinguish_cell(self, cell: Tuple[int, int]) -> None:
        if cell in self.active_fire_cells:
            self.active_fire_cells.discard(cell)
            self.fire_age.pop(cell, None)
            if cell not in self.burned_cells:
                self.burned_cells.add(cell)
                self._burned_order.append(cell)
                while len(self._burned_order) > self.max_burned_cells:
                    oldest_burned = self._burned_order.pop(0)
                    self.burned_cells.discard(oldest_burned)

    def ignite_zone(self, x_min: int, x_max: int, y_min: int, y_max: int, width: int, height: int) -> None:
        for y in range(max(0, y_min), min(height, y_max + 1)):
            for x in range(max(0, x_min), min(width, x_max + 1)):
                if len(self.active_fire_cells) >= self.max_active_cells:
                    return
                pos = (x, y)
                if pos not in self.active_fire_cells and pos not in self.burned_cells:
                    self.active_fire_cells.add(pos)
                    self.fire_age[pos] = 0.0

    def step(
        self,
        dt_min: float,
        env: "GridEnvironment25D",
        protected_positions: Set[Tuple[int, int]],
        rng: random.Random,
    ) -> bool:
        """Advance bounded, moving wildfire front (left/right). Returns True if active_fire_cells changed."""
        if not self.active or not self.active_fire_cells:
            return False

        changed = False
        for cell in list(self.active_fire_cells):
            self.fire_age[cell] = self.fire_age.get(cell, 0.0) + dt_min

        # Flip horizontal movement direction when reaching map boundaries
        xs = [c[0] for c in self.active_fire_cells]
        if self.move_dir_x > 0 and max(xs) >= env.width - 2:
            self.move_dir_x = -1.0
        elif self.move_dir_x < 0 and min(xs) <= 1:
            self.move_dir_x = 1.0

        self.time_since_last_spread += dt_min
        if self.time_since_last_spread < self.spread_interval_min:
            return False
        self.time_since_last_spread = 0.0

        dir_x = 1.0 if self.move_dir_x >= 0 else -1.0
        # Collect forward-biased frontier neighbors
        candidates: List[Tuple[float, Tuple[int, int]]] = []
        seen: Set[Tuple[int, int]] = set()
        for x, y in self.active_fire_cells:
            cur_elev = float(env.elevation_grid[y, x])
            for dx, dy in (
                (1, 0), (-1, 0), (0, 1), (0, -1),
                (1, 1), (1, -1), (-1, 1), (-1, -1),
            ):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < env.width and 0 <= ny < env.height):
                    continue
                nxt = (nx, ny)
                if nxt in self.active_fire_cells or nxt in seen:
                    continue
                if env.static_obstacles[ny, nx] or nxt in protected_positions:
                    continue
                seen.add(nxt)

                # Strongly bias advancement along horizontal direction (left or right)
                horiz_align = dx * dir_x
                if horiz_align < 0:
                    continue  # Never march backward unless completely boxed in
                slope = (float(env.elevation_grid[ny, nx]) - cur_elev) / max(10.0, env.cell_size_m * 0.1)
                slope_bonus = 1.0 + self.slope_bias * max(-0.5, min(1.5, slope))
                fresh_bonus = 1.5 if nxt not in self.burned_cells else 0.35
                forward_weight = (2.2 if horiz_align > 0 else 0.7) * slope_bonus * fresh_bonus
                candidates.append((forward_weight + rng.random() * 0.6, nxt))

        # Fallback if boxed in against protected cells/obstacles
        if not candidates:
            self.move_dir_x = -dir_x
            dir_x = self.move_dir_x
            for x, y in self.active_fire_cells:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    nxt = (nx, ny)
                    if (
                        0 <= nx < env.width
                        and 0 <= ny < env.height
                        and nxt not in self.active_fire_cells
                        and not env.static_obstacles[ny, nx]
                        and nxt not in protected_positions
                    ):
                        candidates.append((rng.random(), nxt))

        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            advance_count = min(len(candidates), max(2, self.max_active_cells // 6))
            for _, nxt in candidates[:advance_count]:
                self.burned_cells.discard(nxt)
                self.active_fire_cells.add(nxt)
                self.fire_age[nxt] = 0.0
                changed = True

        # Extinguish trailing / oldest cells so total active fire area stays strictly bounded
        # and the fire patch visibly translates left/right rather than growing forever
        target_cap = max(4, self.max_active_cells)
        min_core = max(4, target_cap // 2)
        trailing_sorted = sorted(
            self.active_fire_cells,
            key=lambda c: (c[0] * dir_x, -self.fire_age.get(c, 0.0)),
        )
        for cell in trailing_sorted:
            if len(self.active_fire_cells) > target_cap:
                self._extinguish_cell(cell)
                changed = True
            elif len(self.active_fire_cells) > min_core and self.fire_age.get(cell, 0.0) >= self.burn_duration_min:
                self._extinguish_cell(cell)
                changed = True
            else:
                break

        return changed


class GridEnvironment25D:
    """2.5D disaster grid (max 100x100) with elevation, wind, static NFZ, storms, and wildfires."""

    def __init__(
        self,
        width: int = 40,
        height: int = 40,
        cell_size_m: float = 250.0,
        max_altitude_m: float = 160.0,
        wind_vector: Tuple[float, float, float] = (1.0, 0.5, 8.0),
    ):
        self.width = max(10, min(100, int(width)))
        self.height = max(10, min(100, int(height)))
        self.cell_size_m = float(cell_size_m)
        self.max_altitude_m = float(max_altitude_m)
        self.wind_vector = wind_vector  # (dx, dy, speed_mps)

        self.elevation_grid = np.zeros((self.height, self.width), dtype=np.float32)
        self.static_obstacles = np.zeros((self.height, self.width), dtype=bool)
        self.storms: List[WeatherStormCell] = []
        self.wildfires: List[WildfireHazard] = []

        self._passable_flat: Optional[np.ndarray] = None
        self._penalty_flat: Optional[np.ndarray] = None
        self._elev_flat: Optional[np.ndarray] = None
        self._dirty = True

    def mark_dirty(self) -> None:
        self._dirty = True

    @staticmethod
    def _perlin_octave(height: int, width: int, res_y: int, res_x: int, rng: np.random.Generator) -> np.ndarray:
        """Vectorized 2D gradient Perlin noise for a single octave."""
        angles = rng.uniform(0.0, 2.0 * math.pi, size=(res_y + 1, res_x + 1))
        grad_x = np.cos(angles)
        grad_y = np.sin(angles)

        ys = np.linspace(0.0, float(res_y), height, endpoint=False)
        xs = np.linspace(0.0, float(res_x), width, endpoint=False)
        yg, xg = np.meshgrid(ys, xs, indexing="ij")

        x0 = np.floor(xg).astype(np.int32)
        y0 = np.floor(yg).astype(np.int32)
        xf = xg - x0
        yf = yg - y0

        # Quintic fade curve 6t^5 - 15t^4 + 10t^3
        u = xf * xf * xf * (xf * (xf * 6.0 - 15.0) + 10.0)
        v = yf * yf * yf * (yf * (yf * 6.0 - 15.0) + 10.0)

        n00 = grad_x[y0, x0] * xf + grad_y[y0, x0] * yf
        n10 = grad_x[y0, x0 + 1] * (xf - 1.0) + grad_y[y0, x0 + 1] * yf
        n01 = grad_x[y0 + 1, x0] * xf + grad_y[y0 + 1, x0] * (yf - 1.0)
        n11 = grad_x[y0 + 1, x0 + 1] * (xf - 1.0) + grad_y[y0 + 1, x0 + 1] * (yf - 1.0)

        nx0 = n00 * (1.0 - u) + n10 * u
        nx1 = n01 * (1.0 - u) + n11 * u
        return nx0 * (1.0 - v) + nx1 * v

    def set_elevation_perlin(
        self,
        seed: int = 42,
        max_terrain_m: float = 160.0,
        octaves: int = 3,
        persistence: float = 0.5,
    ) -> None:
        """Generates a multi-octave 2D Perlin noise elevation map quantized to 10m altitude steps."""
        rng = np.random.default_rng(int(seed))
        total = np.zeros((self.height, self.width), dtype=np.float64)
        amplitude = 1.0
        max_amp = 0.0
        base_res = 3

        for oct_idx in range(octaves):
            freq = 2 ** oct_idx
            res_x = max(2, base_res * freq)
            res_y = max(2, base_res * freq)
            total += amplitude * self._perlin_octave(self.height, self.width, res_y, res_x, rng)
            max_amp += amplitude
            amplitude *= persistence

        total /= max(1e-9, max_amp)
        lo, hi = float(total.min()), float(total.max())
        norm = (total - lo) / max(1e-9, hi - lo)
        # Apply slight power curve so lowlands/valleys are navigable while peaks stand out
        elev = (norm ** 1.15) * max_terrain_m
        self.elevation_grid = (np.round(elev / 10.0) * 10.0).astype(np.float32)
        self._dirty = True

    def add_static_obstacle_zone(self, x_min: int, x_max: int, y_min: int, y_max: int) -> None:
        x0, x1 = max(0, int(x_min)), min(self.width - 1, int(x_max))
        y0, y1 = max(0, int(y_min)), min(self.height - 1, int(y_max))
        if x0 <= x1 and y0 <= y1:
            self.static_obstacles[y0 : y1 + 1, x0 : x1 + 1] = True
            self._dirty = True

    def add_storm(self, storm: WeatherStormCell) -> None:
        self.storms.append(storm)
        self._dirty = True

    def add_wildfire(self, fire: WildfireHazard) -> None:
        self.wildfires.append(fire)
        self._dirty = True

    def clear_protected_entities(
        self,
        depots: List[Depot],
        camps: List[DisasterCamp],
        max_depot_elev: float,
        max_camp_elev: float,
    ) -> None:
        """Clears static obstacles, active wildfire, and excessive elevation at depots and camps."""
        for pos, cap in (
            *((d.position, max_depot_elev) for d in depots),
            *((c.position, max_camp_elev) for c in camps),
        ):
            self.static_obstacles[pos[1], pos[0]] = False
            self.elevation_grid[pos[1], pos[0]] = min(self.elevation_grid[pos[1], pos[0]], cap)
            for f in self.wildfires:
                f.active_fire_cells.discard(pos)
        self._dirty = True

    def _rebuild_caches(self) -> None:
        passable = (~self.static_obstacles) & (self.elevation_grid <= self.max_altitude_m)
        penalty = np.ones((self.height, self.width), dtype=np.float32)

        if self.storms:
            yy, xx = np.mgrid[0 : self.height, 0 : self.width]
            for storm in self.storms:
                if not storm.active:
                    continue
                dist2 = (xx - storm.center[0]) ** 2 + (yy - storm.center[1]) ** 2
                passable &= dist2 > (storm.core_radius ** 2)
                turb_mask = (dist2 <= (storm.turbulence_radius ** 2)) & (dist2 > (storm.core_radius ** 2))
                penalty = np.where(turb_mask, np.maximum(penalty, storm.penalty_multiplier), penalty)

        for fire in self.wildfires:
            if not fire.active:
                continue
            for fx, fy in fire.active_fire_cells:
                if 0 <= fx < self.width and 0 <= fy < self.height:
                    passable[fy, fx] = False

        self._passable_flat = passable.ravel()
        self._penalty_flat = penalty.ravel()
        self._elev_flat = self.elevation_grid.ravel()
        self._dirty = False

    def ensure_caches(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self._dirty or self._passable_flat is None:
            self._rebuild_caches()
        assert self._passable_flat is not None and self._penalty_flat is not None and self._elev_flat is not None
        return self._passable_flat, self._penalty_flat, self._elev_flat

    def is_passable(self, pos: Tuple[int, int]) -> bool:
        x, y = pos
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        passable_flat, _, _ = self.ensure_caches()
        return bool(passable_flat[y * self.width + x])

    def step_dynamic_obstacles(
        self,
        dt_min: float,
        protected_positions: Set[Tuple[int, int]],
        rng: random.Random,
    ) -> bool:
        changed = False
        for storm in self.storms:
            if storm.active:
                storm.step(dt_min, self.width, self.height)
                changed = True
        for fire in self.wildfires:
            if fire.step(dt_min, self, protected_positions, rng):
                changed = True
        if changed:
            self._dirty = True
        return changed


def _build_neighbor_offsets(width: int, cell_size_m: float) -> List[Tuple[int, int, int, float]]:
    return [
        (1, 0, 1, cell_size_m),
        (-1, 0, -1, cell_size_m),
        (0, 1, width, cell_size_m),
        (0, -1, -width, cell_size_m),
        (1, 1, width + 1, cell_size_m * SQRT2),
        (1, -1, -width + 1, cell_size_m * SQRT2),
        (-1, 1, width - 1, cell_size_m * SQRT2),
        (-1, -1, -width - 1, cell_size_m * SQRT2),
    ]


def astar_25d(
    env: GridEnvironment25D,
    start: Tuple[int, int],
    goal: Tuple[int, int],
    climb_penalty: float = 2.5,
    descent_penalty: float = 0.4,
) -> Tuple[Optional[List[Tuple[int, int]]], float, float]:
    """
    Fast flat-indexed 2.5D A* search.
    Returns (path_coords, weighted_cost_m, physical_dist_m).
    """
    if start == goal:
        return [start], 0.0, 0.0
    if not env.is_passable(start) or not env.is_passable(goal):
        return None, float("inf"), float("inf")

    w, h = env.width, env.height
    total_cells = w * h
    passable, penalty, elev = env.ensure_caches()

    s_idx = start[1] * w + start[0]
    g_idx = goal[1] * w + goal[0]
    gx, gy = goal

    g_score = [float("inf")] * total_cells
    phys_dist = [float("inf")] * total_cells
    came_from = [-1] * total_cells
    closed = [False] * total_cells

    g_score[s_idx] = 0.0
    phys_dist[s_idx] = 0.0
    h0 = math.hypot(start[0] - gx, start[1] - gy) * env.cell_size_m
    open_heap: List[Tuple[float, int]] = [(h0, s_idx)]

    offsets = _build_neighbor_offsets(w, env.cell_size_m)
    cell_m = env.cell_size_m

    while open_heap:
        _, cur = heapq.heappop(open_heap)
        if closed[cur]:
            continue
        if cur == g_idx:
            path: List[Tuple[int, int]] = []
            c = cur
            while c != -1:
                path.append((c % w, c // w))
                c = came_from[c]
            path.reverse()
            return path, g_score[g_idx], phys_dist[g_idx]

        closed[cur] = True
        cx = cur % w
        cy = cur // w
        c_elev = float(elev[cur])
        c_g = g_score[cur]
        c_phys = phys_dist[cur]

        for dx, dy, off, step_m in offsets:
            nx = cx + dx
            ny = cy + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            n_idx = cur + off
            if closed[n_idx] or not passable[n_idx]:
                continue

            dz = float(elev[n_idx]) - c_elev
            vert_pen = climb_penalty * dz if dz > 0.0 else descent_penalty * (-dz)
            step_cost = step_m * float(penalty[n_idx]) + vert_pen
            tentative_g = c_g + step_cost

            if tentative_g < g_score[n_idx]:
                g_score[n_idx] = tentative_g
                phys_dist[n_idx] = c_phys + step_m
                came_from[n_idx] = cur
                # Admissible horizontal Euclidean metric
                f = tentative_g + math.hypot(nx - gx, ny - gy) * cell_m
                heapq.heappush(open_heap, (f, n_idx))

    return None, float("inf"), float("inf")


def compute_route_matrix(
    env: GridEnvironment25D,
    points: Dict[str, Tuple[int, int]],
    climb_penalty: float = 2.5,
    descent_penalty: float = 0.4,
) -> Tuple[Dict[Tuple[str, str], float], Dict[Tuple[str, str], float], Dict[Tuple[str, str], List[Tuple[int, int]]]]:
    """
    Computes directional cost, physical distance, and waypoint paths between all named points
    using N single-source multi-target Dijkstra searches (fast even on 100x100 grids).
    """
    cost_matrix: Dict[Tuple[str, str], float] = {}
    dist_matrix: Dict[Tuple[str, str], float] = {}
    paths: Dict[Tuple[str, str], List[Tuple[int, int]]] = {}

    keys = list(points.keys())
    w, h = env.width, env.height
    total_cells = w * h
    passable, penalty, elev = env.ensure_caches()
    offsets = _build_neighbor_offsets(w, env.cell_size_m)

    for src_key in keys:
        sx, sy = points[src_key]
        s_idx = sy * w + sx
        cost_matrix[(src_key, src_key)] = 0.0
        dist_matrix[(src_key, src_key)] = 0.0
        paths[(src_key, src_key)] = [(sx, sy)]

        target_indices = {
            points[dst][1] * w + points[dst][0]
            for dst in keys
            if dst != src_key and env.is_passable(points[dst])
        }
        if not env.is_passable((sx, sy)) or not target_indices:
            for dst in keys:
                if dst != src_key:
                    cost_matrix[(src_key, dst)] = float("inf")
                    dist_matrix[(src_key, dst)] = float("inf")
                    paths[(src_key, dst)] = []
            continue

        g_score = [float("inf")] * total_cells
        phys_dist = [float("inf")] * total_cells
        came_from = [-1] * total_cells
        closed = [False] * total_cells

        g_score[s_idx] = 0.0
        phys_dist[s_idx] = 0.0
        heap: List[Tuple[float, int]] = [(0.0, s_idx)]
        remaining = set(target_indices)

        while heap and remaining:
            _, cur = heapq.heappop(heap)
            if closed[cur]:
                continue
            closed[cur] = True
            remaining.discard(cur)
            if not remaining:
                break

            cx = cur % w
            cy = cur // w
            c_elev = float(elev[cur])
            c_g = g_score[cur]
            c_phys = phys_dist[cur]

            for dx, dy, off, step_m in offsets:
                nx = cx + dx
                ny = cy + dy
                if not (0 <= nx < w and 0 <= ny < h):
                    continue
                n_idx = cur + off
                if closed[n_idx] or not passable[n_idx]:
                    continue
                dz = float(elev[n_idx]) - c_elev
                vert_pen = climb_penalty * dz if dz > 0.0 else descent_penalty * (-dz)
                tentative_g = c_g + step_m * float(penalty[n_idx]) + vert_pen
                if tentative_g < g_score[n_idx]:
                    g_score[n_idx] = tentative_g
                    phys_dist[n_idx] = c_phys + step_m
                    came_from[n_idx] = cur
                    heapq.heappush(heap, (tentative_g, n_idx))

        for dst_key in keys:
            if dst_key == src_key:
                continue
            dx, dy = points[dst_key]
            d_idx = dy * w + dx
            if g_score[d_idx] == float("inf"):
                cost_matrix[(src_key, dst_key)] = float("inf")
                dist_matrix[(src_key, dst_key)] = float("inf")
                paths[(src_key, dst_key)] = []
            else:
                cost_matrix[(src_key, dst_key)] = g_score[d_idx]
                dist_matrix[(src_key, dst_key)] = phys_dist[d_idx]
                p: List[Tuple[int, int]] = []
                c = d_idx
                while c != -1:
                    p.append((c % w, c // w))
                    c = came_from[c]
                p.reverse()
                paths[(src_key, dst_key)] = p

    return cost_matrix, dist_matrix, paths


def estimate_segment_energy_wh(
    path: List[Tuple[int, int]],
    env: GridEnvironment25D,
    drone: DroneConfig,
    carried_payload_kg: float,
) -> float:
    """Estimates Wh energy consumption over a 2.5D path considering climb & payload weight."""
    if len(path) < 2:
        return 0.0
    load_factor = 1.0 + 0.18 * (carried_payload_kg / max(0.1, drone.max_payload_kg))
    horiz_m = 0.0
    climb_m = 0.0
    for i in range(len(path) - 1):
        x1, y1 = path[i]
        x2, y2 = path[i + 1]
        horiz_m += env.cell_size_m * (SQRT2 if (x1 != x2 and y1 != y2) else 1.0)
        dz = float(env.elevation_grid[y2, x2] - env.elevation_grid[y1, x1])
        if dz > 0.0:
            climb_m += dz
    return (horiz_m / 1000.0) * drone.base_wh_per_km * load_factor + (climb_m / 10.0) * drone.climb_wh_per_10m


class MultiDepotVRPTWGA:
    """
    Genetic Algorithm solving Multi-Depot Vehicle Routing with Time Windows,
    Payload Capacity, and Battery Limits (VRPTW-BL).
    """

    def __init__(
        self,
        env: GridEnvironment25D,
        depots: List[Depot],
        camps: List[DisasterCamp],
        drones: List[DroneConfig],
        cost_matrix: Dict[Tuple[str, str], float],
        dist_matrix: Dict[Tuple[str, str], float],
        paths: Dict[Tuple[str, str], List[Tuple[int, int]]],
        pop_size: int = 50,
        generations: int = 70,
        alpha: float = 1.0,
        beta: float = 2.5,
        gamma: float = 15.0,
        service_time_min: float = 1.5,
        seed: int = 42,
    ):
        self.env = env
        self.depots = {d.id: d for d in depots}
        self.camps = {c.id: c for c in camps}
        self.drones = drones
        self.cost_matrix = cost_matrix
        self.dist_matrix = dist_matrix
        self.paths = paths
        self.pop_size = pop_size
        self.generations = generations
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.service_time_min = service_time_min
        self.rng = random.Random(seed)

        # Pre-filter reachable camps (reachable from at least one depot)
        self.reachable_camp_ids: List[int] = []
        self.unreachable_camp_ids: List[int] = []
        for c in camps:
            ck = f"C{c.id}"
            can_reach = any(
                self.cost_matrix.get((f"D{d.id}", ck), float("inf")) < float("inf")
                and self.cost_matrix.get((ck, f"D{d.id}"), float("inf")) < float("inf")
                for d in depots
            )
            if can_reach:
                self.reachable_camp_ids.append(c.id)
            else:
                self.unreachable_camp_ids.append(c.id)

        # Cache segment energies at zero/full load approximations for fast GA fitness
        self._seg_base_wh: Dict[Tuple[str, str], float] = {}
        if drones:
            ref_drone = drones[0]
            for k, p in paths.items():
                self._seg_base_wh[k] = estimate_segment_energy_wh(p, env, ref_drone, 0.0)

    def _decode_routes(self, permutation: List[int]) -> Dict[int, List[int]]:
        """
        Greedily splits permutation across drones while respecting home depot proximity,
        payload limits, and battery limits where possible.
        """
        routes: Dict[int, List[int]] = {d.id: [] for d in self.drones}
        if not self.drones or not permutation:
            return routes

        drone_loads = {d.id: 0.0 for d in self.drones}
        drone_energy = {d.id: 0.0 for d in self.drones}
        drone_last_key = {d.id: f"D{d.home_depot_id}" for d in self.drones}

        for cid in permutation:
            camp = self.camps[cid]
            ck = f"C{cid}"
            best_drone_id = None
            best_score = float("inf")

            for d in self.drones:
                last_k = drone_last_key[d.id]
                home_k = f"D{d.home_depot_id}"
                seg_cost = self.cost_matrix.get((last_k, ck), float("inf"))
                ret_cost = self.cost_matrix.get((ck, home_k), float("inf"))
                if seg_cost == float("inf") or ret_cost == float("inf"):
                    continue

                seg_wh = self._seg_base_wh.get((last_k, ck), 0.0)
                ret_wh = self._seg_base_wh.get((ck, home_k), 0.0)
                new_load = drone_loads[d.id] + camp.demand_kg
                proj_energy = drone_energy[d.id] + seg_wh + ret_wh

                penalty = 0.0
                if new_load > d.max_payload_kg:
                    penalty += 10000.0 * (new_load - d.max_payload_kg)
                if proj_energy > d.max_battery_wh:
                    penalty += 5000.0 * (proj_energy - d.max_battery_wh)

                # Prefer drones whose home depot / current position is closer & balanced
                score = seg_cost + penalty + len(routes[d.id]) * 50.0
                if score < best_score:
                    best_score = score
                    best_drone_id = d.id

            if best_drone_id is None:
                best_drone_id = self.drones[0].id

            last_k = drone_last_key[best_drone_id]
            routes[best_drone_id].append(cid)
            drone_loads[best_drone_id] += camp.demand_kg
            drone_energy[best_drone_id] += self._seg_base_wh.get((last_k, ck), 0.0)
            drone_last_key[best_drone_id] = ck

        return routes

    def evaluate(self, permutation: List[int]) -> Tuple[float, Dict[int, List[int]], Dict[str, float]]:
        routes = self._decode_routes(permutation)
        total_dist_m = 0.0
        total_energy_wh = 0.0
        late_penalty = 0.0
        violation_penalty = 0.0

        for d in self.drones:
            cids = routes[d.id]
            if not cids:
                continue

            home_k = f"D{d.home_depot_id}"
            route_payload = sum(self.camps[c].demand_kg for c in cids)
            if route_payload > d.max_payload_kg:
                violation_penalty += (route_payload - d.max_payload_kg) * 80.0

            cur_payload = route_payload
            elapsed_min = 0.0
            route_energy = 0.0
            prev_k = home_k

            for cid in cids:
                ck = f"C{cid}"
                d_m = self.dist_matrix.get((prev_k, ck), float("inf"))
                if d_m == float("inf"):
                    violation_penalty += 5000.0
                    break
                total_dist_m += d_m
                elapsed_min += (d_m / max(1.0, d.speed_mps)) / 60.0

                camp = self.camps[cid]
                late_min = max(0.0, elapsed_min - camp.time_window_end_min)
                late_penalty += late_min * URGENCY_WEIGHTS.get(camp.urgency, 1.0)
                elapsed_min += self.service_time_min

                seg_path = self.paths.get((prev_k, ck), [])
                route_energy += estimate_segment_energy_wh(seg_path, self.env, d, cur_payload)
                cur_payload = max(0.0, cur_payload - camp.demand_kg)
                prev_k = ck

            # Return to home depot
            ret_m = self.dist_matrix.get((prev_k, home_k), float("inf"))
            if ret_m == float("inf"):
                violation_penalty += 5000.0
            else:
                total_dist_m += ret_m
                ret_path = self.paths.get((prev_k, home_k), [])
                route_energy += estimate_segment_energy_wh(ret_path, self.env, d, 0.0)

            total_energy_wh += route_energy
            if route_energy > d.max_battery_wh:
                violation_penalty += (route_energy - d.max_battery_wh) * 15.0

        raw_cost = (
            self.alpha * (total_dist_m / 1000.0 + total_energy_wh * 0.1)
            + self.beta * late_penalty
            + self.gamma * violation_penalty
        )
        fitness = 1.0 / (raw_cost + 1e-6)
        metrics = {
            "total_dist_km": total_dist_m / 1000.0,
            "total_energy_wh": total_energy_wh,
            "late_penalty": late_penalty,
            "violation_penalty": violation_penalty,
            "raw_cost": raw_cost,
        }
        return fitness, routes, metrics

    def run(self) -> Tuple[Dict[int, List[int]], Dict[str, float]]:
        cids = list(self.reachable_camp_ids)
        if not cids or not self.drones:
            return {d.id: [] for d in self.drones}, {
                "total_dist_km": 0.0,
                "total_energy_wh": 0.0,
                "late_penalty": 0.0,
                "violation_penalty": 0.0,
                "raw_cost": 0.0,
            }

        if len(cids) == 1:
            _, routes, metrics = self.evaluate(cids)
            return routes, metrics

        # Seed population with urgency-sorted heuristics + random permutations
        urgency_sorted = sorted(
            cids,
            key=lambda cid: (self.camps[cid].time_window_end_min, -URGENCY_WEIGHTS.get(self.camps[cid].urgency, 1.0)),
        )
        population: List[List[int]] = [urgency_sorted]
        while len(population) < self.pop_size:
            population.append(self.rng.sample(cids, len(cids)))

        best_perm = urgency_sorted
        best_fit, best_routes, best_metrics = self.evaluate(best_perm)

        for _ in range(self.generations):
            scored = []
            for chrom in population:
                fit, r, m = self.evaluate(chrom)
                scored.append((fit, chrom, r, m))
                if fit > best_fit:
                    best_fit, best_perm, best_routes, best_metrics = fit, list(chrom), r, m

            new_pop: List[List[int]] = [list(best_perm)]
            while len(new_pop) < self.pop_size:
                t1 = self.rng.sample(scored, min(3, len(scored)))
                t2 = self.rng.sample(scored, min(3, len(scored)))
                p1 = max(t1, key=lambda x: x[0])[1]
                p2 = max(t2, key=lambda x: x[0])[1]

                # Order Crossover (OX)
                cut1, cut2 = sorted(self.rng.sample(range(len(cids)), 2))
                child = [-1] * len(cids)
                child[cut1 : cut2 + 1] = p1[cut1 : cut2 + 1]
                used = set(child[cut1 : cut2 + 1])
                fill_pos = 0
                for item in p2:
                    if item not in used:
                        while child[fill_pos] != -1:
                            fill_pos += 1
                        child[fill_pos] = item

                # Swap / Inversion Mutation
                if self.rng.random() < 0.25:
                    i, j = sorted(self.rng.sample(range(len(cids)), 2))
                    if self.rng.random() < 0.5:
                        child[i], child[j] = child[j], child[i]
                    else:
                        child[i : j + 1] = reversed(child[i : j + 1])
                new_pop.append(child)

            population = new_pop

        return best_routes, best_metrics


@dataclass
class DroneRuntimeState:
    drone_id: int
    home_depot_id: int
    current_pos: Tuple[int, int]
    remaining_battery_wh: float
    max_battery_wh: float
    current_payload_kg: float
    max_payload_kg: float
    assigned_camp_ids: List[int]
    current_target_key: Optional[str] = None
    active_waypoints: List[Tuple[int, int]] = field(default_factory=list)
    waypoint_idx: int = 0
    progress_accum_m: float = 0.0
    state: str = "Standby"  # Standby | Stay at Depot | Stay at Posko | Flying | Re-routing | Returning | Low Battery | Out of Battery | Completed
    eta_min: float = 0.0
    reroute_count: int = 0
    trail: List[Tuple[int, int]] = field(default_factory=list)
    planned_full_path: List[Tuple[int, int]] = field(default_factory=list)

    @property
    def remaining_battery_pct(self) -> float:
        return max(0.0, min(100.0, 100.0 * self.remaining_battery_wh / max(1.0, self.max_battery_wh)))


class AeroReliefSimulator:
    """Step-based simulation engine managing live drone flights, weather drift, wildfire spread & A* re-routing."""

    def __init__(
        self,
        env: GridEnvironment25D,
        depots: List[Depot],
        camps: List[DisasterCamp],
        drones: List[DroneConfig],
        routes: Dict[int, List[int]],
        initial_paths: Dict[Tuple[str, str], List[Tuple[int, int]]],
        seed: int = 42,
    ):
        self.env = env
        self.depots = {d.id: d for d in depots}
        self.camps = {
            c.id: DisasterCamp(
                id=c.id,
                name=c.name,
                position=c.position,
                demand_kg=c.demand_kg,
                urgency=c.urgency,
                time_window_end_min=c.time_window_end_min,
                status="Pending",
            )
            for c in camps
        }
        self.drones_cfg = {d.id: d for d in drones}
        self._initial_paths = initial_paths
        self.rng = random.Random(seed)
        self.sim_time_min: float = 0.0
        self.events: List[str] = []
        self.drone_states: Dict[int, DroneRuntimeState] = {}

        for d in drones:
            home_pos = self.depots[d.home_depot_id].position
            assigned = list(routes.get(d.id, []))
            total_load = sum(self.camps[cid].demand_kg for cid in assigned)

            full_path: List[Tuple[int, int]] = []
            first_target: Optional[str] = None
            first_wp: List[Tuple[int, int]] = []
            state_str = "Standby"

            if assigned:
                cand_first = f"C{assigned[0]}"
                cand_wp = list(initial_paths.get((f"D{d.home_depot_id}", cand_first), []))
                ret_wp = list(initial_paths.get((cand_first, f"D{d.home_depot_id}"), []))
                first_wh = estimate_segment_energy_wh(cand_wp, env, d, total_load) if cand_wp else float("inf")
                after_drop_load = max(0.0, total_load - self.camps[assigned[0]].demand_kg)
                ret_wh = estimate_segment_energy_wh(ret_wp, env, d, after_drop_load) if ret_wp else float("inf")

                if not cand_wp or not ret_wp or (first_wh + ret_wh) > d.max_battery_wh:
                    # Estimated energy insufficient for first delivery + return: stay at Depot
                    state_str = "Stay at Depot"
                    self.events.append(
                        f"[t=0.0m] Drone #{d.id} memperkirakan baterai ({d.max_battery_wh:.0f} Wh) tidak cukup untuk misi {cand_first} + pulang (~{first_wh + ret_wh:.0f} Wh), stay di Depot."
                    )
                    assigned = []
                    total_load = 0.0
                else:
                    seq = [f"D{d.home_depot_id}"] + [f"C{cid}" for cid in assigned] + [f"D{d.home_depot_id}"]
                    for i in range(len(seq) - 1):
                        seg = initial_paths.get((seq[i], seq[i + 1]), [])
                        if seg:
                            if full_path and full_path[-1] == seg[0]:
                                full_path.extend(seg[1:])
                            else:
                                full_path.extend(seg)
                    first_target = cand_first
                    first_wp = cand_wp
                    state_str = "Flying"
                    for cid in assigned:
                        self.camps[cid].status = "In Transit"

            eta = self._compute_eta_min(first_wp, 0, d.speed_mps) if first_wp else 0.0

            self.drone_states[d.id] = DroneRuntimeState(
                drone_id=d.id,
                home_depot_id=d.home_depot_id,
                current_pos=home_pos,
                remaining_battery_wh=d.max_battery_wh,
                max_battery_wh=d.max_battery_wh,
                current_payload_kg=total_load,
                max_payload_kg=d.max_payload_kg,
                assigned_camp_ids=assigned,
                current_target_key=first_target,
                active_waypoints=first_wp,
                waypoint_idx=0,
                state=state_str,
                eta_min=eta,
                trail=[home_pos],
                planned_full_path=full_path,
            )

        # Mark unassigned camps: Pending only if a drone stayed at depot AND at least one depot can reach the camp
        assigned_all = {cid for ds in self.drone_states.values() for cid in ds.assigned_camp_ids}
        stayed_at_depot = any(ds.state == "Stay at Depot" for ds in self.drone_states.values())
        for cid, camp in self.camps.items():
            if cid not in assigned_all:
                has_path = any(
                    initial_paths.get((f"D{d.id}", f"C{cid}")) and initial_paths.get((f"C{cid}", f"D{d.id}"))
                    for d in self.depots.values()
                )
                camp.status = "Pending" if (stayed_at_depot and has_path) else "Unreachable"

        self.events.append(f"[t=0.0m] Simulasi siap: {sum(1 for ds in self.drone_states.values() if ds.assigned_camp_ids)} drone aktif.")

    def _compute_eta_min(self, waypoints: List[Tuple[int, int]], idx: int, speed_mps: float) -> float:
        if not waypoints or idx >= len(waypoints) - 1:
            return 0.0
        dist_m = 0.0
        for i in range(idx, len(waypoints) - 1):
            x1, y1 = waypoints[i]
            x2, y2 = waypoints[i + 1]
            dist_m += self.env.cell_size_m * (SQRT2 if (x1 != x2 and y1 != y2) else 1.0)
        return (dist_m / max(1.0, speed_mps)) / 60.0

    def _target_coords(self, key: str) -> Tuple[int, int]:
        if key.startswith("D"):
            return self.depots[int(key[1:])].position
        return self.camps[int(key[1:])].position

    def _check_and_reroute(self, ds: DroneRuntimeState, cfg: DroneConfig) -> None:
        if not ds.active_waypoints or ds.current_target_key is None:
            return
        remaining_wp = ds.active_waypoints[ds.waypoint_idx :]
        blocked = any(not self.env.is_passable(pt) for pt in remaining_wp)
        if not blocked:
            return

        goal_pos = self._target_coords(ds.current_target_key)
        # If current position was engulfed, step out to nearest passable neighbor
        start_pos = ds.current_pos
        if not self.env.is_passable(start_pos):
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                cand = (start_pos[0] + dx, start_pos[1] + dy)
                if self.env.is_passable(cand):
                    start_pos = cand
                    break

        new_path, _, _ = astar_25d(
            self.env,
            start_pos,
            goal_pos,
            climb_penalty=cfg.climb_penalty_factor,
            descent_penalty=cfg.descent_penalty_factor,
        )

        if new_path is None:
            # Target blocked by fire/storm: mark unreachable if camp, return home
            if ds.current_target_key.startswith("C"):
                cid = int(ds.current_target_key[1:])
                self.camps[cid].status = "Unreachable"
                if cid in ds.assigned_camp_ids:
                    ds.assigned_camp_ids.remove(cid)
                self.events.append(
                    f"[t={self.sim_time_min:.1f}m] {self.camps[cid].name} tertutup halangan, Drone #{ds.drone_id} kembali ke Depot."
                )
            home_k = f"D{ds.home_depot_id}"
            ds.current_target_key = home_k
            ret_path, _, _ = astar_25d(
                self.env, start_pos, self._target_coords(home_k),
                climb_penalty=cfg.climb_penalty_factor, descent_penalty=cfg.descent_penalty_factor
            )
            ds.active_waypoints = ret_path or [start_pos]
            ds.waypoint_idx = 0
            ds.state = "Returning"
            ds.reroute_count += 1
            return

        needed_wh = estimate_segment_energy_wh(new_path, self.env, cfg, ds.current_payload_kg)
        if ds.current_target_key.startswith("C") and needed_wh > ds.remaining_battery_wh * 0.85:
            # Low battery protection: abort remaining camps and return home
            for cid in list(ds.assigned_camp_ids):
                if self.camps[cid].status in ("Pending", "In Transit"):
                    self.camps[cid].status = "Pending"
            ds.assigned_camp_ids.clear()
            home_k = f"D{ds.home_depot_id}"
            ret_path, _, _ = astar_25d(
                self.env, start_pos, self._target_coords(home_k),
                climb_penalty=cfg.climb_penalty_factor, descent_penalty=cfg.descent_penalty_factor
            )
            ds.current_target_key = home_k
            ds.active_waypoints = ret_path or [start_pos]
            ds.waypoint_idx = 0
            ds.state = "Low Battery"
            ds.reroute_count += 1
            self.events.append(
                f"[t={self.sim_time_min:.1f}m] Drone #{ds.drone_id} Low Battery setelah deteksi halangan, kembali ke Depot."
            )
            return

        ds.active_waypoints = new_path
        ds.waypoint_idx = 0
        ds.reroute_count += 1
        ds.state = "Re-routing"
        ds.eta_min = self._compute_eta_min(new_path, 0, cfg.speed_mps)
        self.events.append(
            f"[t={self.sim_time_min:.1f}m] Drone #{ds.drone_id} RE-ROUTING A* menuju {ds.current_target_key} menghindari Cuaca/Api!"
        )

    def _resolve_path(
        self,
        src_key: str,
        dst_key: str,
        src_pos: Tuple[int, int],
        cfg: DroneConfig,
    ) -> Optional[List[Tuple[int, int]]]:
        """Reuses cached initial path if still passable, else runs 2.5D A*."""
        if src_pos == self._target_coords(src_key):
            cached = self._initial_paths.get((src_key, dst_key))
            if cached and all(self.env.is_passable(pt) for pt in cached):
                return list(cached)
        path, _, _ = astar_25d(
            self.env,
            src_pos,
            self._target_coords(dst_key),
            climb_penalty=cfg.climb_penalty_factor,
            descent_penalty=cfg.descent_penalty_factor,
        )
        return path

    def _advance_target(self, ds: DroneRuntimeState, cfg: DroneConfig) -> None:
        if ds.current_target_key is None:
            return
        cur_key = ds.current_target_key
        if cur_key.startswith("C"):
            cid = int(cur_key[1:])
            camp = self.camps[cid]
            camp.delivered_at_min = self.sim_time_min
            if self.sim_time_min <= camp.time_window_end_min:
                camp.status = "Delivered On-Time"
            else:
                camp.status = "Delivered Late"
            ds.current_payload_kg = max(0.0, ds.current_payload_kg - camp.demand_kg)
            self.events.append(
                f"[t={self.sim_time_min:.1f}m] Drone #{ds.drone_id} kirim logistik ke {camp.name} ({camp.status})."
            )
            if cid in ds.assigned_camp_ids:
                ds.assigned_camp_ids.remove(cid)

            home_k = f"D{ds.home_depot_id}"

            if ds.assigned_camp_ids:
                next_cid = ds.assigned_camp_ids[0]
                next_key = f"C{next_cid}"
                path_next = self._resolve_path(cur_key, next_key, ds.current_pos, cfg)
                if path_next is not None:
                    wh_to_next = estimate_segment_energy_wh(path_next, self.env, cfg, ds.current_payload_kg)
                    ret_after_next = self._resolve_path(next_key, home_k, self._target_coords(next_key), cfg)
                    after_load = max(0.0, ds.current_payload_kg - self.camps[next_cid].demand_kg)
                    wh_ret_after = estimate_segment_energy_wh(ret_after_next, self.env, cfg, after_load) if ret_after_next else float("inf")

                    if ret_after_next is not None and (wh_to_next + wh_ret_after) <= ds.remaining_battery_wh:
                        ds.current_target_key = next_key
                        ds.active_waypoints = path_next
                        ds.waypoint_idx = 0
                        ds.state = "Flying"
                        ds.eta_min = self._compute_eta_min(path_next, 0, cfg.speed_mps)
                        return

                    # Estimates cannot continue safely to next camp + return: cancel remaining camps
                    self.events.append(
                        f"[t={self.sim_time_min:.1f}m] Drone #{ds.drone_id} memperkirakan baterai ({ds.remaining_battery_wh:.0f} Wh) tidak cukup lanjut ke {next_key} + pulang (~{wh_to_next + wh_ret_after:.0f} Wh)."
                    )
                else:
                    self.camps[next_cid].status = "Unreachable"
                    ds.assigned_camp_ids.remove(next_cid)

                for rem_cid in list(ds.assigned_camp_ids):
                    if self.camps[rem_cid].status == "In Transit":
                        self.camps[rem_cid].status = "Pending"
                ds.assigned_camp_ids.clear()

            # Try returning to Depot; if estimated energy insufficient or blocked, stay at Posko
            path_home = self._resolve_path(cur_key, home_k, ds.current_pos, cfg)
            wh_home = estimate_segment_energy_wh(path_home, self.env, cfg, ds.current_payload_kg) if path_home else float("inf")
            if path_home is None or wh_home > ds.remaining_battery_wh:
                ds.current_target_key = None
                ds.active_waypoints = []
                ds.waypoint_idx = 0
                ds.eta_min = 0.0
                ds.state = "Stay at Posko"
                self.events.append(
                    f"[t={self.sim_time_min:.1f}m] Drone #{ds.drone_id} memperkirakan tidak cukup energi/jalur ke Depot (~{wh_home:.0f} > {ds.remaining_battery_wh:.0f} Wh), stay di {camp.name}."
                )
            else:
                ds.current_target_key = home_k
                ds.active_waypoints = path_home
                ds.waypoint_idx = 0
                ds.state = "Returning"
                ds.eta_min = self._compute_eta_min(path_home, 0, cfg.speed_mps)
        else:
            # Arrived back at Depot
            ds.current_target_key = None
            ds.active_waypoints = []
            ds.waypoint_idx = 0
            ds.eta_min = 0.0
            ds.state = "Completed"
            self.events.append(f"[t={self.sim_time_min:.1f}m] Drone #{ds.drone_id} kembali selamat ke Depot.")

    def _ground_drone_out_of_battery(self, ds: DroneRuntimeState) -> None:
        """Immediately grounds a drone at 0% battery so it cannot continue flying."""
        if ds.state == "Out of Battery":
            return
        ds.remaining_battery_wh = 0.0
        ds.state = "Out of Battery"
        ds.active_waypoints = []
        ds.current_target_key = None
        ds.eta_min = 0.0
        ds.progress_accum_m = 0.0
        for cid in list(ds.assigned_camp_ids):
            if self.camps[cid].status == "In Transit":
                self.camps[cid].status = "Pending"
        ds.assigned_camp_ids.clear()
        self.events.append(
            f"[t={self.sim_time_min:.1f}m] DARURAT: Drone #{ds.drone_id} kehabisan baterai (0%) di {ds.current_pos} dan berhenti terbang!"
        )

    def is_finished(self) -> bool:
        return all(
            ds.state in ("Standby", "Completed", "Out of Battery", "Stay at Depot", "Stay at Posko")
            for ds in self.drone_states.values()
        )

    def step(self, dt_min: float = 0.5) -> None:
        if self.is_finished():
            return

        self.sim_time_min += dt_min
        protected = {d.position for d in self.depots.values()} | {c.position for c in self.camps.values()}
        obstacles_changed = self.env.step_dynamic_obstacles(dt_min, protected, self.rng)

        for did, ds in self.drone_states.items():
            if ds.state in ("Standby", "Completed", "Out of Battery", "Stay at Depot", "Stay at Posko"):
                continue
            if ds.remaining_battery_wh <= 0.0:
                self._ground_drone_out_of_battery(ds)
                continue

            cfg = self.drones_cfg[did]

            if obstacles_changed:
                self._check_and_reroute(ds, cfg)

            if not ds.active_waypoints or ds.state == "Out of Battery":
                continue

            # Reset transient Re-routing label back to Flying after 1 tick of movement
            if ds.state == "Re-routing":
                ds.state = "Flying"

            ds.progress_accum_m += cfg.speed_mps * dt_min * 60.0
            while ds.waypoint_idx < len(ds.active_waypoints) - 1:
                if ds.remaining_battery_wh <= 0.0:
                    self._ground_drone_out_of_battery(ds)
                    break

                p_cur = ds.active_waypoints[ds.waypoint_idx]
                p_nxt = ds.active_waypoints[ds.waypoint_idx + 1]
                seg_m = self.env.cell_size_m * (SQRT2 if (p_cur[0] != p_nxt[0] and p_cur[1] != p_nxt[1]) else 1.0)
                if ds.progress_accum_m < seg_m:
                    break

                # Calculate battery required for this segment before moving
                _, penalty_flat, elev_flat = self.env.ensure_caches()
                n_idx = p_nxt[1] * self.env.width + p_nxt[0]
                c_idx = p_cur[1] * self.env.width + p_cur[0]
                dz = float(elev_flat[n_idx] - elev_flat[c_idx])
                load_factor = 1.0 + 0.18 * (ds.current_payload_kg / max(0.1, cfg.max_payload_kg))
                turb_factor = float(penalty_flat[n_idx])
                seg_wh = (seg_m / 1000.0) * cfg.base_wh_per_km * load_factor * turb_factor
                if dz > 0.0:
                    seg_wh += (dz / 10.0) * cfg.climb_wh_per_10m

                if ds.remaining_battery_wh <= seg_wh:
                    # Battery hits 0% mid-segment: drone cannot continue flying
                    self._ground_drone_out_of_battery(ds)
                    break

                ds.remaining_battery_wh -= seg_wh
                ds.progress_accum_m -= seg_m
                ds.waypoint_idx += 1
                ds.current_pos = p_nxt
                ds.trail.append(p_nxt)

            if ds.state == "Out of Battery":
                continue

            ds.eta_min = self._compute_eta_min(ds.active_waypoints, ds.waypoint_idx, cfg.speed_mps)

            if ds.waypoint_idx >= len(ds.active_waypoints) - 1:
                ds.progress_accum_m = 0.0
                self._advance_target(ds, cfg)


def _pick_separated_point(
    rng: random.Random,
    x_lo: int,
    x_hi: int,
    y_lo: int,
    y_hi: int,
    occupied_exact: Set[Tuple[int, int]],
    constraints: List[Tuple[List[Tuple[int, int]], float]],
    max_tries: int = 250,
) -> Tuple[int, int]:
    """Picks a grid point respecting minimum separation constraints with progressive relaxation."""
    x_lo_c, x_hi_c = min(x_lo, x_hi), max(x_lo, x_hi)
    y_lo_c, y_hi_c = min(y_lo, y_hi), max(y_lo, y_hi)

    for scale in (1.0, 0.65, 0.35, 0.0):
        for _ in range(max_tries):
            x = rng.randint(x_lo_c, x_hi_c)
            y = rng.randint(y_lo_c, y_hi_c)
            if (x, y) in occupied_exact:
                continue
            if all(
                math.hypot(x - px, y - py) >= min_d * scale
                for pts, min_d in constraints
                for px, py in pts
            ):
                return x, y

    # Deterministic fallback if random sampling was exhausted on very small grids
    for y in range(y_lo_c, y_hi_c + 1):
        for x in range(x_lo_c, x_hi_c + 1):
            if (x, y) not in occupied_exact:
                return x, y
    return x_lo_c, y_lo_c


def generate_random_scenario_layout(
    width: int = 50,
    height: int = 50,
    seed: Optional[int] = None,
    num_depots: int = 2,
    num_camps: int = 8,
    storm_core_radius: Optional[float] = None,
    storm_turb_radius: Optional[float] = None,
) -> Dict[str, object]:
    """Generates randomized, non-overlapping initial placements for depots, camps, storm, and wildfire."""
    rng = random.Random(seed)
    min_dim = min(width, height)
    margin = max(1, min(3, int(round(min_dim * 0.06))))
    x_lo, x_hi = margin, max(margin, width - 1 - margin)
    y_lo, y_hi = margin, max(margin, height - 1 - margin)

    occupied_exact: Set[Tuple[int, int]] = set()
    depot_positions: List[Tuple[int, int]] = []
    camp_positions: List[Tuple[int, int]] = []

    depot_sep = max(4.0, min_dim * 0.35)
    depots: List[Depot] = []
    for i in range(num_depots):
        pos = _pick_separated_point(
            rng, x_lo, x_hi, y_lo, y_hi, occupied_exact, [(depot_positions, depot_sep)]
        )
        occupied_exact.add(pos)
        depot_positions.append(pos)
        depots.append(Depot(id=i + 1, name=f"Depot {i + 1}", position=pos))

    camp_profiles = [
        (2.5, "CRITICAL", 14.0),
        (2.0, "HIGH", 22.0),
        (2.5, "CRITICAL", 16.0),
        (1.5, "NORMAL", 30.0),
        (2.0, "HIGH", 20.0),
        (2.0, "HIGH", 24.0),
        (1.5, "NORMAL", 28.0),
        (2.5, "CRITICAL", 18.0),
    ]
    camp_depot_sep = max(3.0, min_dim * 0.14)
    camp_camp_sep = max(2.5, min_dim * 0.11)
    camps: List[DisasterCamp] = []
    for i in range(num_camps):
        pos = _pick_separated_point(
            rng,
            x_lo,
            x_hi,
            y_lo,
            y_hi,
            occupied_exact,
            [(depot_positions, camp_depot_sep), (camp_positions, camp_camp_sep)],
        )
        occupied_exact.add(pos)
        camp_positions.append(pos)
        demand_kg, urgency, tw_min = camp_profiles[i % len(camp_profiles)]
        suffix = " (Kritis)" if urgency == "CRITICAL" else ""
        camps.append(
            DisasterCamp(
                id=i + 1,
                name=f"Posko {i + 1}{suffix}",
                position=pos,
                demand_kg=demand_kg,
                urgency=urgency,
                time_window_end_min=tw_min,
            )
        )

    core_r = storm_core_radius if storm_core_radius is not None else max(2.0, width * 0.055)
    turb_r = storm_turb_radius if storm_turb_radius is not None else max(4.0, width * 0.11)
    s_margin = min(max(2, int(math.ceil(core_r)) + 1), max(2, min_dim // 3))
    sx_lo, sx_hi = s_margin, max(s_margin, width - 1 - s_margin)
    sy_lo, sy_hi = s_margin, max(s_margin, height - 1 - s_margin)

    all_entities = depot_positions + camp_positions
    storm_pos = _pick_separated_point(
        rng,
        sx_lo,
        sx_hi,
        sy_lo,
        sy_hi,
        occupied_exact,
        [(all_entities, max(core_r + 2.0, turb_r * 0.8))],
    )

    f_margin = min(max(2, int(round(min_dim * 0.06))), max(2, min_dim // 3))
    fx_lo, fx_hi = f_margin, max(f_margin, width - 1 - f_margin)
    fy_lo, fy_hi = f_margin, max(f_margin, height - 1 - f_margin)
    # Wildfire ignites a 3x3 zone around fire_center; keep clear of depots/camps and storm core
    fire_pos = _pick_separated_point(
        rng,
        fx_lo,
        fx_hi,
        fy_lo,
        fy_hi,
        occupied_exact | {storm_pos},
        [(all_entities, 3.5), ([storm_pos], core_r + 3.0)],
    )

    return {
        "depots": depots,
        "camps": camps,
        "storm_center": (float(storm_pos[0]), float(storm_pos[1])),
        "fire_center": fire_pos,
    }


def create_default_scenario(
    width: int = 50,
    height: int = 50,
    cell_size_m: float = 200.0,
    terrain_seed: int = 42,
    num_drones: int = 3,
    wind_vector: Tuple[float, float, float] = (1.0, 0.4, 9.0),
    layout_seed: Optional[int] = None,
) -> Tuple[GridEnvironment25D, List[Depot], List[DisasterCamp], List[DroneConfig]]:
    """Builds a ready-to-run PRD scenario scalable from 10x10 up to 100x100 with randomized initial placement."""
    env = GridEnvironment25D(
        width=width,
        height=height,
        cell_size_m=cell_size_m,
        max_altitude_m=160.0,
        wind_vector=wind_vector,
    )
    env.set_elevation_perlin(seed=terrain_seed, max_terrain_m=160.0)

    core_r = max(2.0, width * 0.055)
    turb_r = max(4.0, width * 0.11)
    layout = generate_random_scenario_layout(
        width=width,
        height=height,
        seed=layout_seed,
        storm_core_radius=core_r,
        storm_turb_radius=turb_r,
    )
    depots: List[Depot] = layout["depots"]  # type: ignore[assignment]
    camps: List[DisasterCamp] = layout["camps"]  # type: ignore[assignment]
    storm_center: Tuple[float, float] = layout["storm_center"]  # type: ignore[assignment]
    fx, fy = layout["fire_center"]  # type: ignore[misc]

    # Static No-Fly Zone disabled per user requirement

    # Moving Bad Weather Storm Cell
    storm = WeatherStormCell(
        id=1,
        name="Badai Utama",
        center=storm_center,
        core_radius=core_r,
        turbulence_radius=turb_r,
        velocity=(wind_vector[0] * 0.45, wind_vector[1] * 0.45),
        penalty_multiplier=1.85,
        active=True,
    )
    env.add_storm(storm)

    # Moving, area-limited Wildfire (Karhutla)
    fire = WildfireHazard(
        id=1,
        name="Karhutla Awal",
        base_spread_prob=0.28,
        wind_bias=0.50,
        slope_bias=0.30,
        burn_duration_min=8.0,
        spread_interval_min=1.0,
        max_active_cells=18,
        max_burned_cells=36,
        move_dir_x=1.0 if wind_vector[0] >= 0 else -1.0,
        active=True,
    )
    fire.ignite_zone(fx - 1, fx + 1, fy - 1, fy + 1, width, height)
    env.add_wildfire(fire)

    # Ensure depots and camps are never blocked by static obstacles or initial fire
    env.clear_protected_entities(depots, camps, max_depot_elev=40.0, max_camp_elev=120.0)

    drones = [
        DroneConfig(
            id=i + 1,
            home_depot_id=depots[i % len(depots)].id,
            max_battery_wh=350.0,
            max_payload_kg=8.0,
            speed_mps=18.0,
            climb_penalty_factor=2.5,
            descent_penalty_factor=0.4,
        )
        for i in range(num_drones)
    ]

    return env, depots, camps, drones
