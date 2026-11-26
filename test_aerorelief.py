"""Regression tests for AeroRelief 2.5D engine, layout randomization, and Streamlit app."""

import math
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import aerorelief_engine as eng


class TestAeroReliefEngine(unittest.TestCase):
    def test_astar_avoids_static_obstacles_and_high_climb(self):
        env = eng.GridEnvironment25D(width=20, height=20, cell_size_m=100.0, max_altitude_m=160.0)
        env.add_static_obstacle_zone(8, 12, 5, 15)
        path, _, _ = eng.astar_25d(env, (5, 10), (15, 10))
        self.assertIsNotNone(path)
        for x, y in path:
            self.assertFalse(env.static_obstacles[y, x])

    def test_unreachable_camp_stays_unreachable_when_other_drone_stays_at_depot(self):
        env = eng.GridEnvironment25D(width=20, height=20, cell_size_m=200.0, max_altitude_m=160.0)
        depots = [eng.Depot(id=1, name="D1", position=(2, 2))]
        camps = [
            eng.DisasterCamp(id=1, name="ReachableFar", position=(17, 17), demand_kg=2.0, urgency="HIGH", time_window_end_min=20.0),
            eng.DisasterCamp(id=2, name="WalledOff", position=(2, 17), demand_kg=1.0, urgency="CRITICAL", time_window_end_min=10.0),
        ]
        # Box in camp 2 completely
        env.add_static_obstacle_zone(1, 3, 16, 18)
        env.static_obstacles[17, 2] = False

        drones = [eng.DroneConfig(id=1, home_depot_id=1, max_battery_wh=30.0, max_payload_kg=8.0)]
        pts = {"D1": depots[0].position, "C1": camps[0].position, "C2": camps[1].position}
        cm, dm, paths = eng.compute_route_matrix(env, pts)
        routes = {1: [1]}

        sim = eng.AeroReliefSimulator(env, depots, camps, drones, routes, paths)
        self.assertEqual(sim.drone_states[1].state, "Stay at Depot")
        self.assertEqual(sim.camps[2].status, "Unreachable")

    def test_drone_grounds_when_battery_hits_zero_mid_flight(self):
        env = eng.GridEnvironment25D(width=30, height=30, cell_size_m=200.0, max_altitude_m=160.0)
        depots = [eng.Depot(id=1, name="D1", position=(2, 2))]
        camps = [eng.DisasterCamp(id=1, name="C1", position=(25, 25), demand_kg=2.0)]
        drones = [eng.DroneConfig(id=1, home_depot_id=1, max_battery_wh=100.0, max_payload_kg=8.0, base_wh_per_km=5.0)]
        pts = {"D1": (2, 2), "C1": (25, 25)}
        cm, dm, paths = eng.compute_route_matrix(env, pts)
        # Force an in-flight battery depletion by setting high base_wh_per_km after init
        sim = eng.AeroReliefSimulator(env, depots, camps, drones, {1: [1]}, paths)
        sim.drones_cfg[1].base_wh_per_km = 500.0
        for _ in range(10):
            sim.step(dt_min=0.2)
        self.assertEqual(sim.drone_states[1].state, "Out of Battery")
        self.assertEqual(sim.drone_states[1].remaining_battery_wh, 0.0)

    def test_random_layout_non_overlapping_across_sizes(self):
        for size in (20, 50, 100):
            layout = eng.generate_random_scenario_layout(size, size, seed=77)
            all_pos = [d.position for d in layout["depots"]] + [c.position for c in layout["camps"]]
            self.assertEqual(len(set(all_pos)), len(all_pos))
            sx, sy = layout["storm_center"]
            core_r = max(2.0, size * 0.055)
            for px, py in all_pos:
                self.assertGreater(math.hypot(px - sx, py - sy), core_r)
            fx, fy = layout["fire_center"]
            for px, py in all_pos:
                self.assertGreater(max(abs(px - fx), abs(py - fy)), 1)

    def test_advance_target_reuses_initial_path_when_passable(self):
        env = eng.GridEnvironment25D(width=20, height=20, cell_size_m=200.0, max_altitude_m=160.0)
        depots = [eng.Depot(id=1, name="D1", position=(2, 2))]
        camps = [
            eng.DisasterCamp(id=1, name="C1", position=(5, 2), demand_kg=1.0),
            eng.DisasterCamp(id=2, name="C2", position=(8, 2), demand_kg=1.0),
        ]
        drones = [eng.DroneConfig(id=1, home_depot_id=1, max_battery_wh=350.0, max_payload_kg=8.0)]
        pts = {"D1": (2, 2), "C1": (5, 2), "C2": (8, 2)}
        _, _, paths = eng.compute_route_matrix(env, pts)
        sim = eng.AeroReliefSimulator(env, depots, camps, drones, {1: [1, 2]}, paths)
        with patch("aerorelief_engine.astar_25d", wraps=eng.astar_25d) as spy_astar:
            while sim.camps[1].status == "In Transit":
                sim.step(dt_min=0.15)
            self.assertEqual(spy_astar.call_count, 0)


class TestStreamlitDashboard(unittest.TestCase):
    def test_app_controls_and_hazard_injection(self):
        at = AppTest.from_file("app_mockup.py", default_timeout=30)
        at.run()
        self.assertFalse(at.exception)

        next(b for b in at.button if b.label == "Play").click().run()
        self.assertTrue(at.session_state["playing"])
        t_after_play = at.session_state["sim"].sim_time_min

        # Injecting storm while playing must NOT skip an extra auto-step tick
        next(b for b in at.button if b.label == "Suntik Badai").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["sim"].sim_time_min, t_after_play)

        next(b for b in at.button if b.label == "Suntik Api").click().run()
        self.assertFalse(at.exception)

        next(b for b in at.button if b.label == "Pause").click().run()
        self.assertFalse(at.session_state["playing"])

        next(b for b in at.button if b.label == "+1 Tick").click().run()
        self.assertGreater(at.session_state["sim"].sim_time_min, t_after_play)

        next(b for b in at.button if b.label == "Reset").click().run()
        self.assertEqual(at.session_state["sim"].sim_time_min, 0.0)


if __name__ == "__main__":
    unittest.main()
