"""
AeroRelief: Prototype simulation combining A* Pathfinding and Genetic Algorithm
Final Project - Konsep Kecerdasan Artifisial (KKA)
"""

import math
import heapq
import random

class GridEnvironment:
    """Represents a 2D grid disaster area with obstacles/no-fly zones."""
    def __init__(self, width=30, height=30):
        self.width = width
        self.height = height
        self.obstacles = set()
        
    def add_obstacle_zone(self, x_min, x_max, y_min, y_max):
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.obstacles.add((x, y))

    def is_passable(self, pos):
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height and pos not in self.obstacles

    def get_neighbors(self, pos):
        x, y = pos
        # 8-directional movement
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0), 
                      (1, 1), (1, -1), (-1, 1), (-1, -1)]
        neighbors = []
        for dx, dy in directions:
            nxt = (x + dx, y + dy)
            if self.is_passable(nxt):
                # Diagonal moves have sqrt(2) cost
                cost = 1.414 if dx != 0 and dy != 0 else 1.0
                neighbors.append((nxt, cost))
        return neighbors


def heuristic_euclidean(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def astar_search(env, start, goal):
    """Computes shortest path using A* search."""
    if start == goal:
        return [start], 0.0

    open_set = []
    heapq.heappush(open_set, (0.0, start))
    came_from = {}
    g_score = {start: 0.0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            # Reconstruct path
            path = []
            curr = current
            while curr in came_from:
                path.append(curr)
                curr = came_from[curr]
            path.append(start)
            path.reverse()
            return path, g_score[goal]

        for neighbor, cost in env.get_neighbors(current):
            tentative_g = g_score[current] + cost
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic_euclidean(neighbor, goal)
                heapq.heappush(open_set, (f_score, neighbor))

    return None, float('inf') # No path found


class GeneticDroneRouter:
    """Genetic Algorithm to optimize delivery routes among multiple disaster camps."""
    def __init__(self, depot, camps, distance_matrix, num_drones=2, pop_size=30, generations=50):
        self.depot = depot
        self.camps = camps
        self.distance_matrix = distance_matrix
        self.num_drones = num_drones
        self.pop_size = pop_size
        self.generations = generations

    def evaluate_fitness(self, chromosome):
        # Chromosome is an ordered list of camp indices partitioned among drones
        total_distance = 0.0
        n_camps = len(self.camps)
        chunk_size = math.ceil(n_camps / self.num_drones)
        
        for d in range(self.num_drones):
            drone_camps = chromosome[d * chunk_size : (d + 1) * chunk_size]
            if not drone_camps:
                continue
            # Depot -> First camp
            dist = self.distance_matrix[(-1, drone_camps[0])]
            # Between camps
            for i in range(len(drone_camps) - 1):
                dist += self.distance_matrix[(drone_camps[i], drone_camps[i+1])]
            # Last camp -> Depot
            dist += self.distance_matrix[(drone_camps[-1], -1)]
            total_distance += dist
            
        return 1.0 / (total_distance + 1e-6), total_distance

    def run(self):
        n = len(self.camps)
        population = [random.sample(range(n), n) for _ in range(self.pop_size)]
        best_solution = None
        best_cost = float('inf')

        for _ in range(self.generations):
            evaluated = [self.evaluate_fitness(chrom) for chrom in population]
            for chrom, (fitness, cost) in zip(population, evaluated):
                if cost < best_cost:
                    best_cost = cost
                    best_solution = chrom

            # Tournament selection & Crossover (Order Crossover)
            new_pop = [best_solution]
            while len(new_pop) < self.pop_size:
                p1 = min(random.sample(population, 3), key=lambda c: self.evaluate_fitness(c)[1])
                p2 = min(random.sample(population, 3), key=lambda c: self.evaluate_fitness(c)[1])
                
                # Crossover
                cut1, cut2 = sorted(random.sample(range(n), 2))
                child = [-1] * n
                child[cut1:cut2] = p1[cut1:cut2]
                fill_idx = 0
                for item in p2:
                    if item not in child:
                        while child[fill_idx] != -1:
                            fill_idx += 1
                        child[fill_idx] = item
                
                # Mutation (Swap)
                if random.random() < 0.2:
                    i, j = random.sample(range(n), 2)
                    child[i], child[j] = child[j], child[i]
                new_pop.append(child)

            population = new_pop

        return best_solution, best_cost


if __name__ == "__main__":
    print("=== AeroRelief AI Simulation Engine Prototype ===")
    
    # 1. Setup Environment
    env = GridEnvironment(30, 30)
    # Add No-Fly Zone / Disaster debris area in center
    env.add_obstacle_zone(10, 18, 10, 18)
    
    # 2. Setup Depot and Disaster Camps
    depot = (2, 2)
    camps = [(8, 22), (25, 25), (24, 6), (5, 14), (20, 2)]
    print(f"Base Depot: {depot}")
    print(f"Emergency Camps to serve: {len(camps)}")
    
    # 3. Calculate Distance Matrix using A*
    all_points = [-1] + list(range(len(camps)))
    point_coords = {-1: depot}
    for idx, c in enumerate(camps):
        point_coords[idx] = c
        
    dist_matrix = {}
    print("\nComputing obstacle-free trajectories with A* Search...")
    for p1 in all_points:
        for p2 in all_points:
            if p1 == p2:
                dist_matrix[(p1, p2)] = 0.0
            else:
                path, cost = astar_search(env, point_coords[p1], point_coords[p2])
                dist_matrix[(p1, p2)] = cost

    print("Distance matrix computed successfully.")

    # 4. Run Genetic Algorithm to distribute & sequence routes
    print("\nRunning Genetic Algorithm for Multi-Drone Route Allocation...")
    ga = GeneticDroneRouter(depot, camps, dist_matrix, num_drones=2, pop_size=40, generations=60)
    best_chrom, best_cost = ga.run()

    chunk = math.ceil(len(camps) / 2)
    print(f"Optimal Multi-Drone Total Cost: {best_cost:.2f} distance units\n")
    for d in range(2):
        assigned = best_chrom[d*chunk : (d+1)*chunk]
        route_camps = [f"Camp #{idx} {camps[idx]}" for idx in assigned]
        print(f"Drone #{d+1} Delivery Sequence: Depot -> " + " -> ".join(route_camps) + " -> Depot")
