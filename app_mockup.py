import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from aero_relief_prototype import GridEnvironment, astar_search, GeneticDroneRouter

st.set_page_config(page_title="AeroRelief Simulator - KKA Final Project", layout="wide", page_icon="🚁")

st.title("🚁 AeroRelief: Emergency Medical Drone Logistics Simulator")
st.markdown("""
**Tugas Final Project Konsep Kecerdasan Artifisial (KKA) - Teknik Informatika ITS**  
*Penerapan Algoritma Pencarian: **Informed Search (A\*)** & **Local / Heuristic Search (Genetic Algorithm)***
""")

# Sidebar Controls
st.sidebar.header("⚙️ Konfigurasi Parameter Simulasi")
num_drones = st.sidebar.slider("Jumlah Armada Drone", min_value=1, max_value=4, value=2)
pop_size = st.sidebar.slider("Ukuran Populasi (GA)", min_value=20, max_value=100, value=40, step=10)
generations = st.sidebar.slider("Jumlah Generasi (GA)", min_value=20, max_value=150, value=60, step=10)

# Environment Setup
env = GridEnvironment(30, 30)
env.add_obstacle_zone(10, 18, 10, 18)

depot = (2, 2)
camps = [(8, 22), (25, 25), (24, 6), (5, 14), (20, 2), (12, 4), (22, 16)]

col_map, col_stats = st.columns([3, 2])

# Compute Distance Matrix
all_points = [-1] + list(range(len(camps)))
point_coords = {-1: depot}
for idx, c in enumerate(camps):
    point_coords[idx] = c

dist_matrix = {}
detailed_paths = {}

for p1 in all_points:
    for p2 in all_points:
        if p1 == p2:
            dist_matrix[(p1, p2)] = 0.0
            detailed_paths[(p1, p2)] = []
        else:
            path, cost = astar_search(env, point_coords[p1], point_coords[p2])
            dist_matrix[(p1, p2)] = cost
            detailed_paths[(p1, p2)] = path

# Run GA
ga = GeneticDroneRouter(depot, camps, dist_matrix, num_drones=num_drones, pop_size=pop_size, generations=generations)
best_chrom, best_cost = ga.run()

with col_map:
    st.subheader("🗺️ Visualisasi Peta Zona Bencana & Rute Optimal")
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 30)
    ax.grid(True, linestyle="--", alpha=0.5)

    # Obstacle / No-fly zone
    rect = patches.Rectangle((10, 10), 9, 9, linewidth=1.5, edgecolor='crimson', facecolor='salmon', alpha=0.5, label='No-Fly Zone (Hazard)')
    ax.add_patch(rect)

    # Depot
    ax.plot(depot[0], depot[1], 'ks', markersize=12, label='Depot / Basecamp')
    ax.text(depot[0], depot[1] - 1.5, "Depot", fontweight='bold', ha='center')

    # Camps
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    chunk = int(np.ceil(len(camps) / num_drones))

    for idx, c in enumerate(camps):
        ax.plot(c[0], c[1], 'ro', markersize=9)
        ax.text(c[0], c[1] + 0.8, f"Posko {idx+1}", fontsize=9, ha='center', fontweight='bold')

    # Draw trajectories
    for d in range(num_drones):
        drone_camps = best_chrom[d*chunk : (d+1)*chunk]
        if not drone_camps:
            continue
        c_color = colors[d % len(colors)]
        
        # Sequence: Depot -> Camps -> Depot
        route_nodes = [-1] + drone_camps + [-1]
        for i in range(len(route_nodes) - 1):
            p1, p2 = route_nodes[i], route_nodes[i+1]
            sub_path = detailed_paths[(p1, p2)]
            if sub_path:
                xs = [p[0] for p in sub_path]
                ys = [p[1] for p in sub_path]
                ax.plot(xs, ys, color=c_color, linewidth=2.5, linestyle='-', label=f"Drone #{d+1} Path" if i == 0 else "")

    ax.set_xlabel("Koordinat X (Grid Km)")
    ax.set_ylabel("Koordinat Y (Grid Km)")
    ax.legend(loc='upper right')
    st.pyplot(fig)

with col_stats:
    st.subheader("📊 Analitik & Jadwal Pengiriman Armada")
    st.metric("Total Jarak Tempuh Armada", f"{best_cost:.2f} km")
    st.metric("Jumlah Titik Posko Bencana", f"{len(camps)} Posko")
    st.metric("Jumlah Armada Drone Aktif", f"{num_drones} UAV")

    st.markdown("### 📋 Alokasi Rute per Drone:")
    for d in range(num_drones):
        drone_camps = best_chrom[d*chunk : (d+1)*chunk]
        if not drone_camps:
            st.info(f"**Drone #{d+1}:** Standby di Depot")
            continue
        route_str = " ➔ ".join([f"**Posko {idx+1}**" for idx in drone_camps])
        st.success(f"**Drone #{d+1}:** Depot ➔ {route_str} ➔ Depot")

    st.markdown("""
    ---
    ### 🔬 Evaluasi Algoritma:
    - **Informed Search (A\*):** Berhasil menavigasi drone melewati rintangan *No-Fly Zone* (merah) menggunakan lintasan dengan biaya energi minimum.
    - **Genetic Algorithm:** Berhasil mendistribusikan beban kunjungan antar drone secara seimbang tanpa tumpang tindih urutan rute.
    """)
