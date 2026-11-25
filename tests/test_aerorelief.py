"""Comprehensive unit and integration tests for AeroRelief AI Engine & Flask Web App."""

import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from aerorelief.environment import TopographicEnvironment
from aerorelief.pathfinding import astar_search, ucs_search
from aerorelief.routing import GeneticDroneOptimizer
from aerorelief.scenarios import SCENARIOS, build_drone_fleet
from aerorelief.solver import solve_mission
from server import app


class TestAeroReliefAI(unittest.TestCase):
    def test_astar_optimality_and_efficiency_all_scenarios(self):
        for sc_id, sc in SCENARIOS.items():
            env = TopographicEnvironment(
                width=sc.grid_width,
                height=sc.grid_height,
                hills=sc.hills,
                hazard_zones=sc.hazard_zones,
            )
            a_total_exp = 0
            u_total_exp = 0
            for camp in sc.camps:
                res_a = astar_search(env, sc.depot, (camp.x, camp.y))
                res_u = ucs_search(env, sc.depot, (camp.x, camp.y))
                self.assertTrue(res_a.found, f"A* failed on {sc_id} -> {camp.name}")
                self.assertTrue(res_u.found, f"UCS failed on {sc_id} -> {camp.name}")
                self.assertAlmostEqual(res_a.cost, res_u.cost, places=5)
                a_total_exp += len(res_a.explored_nodes)
                u_total_exp += len(res_u.explored_nodes)
                for pt in res_a.path:
                    self.assertNotIn(pt, env.obstacles)
            self.assertLess(a_total_exp, u_total_exp)

    def test_ga_visits_all_camps_and_improves_history(self):
        mission = solve_mission({"scenario_id": "semeru", "num_drones": 3, "generations": 40})
        self.assertTrue(mission["reachable"])
        self.assertFalse(mission["empty"])

        hist = mission["routing"]["ga_summary"]["history"]
        self.assertEqual(len(hist), 40)
        self.assertLessEqual(hist[-1]["best_objective"], hist[0]["best_objective"])

        visited = []
        obstacles = set(tuple(o) for o in mission["obstacles"])
        for ds in mission["routing"]["active"]["evaluation"]["drone_schedules"]:
            for d_info in ds["deliveries"]:
                visited.append(d_info["camp_id"])
            for seg in ds["segments"]:
                for pt in seg["path"]:
                    self.assertNotIn(tuple(pt), obstacles)

        expected_ids = sorted(c["id"] for c in mission["camps"])
        self.assertEqual(sorted(visited), expected_ids)

    def test_battery_reload_triggered_when_battery_small(self):
        mission = solve_mission({"scenario_id": "semeru", "num_drones": 2, "max_battery_km": 68.0, "generations": 30})
        self.assertTrue(mission["reachable"])
        total_reloads = sum(
            ds["reloads"] for ds in mission["routing"]["active"]["evaluation"]["drone_schedules"]
        )
        self.assertGreaterEqual(total_reloads, 1)

    def test_empty_and_unreachable_states(self):
        empty_res = solve_mission({"scenario_id": "semeru", "custom_camps": []})
        self.assertTrue(empty_res["empty"])

        # Wall off depot (3,4) completely
        wall = [(2, 3), (3, 3), (4, 3), (2, 4), (4, 4), (2, 5), (3, 5), (4, 5)]
        blocked_res = solve_mission({"scenario_id": "semeru", "custom_obstacles": wall})
        self.assertFalse(blocked_res["reachable"])

    def test_flask_api_and_media_routes(self):
        client = app.test_client()
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/api/health").status_code, 200)

        sc_resp = client.get("/api/scenarios")
        self.assertEqual(sc_resp.status_code, 200)
        self.assertEqual(len(sc_resp.get_json()["scenarios"]), 3)

        for sc_id in ("semeru", "cianjur", "demak"):
            r = client.post("/api/solve", json={"scenario_id": sc_id, "generations": 20})
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertTrue(data["reachable"])

        # Unreachable obstacle case via API
        r_err = client.post(
            "/api/solve",
            json={
                "scenario_id": "semeru",
                "custom_obstacles": [(2, 3), (3, 3), (4, 3), (2, 4), (4, 4), (2, 5), (3, 5), (4, 5)],
            },
        )
        self.assertEqual(r_err.status_code, 200)
        self.assertFalse(r_err.get_json()["reachable"])

        for media_file in (
            "/media/aerorelief_mockup_demo.mp4",
            "/media/aerorelief_simulation.gif",
            "/media/flowchart_sistem.png",
            "/media/benchmark_algorithms.png",
            "/media/video_poster.png",
            "/media/AeroRelief_Progress_KKA.pptx",
            "/media/mockup_simulation.png",
        ):
            mr = client.get(media_file)
            self.assertEqual(mr.status_code, 200, f"Missing or broken route: {media_file}")
            mr.close()


if __name__ == "__main__":
    unittest.main()
