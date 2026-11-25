"""Comprehensive unit and integration tests for AeroRelief AI Engine & Dynamic Re-planning."""

import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from aerorelief.dynamic import active_dynamic_obstacles_at
from aerorelief.environment import TopographicEnvironment
from aerorelief.models import DynamicHazardEvent
from aerorelief.pathfinding import astar_search, ucs_search
from aerorelief.scenarios import SCENARIOS
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

    def test_dynamic_obstacles_trigger_midflight_replan_all_scenarios(self):
        for sc_id, sc in SCENARIOS.items():
            mission = solve_mission(
                {"scenario_id": sc_id, "generations": 35, "enable_dynamic_events": True}
            )
            self.assertTrue(mission["reachable"], f"Dynamic mission unreachable on {sc_id}")
            self.assertGreaterEqual(len(mission["dynamic"]["replan_log"]), 1)
            self.assertGreaterEqual(len(mission["dynamic"]["superseded_routes"]), 1)

            base_obs = set(tuple(o) for o in mission["obstacles"])
            dyn_events = sc.dynamic_events

            visited = []
            for ds in mission["routing"]["active"]["evaluation"]["drone_schedules"]:
                for d_info in ds["deliveries"]:
                    visited.append(d_info["camp_id"])
                for s_idx, seg in enumerate(ds["segments"]):
                    if seg.get("is_escape_step"):
                        continue
                    next_is_escape = (
                        s_idx + 1 < len(ds["segments"])
                        and ds["segments"][s_idx + 1].get("is_escape_step", False)
                    )
                    s_path = seg["path"]
                    for idx_p, pt in enumerate(s_path):
                        if next_is_escape and idx_p == len(s_path) - 1:
                            continue
                        coord = (int(pt[0]), int(pt[1]))
                        self.assertNotIn(coord, base_obs)
                        frac = idx_p / max(1, len(s_path) - 1)
                        pt_time = seg["start_min"] + frac * (seg["end_min"] - seg["start_min"])
                        active_dyn = active_dynamic_obstacles_at(
                            dyn_events, pt_time, sc.grid_width, sc.grid_height
                        )
                        self.assertNotIn(
                            coord,
                            active_dyn,
                            f"{sc_id} {ds['callsign']} collided with dynamic obstacle {coord} at t={pt_time:.2f}",
                        )

            expected_ids = sorted(c["id"] for c in mission["camps"])
            self.assertEqual(sorted(visited), expected_ids)

    def test_moving_obstacle_phase_expiration(self):
        ev = DynamicHazardEvent(
            id="moving_1",
            name="Badai Bergerak",
            trigger_min=6.0,
            expire_min=18.0,
            x_min=5,
            x_max=7,
            y_min=5,
            y_max=7,
        )
        self.assertEqual(len(active_dynamic_obstacles_at([ev], 4.0, 20, 20)), 0)
        self.assertEqual(len(active_dynamic_obstacles_at([ev], 10.0, 20, 20)), 9)
        self.assertEqual(len(active_dynamic_obstacles_at([ev], 18.5, 20, 20)), 0)

    def test_battery_reload_triggered_when_battery_small(self):
        mission = solve_mission(
            {
                "scenario_id": "semeru",
                "num_drones": 2,
                "max_battery_km": 68.0,
                "generations": 30,
                "enable_dynamic_events": False,
            }
        )
        self.assertTrue(mission["reachable"])
        total_reloads = sum(
            ds["reloads"] for ds in mission["routing"]["active"]["evaluation"]["drone_schedules"]
        )
        self.assertGreaterEqual(total_reloads, 1)

    def test_empty_and_unreachable_states(self):
        empty_res = solve_mission({"scenario_id": "semeru", "custom_camps": []})
        self.assertTrue(empty_res["empty"])

        wall = [(2, 3), (3, 3), (4, 3), (2, 4), (4, 4), (2, 5), (3, 5), (4, 5)]
        blocked_res = solve_mission({"scenario_id": "semeru", "custom_obstacles": wall})
        self.assertFalse(blocked_res["reachable"])

    def test_api_replan_live_midflight_injection(self):
        client = app.test_client()
        base = client.post(
            "/api/solve",
            json={"scenario_id": "semeru", "generations": 25, "enable_dynamic_events": False},
        ).get_json()
        self.assertTrue(base["reachable"])

        # Pick an active airborne drone segment around t = 8.0 min and block a point ahead of it
        target_cell = None
        for ds in base["routing"]["active"]["evaluation"]["drone_schedules"]:
            for seg in ds["segments"]:
                if seg["start_min"] <= 8.0 < seg["end_min"] and len(seg["path"]) >= 8:
                    target_cell = seg["path"][len(seg["path"]) // 2 + 2]
                    break
            if target_cell:
                break
        self.assertIsNotNone(target_cell)

        replan_resp = client.post(
            "/api/replan",
            json={
                "scenario_id": "semeru",
                "generations": 25,
                "enable_dynamic_events": False,
                "new_event": {
                    "id": "live_test_obs",
                    "name": "Rintangan Mendadak Uji",
                    "trigger_min": 8.0,
                    "cells": [target_cell],
                },
            },
        )
        self.assertEqual(replan_resp.status_code, 200)
        adapted = replan_resp.get_json()
        self.assertTrue(adapted["reachable"])
        self.assertGreaterEqual(len(adapted["dynamic"]["replan_log"]), 1)

    def test_flask_api_and_media_routes(self):
        client = app.test_client()
        r_idx = client.get("/")
        self.assertEqual(r_idx.status_code, 200)
        r_idx.close()

        self.assertEqual(client.get("/api/health").status_code, 200)
        sc_resp = client.get("/api/scenarios")
        self.assertEqual(sc_resp.status_code, 200)
        self.assertEqual(len(sc_resp.get_json()["scenarios"]), 3)

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
