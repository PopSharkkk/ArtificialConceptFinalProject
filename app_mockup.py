"""Streamlit interactive dashboard for AeroRelief (alternative Python UI)."""

import os
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from aerorelief.solver import solve_mission

st.set_page_config(page_title="AeroRelief Simulator - KKA ITS", layout="wide")

st.title("AeroRelief: Optimasi Rute Logistik Medis Multi-Drone Pasca Bencana")
st.markdown(
    "**Final Project Konsep Kecerdasan Artifisial (EK234201) - Teknik Informatika ITS** | "
    "Two-Tier AI Search: **Informed Search (A*)** & **Local Search (Genetic Algorithm VRPTW-BL)**"
)

st.sidebar.header("Konfigurasi Parameter Simulasi")
scenario_map = {
    "Erupsi Gunung Semeru (Lumajang)": "semeru",
    "Gempa Bumi & Longsor Cianjur": "cianjur",
    "Banjir Bandang Karanganyar (Demak)": "demak",
}
selected_label = st.sidebar.selectbox("Skenario Bencana", list(scenario_map.keys()))
scenario_id = scenario_map[selected_label]

path_algo = st.sidebar.selectbox("Algoritma Pencarian Jalur (Tier 1)", ["astar", "ucs", "greedy"])
routing_algo = st.sidebar.selectbox("Algoritma Penjadwalan (Tier 2)", ["ga", "sa"])
num_drones = st.sidebar.slider("Jumlah Armada Drone", 1, 4, 3)
pop_size = st.sidebar.slider("Ukuran Populasi (GA)", 20, 100, 50, 10)
generations = st.sidebar.slider("Jumlah Generasi", 20, 140, 80, 10)
max_battery = st.sidebar.slider("Batas Jarak Baterai (km)", 45, 120, 80, 5)

mission = solve_mission(
    {
        "scenario_id": scenario_id,
        "path_algorithm": path_algo,
        "routing_algorithm": routing_algo,
        "num_drones": num_drones,
        "pop_size": pop_size,
        "generations": generations,
        "max_battery_km": max_battery,
    }
)

tab_sim, tab_video = st.tabs(["Peta & Analitik Optimasi", "Video Simulasi HD (1080p)"])

with tab_sim:
    if not mission.get("reachable"):
        st.error(mission.get("message", "Posko tidak dapat dijangkau."))
    else:
        eval_data = mission["routing"]["active"]["evaluation"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Jarak Armada", f"{eval_data['total_distance_km']:.1f} km")
        c2.metric("Makespan (Waktu Selesai)", f"{eval_data['makespan_min']:.1f} menit")
        c3.metric("Ketepatan Waktu Urgensi", f"{eval_data['on_time_pct']:.1f}%")

        col_map, col_info = st.columns([3, 2])
        with col_map:
            fig, ax = plt.subplots(figsize=(9, 6.5))
            ax.imshow(mission["elevation"], origin="lower", cmap="YlGn", alpha=0.35)
            for hz in mission["scenario"]["hazard_zones"]:
                rect = patches.Rectangle(
                    (hz["x_min"] - 0.5, hz["y_min"] - 0.5),
                    hz["x_max"] - hz["x_min"] + 1,
                    hz["y_max"] - hz["y_min"] + 1,
                    linewidth=1.8,
                    edgecolor="#B91C1C",
                    facecolor="#FCA5A5",
                    alpha=0.55,
                )
                ax.add_patch(rect)

            depot = mission["depot"]
            ax.plot(depot[0], depot[1], "s", color="#C84318", markersize=12, label="Base Depot")
            for camp in mission["camps"]:
                ax.plot(camp["x"], camp["y"], "o", color="#B4232E", markersize=8)
                ax.text(camp["x"] + 0.4, camp["y"] + 0.4, f"P{camp['id']}", fontsize=8, fontweight="bold")

            colors = ["#1D5BD6", "#B86B00", "#0F7B58", "#B4234E"]
            for idx, ds in enumerate(eval_data["drone_schedules"]):
                col = colors[idx % len(colors)]
                for s_i, seg in enumerate(ds["segments"]):
                    if len(seg["path"]) >= 2:
                        xs = [p[0] for p in seg["path"]]
                        ys = [p[1] for p in seg["path"]]
                        ax.plot(xs, ys, color=col, linewidth=2.3, label=ds["callsign"] if s_i == 0 else "")

            ax.set_xlim(-0.5, mission["scenario"]["grid_width"] - 0.5)
            ax.set_ylim(-0.5, mission["scenario"]["grid_height"] - 0.5)
            ax.legend(loc="upper right", fontsize=8)
            ax.set_title(mission["scenario"]["title"])
            st.pyplot(fig)

        with col_info:
            st.subheader("Manifes Rute Armada")
            for ds in eval_data["drone_schedules"]:
                st.write(
                    f"**{ds['callsign']}** ({ds['total_distance_km']} km, {ds['total_time_min']} mnt): "
                    + " -> ".join(ds["route_labels"])
                )
            st.subheader("Benchmark Pencarian Jalur")
            st.dataframe(mission["pathfinding"]["benchmark"], use_container_width=True)

with tab_video:
    video_path = os.path.join(os.path.dirname(__file__), "media", "aerorelief_mockup_demo.mp4")
    if os.path.exists(video_path):
        st.video(video_path)
    else:
        st.warning("File video media/aerorelief_mockup_demo.mp4 belum ditemukan.")
