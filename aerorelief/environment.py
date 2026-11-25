"""Topographic 2D/elevation disaster environment for UAV path planning."""

import math
from typing import Iterable, List, Optional, Set, Tuple
from .models import HazardZone, Hill

Coord = Tuple[int, int]


class TopographicEnvironment:
    """Grid disaster area with elevation terrain and no-fly hazard obstacles."""

    def __init__(
        self,
        width: int = 36,
        height: int = 26,
        hills: Optional[List[Hill]] = None,
        hazard_zones: Optional[List[HazardZone]] = None,
        extra_obstacles: Optional[Iterable[Coord]] = None,
    ):
        self.width = width
        self.height = height
        self.hills = hills or []
        self.hazard_zones = hazard_zones or []
        self.obstacles: Set[Coord] = set()
        self.elevation: List[List[float]] = self._compute_elevation()

        for hz in self.hazard_zones:
            self.add_obstacle_zone(hz.x_min, hz.x_max, hz.y_min, hz.y_max)

        if extra_obstacles:
            for obs in extra_obstacles:
                x, y = int(obs[0]), int(obs[1])
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.obstacles.add((x, y))

    def _compute_elevation(self) -> List[List[float]]:
        grid: List[List[float]] = []
        for y in range(self.height):
            row: List[float] = []
            for x in range(self.width):
                elev = 35.0
                for hill in self.hills:
                    dx = x - hill.cx
                    dy = y - hill.cy
                    dist_sq = dx * dx + dy * dy
                    denom = 2.0 * (hill.radius ** 2)
                    elev += hill.height_m * math.exp(-dist_sq / max(denom, 1e-6))
                row.append(round(min(900.0, elev), 2))
            grid.append(row)
        return grid

    def add_obstacle_zone(self, x_min: int, x_max: int, y_min: int, y_max: int) -> None:
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.obstacles.add((x, y))

    def is_passable(self, pos: Coord) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height and pos not in self.obstacles

    def get_elevation(self, pos: Coord) -> float:
        x, y = pos
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.elevation[y][x]
        return 0.0

    def step_cost(self, u: Coord, v: Coord) -> float:
        dx = abs(v[0] - u[0])
        dy = abs(v[1] - u[1])
        horiz_dist = 1.41421356 if (dx != 0 and dy != 0) else 1.0
        elev_diff = self.elevation[v[1]][v[0]] - self.elevation[u[1]][u[0]]
        climb_penalty = max(0.0, elev_diff) * 0.004
        return horiz_dist + climb_penalty

    def get_neighbors(self, pos: Coord) -> List[Tuple[Coord, float, float]]:
        """Return list of (neighbor_coord, step_cost, horiz_dist_km)."""
        x, y = pos
        directions = [
            (0, 1), (1, 0), (0, -1), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1),
        ]
        neighbors: List[Tuple[Coord, float, float]] = []
        for dx, dy in directions:
            nxt = (x + dx, y + dy)
            if not self.is_passable(nxt):
                continue
            # Prevent diagonal corner cutting when both adjacent cardinal cells are obstacles
            if dx != 0 and dy != 0:
                if not self.is_passable((x + dx, y)) and not self.is_passable((x, y + dy)):
                    continue
            horiz_dist = 1.41421356 if (dx != 0 and dy != 0) else 1.0
            cost = self.step_cost(pos, nxt)
            neighbors.append((nxt, cost, horiz_dist))
        return neighbors
