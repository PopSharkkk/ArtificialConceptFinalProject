"""
Generate all visual, analytical, and video assets for AeroRelief:
1. web/static/precomputed.json (3 solved disaster scenarios)
2. media/flowchart_sistem.png (Architectural flowchart)
3. media/benchmark_algorithms.png (A* vs UCS vs Greedy & GA vs SA benchmark)
4. media/aerorelief_mockup_demo.mp4 (1920x1080 30fps 22s Mission Control demo video)
5. media/video_poster.png & mockup_simulation.png (1920x1080 crisp UI frame)
6. media/aerorelief_simulation.gif (960x540 12fps GitHub README preview)
"""

import math
import os
import subprocess
import sys
import time
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from aerorelief.solver import export_precomputed_json, solve_mission

MEDIA_DIR = os.path.join(ROOT_DIR, "media")
WEB_STATIC_DIR = os.path.join(ROOT_DIR, "web", "static")
os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(WEB_STATIC_DIR, exist_ok=True)

FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_REG = "C:/Windows/Fonts/segoeui.ttf"
FONT_MONO_BOLD = "C:/Windows/Fonts/consolab.ttf"
FONT_MONO = "C:/Windows/Fonts/consola.ttf"


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


# Palette (Light Tactical Cartography + Dark Night Ops Video Console)
PALETTE = {
    "bg": (13, 21, 30),
    "panel": (20, 32, 45),
    "panel_alt": (28, 43, 59),
    "border": (42, 59, 78),
    "ink": (237, 242, 247),
    "muted": (159, 176, 194),
    "accent": (242, 106, 54),
    "terrain": (52, 211, 153),
    "hazard_fill": (127, 29, 29),
    "hazard_edge": (248, 113, 113),
    "uav_colors": [
        (88, 153, 255),   # UAV-01 Rajawali
        (245, 158, 11),   # UAV-02 Garuda
        (45, 212, 191),   # UAV-03 Elang
        (251, 113, 133),  # UAV-04 Merpati
    ],
    "ok": (52, 211, 153),
    "warn": (251, 191, 36),
    "crit": (248, 113, 113),
}


def generate_flowchart_png(out_path: str) -> None:
    """Draw a high-resolution two-tier system architecture flowchart."""
    W, H = 1800, 1000
    img = Image.new("RGB", (W, H), (246, 245, 240))
    draw = ImageDraw.Draw(img)

    f_title = load_font(FONT_BOLD, 34)
    f_sub = load_font(FONT_REG, 20)
    f_box_t = load_font(FONT_BOLD, 21)
    f_box_b = load_font(FONT_REG, 17)
    f_tag = load_font(FONT_MONO_BOLD, 15)

    # Header bar
    draw.rectangle([0, 0, W, 112], fill=(20, 32, 43))
    draw.rectangle([0, 106, W, 112], fill=(200, 67, 24))
    draw.text((56, 22), "ARSITEKTUR & ALUR KERJA SISTEM AERORELIEF", fill=(255, 255, 255), font=f_title)
    draw.text(
        (56, 66),
        "Optimasi Rute Logistik Medis Multi-Drone Berbasis Two-Tier AI Search (A* + Genetic Algorithm)",
        fill=(185, 200, 214),
        font=f_sub,
    )

    def draw_box(x1, y1, x2, y2, title, lines, fill=(255, 255, 255), border=(20, 32, 43), tag=None, tag_col=(200, 67, 24)):
        draw.rounded_rectangle([x1 + 4, y1 + 5, x2 + 4, y2 + 5], radius=12, fill=(215, 217, 220))
        draw.rounded_rectangle([x1, y1, x2, y2], radius=12, fill=fill, outline=border, width=3)
        ty = y1 + 18
        if tag:
            draw.rounded_rectangle([x1 + 18, y1 + 14, x1 + 18 + len(tag) * 10 + 22, y1 + 40], radius=6, fill=tag_col)
            draw.text((x1 + 29, y1 + 18), tag, fill=(255, 255, 255), font=f_tag)
            ty = y1 + 50
        draw.text((x1 + 20, ty), title, fill=(20, 32, 43), font=f_box_t)
        ly = ty + 32
        for line in lines:
            draw.text((x1 + 20, ly), line, fill=(66, 82, 98), font=f_box_b)
            ly += 24

    def draw_arrow(x1, y1, x2, y2, color=(20, 32, 43), label=None, label_bg=(246, 245, 240)):
        draw.line([x1, y1, x2, y2], fill=color, width=4)
        ang = math.atan2(y2 - y1, x2 - x1)
        ah = 14
        p1 = (x2 - ah * math.cos(ang - 0.45), y2 - ah * math.sin(ang - 0.45))
        p2 = (x2 - ah * math.cos(ang + 0.45), y2 - ah * math.sin(ang + 0.45))
        draw.polygon([(x2, y2), p1, p2], fill=color)
        if label:
            mx, my = (x1 + x2) // 2, (y1 + y2) // 2
            draw.rectangle([mx - 42, my - 14, mx + 42, my + 14], fill=label_bg)
            draw.text((mx - 34, my - 10), label, fill=color, font=f_tag)

    # Row 1: Input -> Tier 1 A* -> Tier 2 GA Container
    draw_box(
        60, 155, 500, 345,
        "1. Input Data Bencana",
        [
            "- Peta grid & topografi elevasi (m)",
            "- Koordinat Depot & Posko Darurat",
            "- Zona Terlarang (No-Fly / Hazard)",
            "- Batas baterai & muatan armada UAV",
        ],
        tag="INPUT",
        tag_col=(35, 107, 89),
    )

    draw_arrow(500, 250, 600, 250)

    draw_box(
        600, 155, 1180, 345,
        "2. Matriks Jalur Aman (Algoritma A*)",
        [
            "- Hitung jalur terpendek antar Depot & seluruh Posko",
            "- Fungsi evaluasi: f(n) = g(n) + h(n) Euclidean",
            "- Penalti elevasi tanjakan & penghindaran zona bahaya",
            "- Hasil: Matriks jarak, waktu tempuh, & daftar waypoints",
        ],
        tag="TIER 1: INFORMED SEARCH",
        tag_col=(29, 91, 214),
    )

    draw_arrow(1180, 250, 1280, 250)

    draw_box(
        1280, 155, 1740, 345,
        "3. Inisialisasi Populasi Rute",
        [
            "- Kromosom: permutasi ID Posko + pemisah UAV",
            "- Populasi acak tervalidasi N individu",
            "- Penjadwalan awal seluruh armada drone",
        ],
        tag="TIER 2: LOCAL SEARCH",
        tag_col=(200, 67, 24),
    )

    # Arrow down into GA Loop
    draw_arrow(1510, 345, 1510, 425)

    # GA Optimization Container
    draw.rounded_rectangle([60, 425, 1740, 725], radius=16, fill=(234, 231, 223), outline=(200, 67, 24), width=3)
    draw.text((88, 444), "4. Siklus Optimasi Penjadwalan Multi-Drone (Genetic Algorithm VRPTW-BL)", fill=(200, 67, 24), font=f_box_t)

    draw_box(
        1280, 495, 1705, 690,
        "4a. Evaluasi Fitness VRPTW-BL",
        [
            "- Simulasi jarak, muatan, & reload",
            "- Penalti keterlambatan urgensi Posko",
            "- Catat total jarak & makespan terbaik",
        ],
        border=(200, 67, 24),
    )

    draw_arrow(1280, 592, 1165, 592)

    draw_box(
        820, 495, 1165, 690,
        "4b. Kondisi Berhenti?",
        [
            "- Cek Generasi == Maksimal",
            "- Jika BELUM: lanjut seleksi",
            "- Jika YA: keluarkan rute terbaik",
        ],
        border=(20, 32, 43),
    )

    draw_arrow(820, 592, 705, 592, label="BELUM", label_bg=(234, 231, 223))

    draw_box(
        95, 495, 705, 690,
        "4c. Operator Genetik (Generasi Berikutnya)",
        [
            "- Elitism: pertahankan 2 kromosom terbaik",
            "- Tournament Selection (k = 3)",
            "- Order Crossover (OX) & Mutasi Swap / 2-Opt Inversion",
        ],
        border=(29, 91, 214),
    )

    # Loop back arrow from 4c top back to 4a
    draw.line([400, 495, 400, 472, 1490, 472, 1490, 495], fill=(29, 91, 214), width=3)
    draw.polygon([(1490, 495), (1482, 480), (1498, 480)], fill=(29, 91, 214))

    # Arrow from 4b down to Row 3
    draw_arrow(992, 690, 992, 785, label="YA")

    # Row 3: Output & Simulation
    draw_box(
        60, 785, 860, 945,
        "5. Rekonstruksi Waypoints & Manifes Penerbangan",
        [
            "- Gabungkan urutan Posko GA dengan detail lintasan grid A*",
            "- Hitung jadwal waktu tiba (ETA), titik reload Depot, & sisa baterai",
        ],
        tag="OUTPUT SOLUSI",
        tag_col=(15, 123, 88),
    )

    draw_arrow(860, 865, 950, 865)

    draw_box(
        950, 785, 1740, 945,
        "6. Dashboard Web Interaktif & Simulasi Video HD",
        [
            "- Animasi armada multi-drone real-time di peta topografi",
            "- Grafik konvergensi GA vs SA & benchmark A* vs UCS",
        ],
        tag="VISUALISASI",
        tag_col=(20, 32, 43),
    )

    img.save(out_path, optimize=True)
    print(f"Saved flowchart: {out_path}")


def generate_benchmark_png(mission: dict, out_path: str) -> None:
    """Generate dual analytical chart comparing Search and Routing algorithms."""
    bench = mission["pathfinding"]["benchmark"]
    ga_hist = mission["routing"]["ga_summary"]["history"]
    sa_hist = mission["routing"]["sa_summary"]["history"]

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Segoe UI", "Arial", "DejaVu Sans"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.8), dpi=140)
    fig.patch.set_facecolor("#F6F5F0")

    # Panel 1: Pathfinding Search Comparison
    labels = ["A* Search\n(Informed)", "Uniform Cost\n(Uninformed)", "Greedy BFS\n(Heuristic Only)"]
    explored = [r["total_explored_nodes"] for r in bench]
    gaps = [r["optimality_gap_pct"] for r in bench]
    bar_colors = ["#1D5BD6", "#425262", "#C84318"]

    ax1.set_facecolor("#FFFFFF")
    bars = ax1.bar(labels, explored, color=bar_colors, width=0.52, edgecolor="#14202B", linewidth=1.2)
    ax1.set_title(
        "Efisiensi Eksplorasi Simpul: A* vs UCS vs Greedy BFS",
        fontsize=13,
        fontweight="bold",
        color="#14202B",
        pad=14,
    )
    ax1.set_ylabel("Total Simpul Grid Dieksplorasi (72 Pasangan)", fontsize=10.5, color="#14202B")
    ax1.grid(axis="y", linestyle="--", alpha=0.45, color="#94A3B8")
    ax1.set_ylim(0, max(explored) * 1.22)
    for bar, val, gap in zip(bars, explored, gaps):
        tag = f"{val:,} simpul\n(Gap: {gap:.2f}%)"
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            val + max(explored) * 0.03,
            tag,
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="bold",
            color="#14202B",
        )

    # Panel 2: GA vs SA Convergence
    ax2.set_facecolor("#FFFFFF")
    gens_ga = [h["gen"] for h in ga_hist]
    obj_ga = [h["best_objective"] for h in ga_hist]
    gens_sa = [h["gen"] for h in sa_hist]
    obj_sa = [h["best_objective"] for h in sa_hist]

    ax2.plot(gens_ga, obj_ga, color="#1D5BD6", linewidth=2.8, label="Genetic Algorithm (GA)")
    ax2.plot(gens_sa, obj_sa, color="#C84318", linewidth=2.4, linestyle="--", label="Simulated Annealing (SA)")
    ax2.set_title(
        "Konvergensi Optimasi Rute VRPTW-BL per Generasi",
        fontsize=13,
        fontweight="bold",
        color="#14202B",
        pad=14,
    )
    ax2.set_xlabel("Generasi / Checkpoint Iterasi", fontsize=10.5, color="#14202B")
    ax2.set_ylabel("Nilai Fungsi Objektif Terbaik (Lebih Rendah = Lebih Baik)", fontsize=10.5, color="#14202B")
    ax2.grid(True, linestyle="--", alpha=0.45, color="#94A3B8")
    ax2.legend(loc="upper right", frameon=True, facecolor="#F6F5F0", edgecolor="#CFD6DE")

    # Annotate final GA value
    ax2.scatter([gens_ga[-1]], [obj_ga[-1]], color="#1D5BD6", s=55, zorder=5)
    ax2.annotate(
        f"GA Final: {obj_ga[-1]:.1f}",
        xy=(gens_ga[-1], obj_ga[-1]),
        xytext=(gens_ga[-1] * 0.62, obj_ga[-1] + (max(obj_ga) - min(obj_ga)) * 0.055),
        arrowprops=dict(arrowstyle="->", color="#1D5BD6", lw=1.4),
        fontsize=9.5,
        fontweight="bold",
        color="#1D5BD6",
    )

    fig.suptitle(
        f"Hasil Pengujian Algoritma Pencarian Python : {mission['scenario']['title']}",
        fontsize=15,
        fontweight="bold",
        color="#14202B",
        y=0.98,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f"Saved benchmark chart: {out_path}")


def _build_video_base_canvas(mission: dict) -> Tuple[Image.Image, dict]:
    """Pre-render static Mission Control background + topographic map at 1920x1080."""
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), PALETTE["bg"])
    draw = ImageDraw.Draw(img)

    f_h1 = load_font(FONT_BOLD, 28)
    f_sub = load_font(FONT_REG, 17)
    f_mono = load_font(FONT_MONO_BOLD, 16)
    f_lbl = load_font(FONT_BOLD, 15)

    # Top Header Chrome
    draw.rectangle([0, 0, W, 84], fill=PALETTE["panel"])
    draw.line([0, 84, W, 84], fill=PALETTE["border"], width=2)
    draw.rectangle([28, 22, 42, 62], fill=PALETTE["accent"])
    draw.text((58, 16), "AERORELIEF MISSION CONTROL", fill=PALETTE["ink"], font=f_h1)
    draw.text(
        (58, 50),
        f"Skenario: {mission['scenario']['title']}  |  Two-Tier AI Search (A* + Genetic Algorithm)",
        fill=PALETTE["muted"],
        font=f_sub,
    )

    # Map Frame (Left) & Telemetry Panel (Right)
    map_box = (36, 108, 1284, 1012)  # 1248 x 904
    side_box = (1308, 108, 1884, 1012)  # 576 x 904
    draw.rounded_rectangle(map_box, radius=14, fill=PALETTE["panel"], outline=PALETTE["border"], width=2)
    draw.rounded_rectangle(side_box, radius=14, fill=PALETTE["panel"], outline=PALETTE["border"], width=2)

    # Grid geometry inside map_box
    gw = mission["scenario"]["grid_width"]
    gh = mission["scenario"]["grid_height"]
    pad_l, pad_t, pad_r, pad_b = 56, 62, 36, 48
    px1 = map_box[0] + pad_l
    py1 = map_box[1] + pad_t
    px2 = map_box[2] - pad_r
    py2 = map_box[3] - pad_b
    cell_w = (px2 - px1) / gw
    cell_h = (py2 - py1) / gh

    # Render elevation terrain heatmap cells directly onto map
    elev = mission["elevation"]
    max_elev = max(max(row) for row in elev) or 1.0
    for gy in range(gh):
        for gx in range(gw):
            val = elev[gy][gx] / max_elev
            r = int(17 + val * 20)
            g = int(28 + val * 44)
            b = int(39 + val * 30)
            cx1 = px1 + gx * cell_w
            cy1 = py2 - (gy + 1) * cell_h
            draw.rectangle([cx1, cy1, cx1 + cell_w + 1, cy1 + cell_h + 1], fill=(r, g, b))

    # Subtle grid hairlines
    for gx in range(gw + 1):
        x = px1 + gx * cell_w
        draw.line([x, py1, x, py2], fill=(35, 50, 66), width=1)
    for gy in range(gh + 1):
        y = py1 + gy * cell_h
        draw.line([px1, y, px2, y], fill=(35, 50, 66), width=1)

    # Axis ticks
    for gx in range(0, gw + 1, 5):
        x = px1 + gx * cell_w
        draw.text((x - 8, py2 + 10), str(gx), fill=PALETTE["muted"], font=f_mono)
    for gy in range(0, gh + 1, 5):
        y = py2 - gy * cell_h
        draw.text((px1 - 32, y - 8), str(gy), fill=PALETTE["muted"], font=f_mono)

    # Draw Hazard Zones
    for hz in mission["scenario"]["hazard_zones"]:
        hx1 = px1 + hz["x_min"] * cell_w
        hx2 = px1 + (hz["x_max"] + 1) * cell_w
        hy2 = py2 - hz["y_min"] * cell_h
        hy1 = py2 - (hz["y_max"] + 1) * cell_h
        draw.rectangle([hx1, hy1, hx2, hy2], fill=PALETTE["hazard_fill"], outline=PALETTE["hazard_edge"], width=3)
        # Diagonal hazard stripes
        step = 18
        for s in range(0, int((hx2 - hx1) + (hy2 - hy1)), step):
            sx1 = max(hx1, hx1 + s - (hy2 - hy1))
            sy1 = min(hy2, hy1 + s)
            sx2 = min(hx2, hx1 + s)
            sy2 = max(hy1, hy1 + s - (hx2 - hx1))
            if sx1 < sx2 and sy1 > sy2:
                draw.line([sx1, sy1, sx2, sy2], fill=(185, 45, 45), width=2)
        draw.text((hx1 + 10, hy1 + 10), hz["name"].upper(), fill=(254, 202, 202), font=f_lbl)

    draw.rectangle([px1, py1, px2, py2], outline=PALETTE["border"], width=2)

    def to_px(gx: float, gy: float) -> Tuple[float, float]:
        return (px1 + (gx + 0.5) * cell_w, py2 - (gy + 0.5) * cell_h)

    geom = {
        "map_box": map_box,
        "side_box": side_box,
        "px1": px1,
        "py1": py1,
        "px2": px2,
        "py2": py2,
        "cell_w": cell_w,
        "cell_h": cell_h,
        "to_px": to_px,
    }
    return img, geom


def generate_video_and_gif(mission: dict, mp4_path: str, gif_path: str, poster_path: str, root_mockup_path: str) -> None:
    """Render 660 frames at 1920x1080 (30fps, 22s) directly to FFmpeg libx264."""
    t_start = time.time()
    base_img, geom = _build_video_base_canvas(mission)
    to_px = geom["to_px"]
    side_box = geom["side_box"]
    map_box = geom["map_box"]
    cell_w = geom["cell_w"]
    cell_h = geom["cell_h"]

    f_title_lg = load_font(FONT_BOLD, 44)
    f_h2 = load_font(FONT_BOLD, 22)
    f_h3 = load_font(FONT_BOLD, 18)
    f_body = load_font(FONT_REG, 16)
    f_mono = load_font(FONT_MONO_BOLD, 16)
    f_mono_sm = load_font(FONT_MONO, 14)

    depot = tuple(mission["depot"])
    camps = mission["camps"]
    explored_nodes = mission["pathfinding"]["explored_union"]
    bench = mission["pathfinding"]["benchmark"]
    ga_hist = mission["routing"]["ga_summary"]["history"]
    sa_hist = mission["routing"]["sa_summary"]["history"]
    active_eval = mission["routing"]["active"]["evaluation"]
    schedules = active_eval["drone_schedules"]
    makespan = active_eval["makespan_min"]

    # Map camp_id -> arrival_min
    camp_arrival: Dict[int, float] = {}
    for ds in schedules:
        for d_info in ds["deliveries"]:
            camp_arrival[d_info["camp_id"]] = d_info["arrival_min"]

    # Setup FFmpeg pipe
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", "1920x1080",
        "-r", "30",
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "21",
        "-preset", "fast",
        "-movflags", "+faststart",
        mp4_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None

    TOTAL_FRAMES = 660  # 22 seconds @ 30fps
    poster_saved = False

    def draw_uav_sprite(draw: ImageDraw.ImageDraw, cx: float, cy: float, color: Tuple[int, int, int], callsign: str):
        r = 14
        # Quadrotor arms
        draw.line([cx - r, cy - r, cx + r, cy + r], fill=color, width=3)
        draw.line([cx - r, cy + r, cx + r, cy - r], fill=color, width=3)
        for rx, ry in [(cx - r, cy - r), (cx + r, cy - r), (cx - r, cy + r), (cx + r, cy + r)]:
            draw.ellipse([rx - 5, ry - 5, rx + 5, ry + 5], outline=color, width=2, fill=(13, 21, 30))
        draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=color, outline=(255, 255, 255), width=2)
        draw.rounded_rectangle([cx + 14, cy - 11, cx + 82, cy + 10], radius=4, fill=(13, 21, 30), outline=color, width=1)
        draw.text((cx + 18, cy - 9), callsign.split()[0], fill=(255, 255, 255), font=f_mono_sm)

    for frame_idx in range(TOTAL_FRAMES):
        frame = base_img.copy()
        draw = ImageDraw.Draw(frame)

        # Determine chapter
        if frame_idx < 105:
            chapter = 1
            chapter_title = "TAHAP 0 : INISIALISASI PETA BENCANA & POSKO DARURAT"
            prog = frame_idx / 105.0
        elif frame_idx < 270:
            chapter = 2
            chapter_title = "TAHAP 1 : INFORMED SEARCH (ALGORITMA A* PATHFINDING)"
            prog = (frame_idx - 105) / 165.0
        elif frame_idx < 420:
            chapter = 3
            chapter_title = "TAHAP 2 : LOCAL SEARCH (GENETIC ALGORITHM VRPTW-BL)"
            prog = (frame_idx - 270) / 150.0
        else:
            chapter = 4
            chapter_title = "TAHAP 3 : EKSEKUSI MISI PENGIRIMAN LOGISTIK MULTI-DRONE"
            prog = min(1.0, (frame_idx - 420) / 200.0)

        # Top banner inside map
        draw.text((map_box[0] + 56, map_box[1] + 18), chapter_title, fill=PALETTE["accent"], font=f_h2)

        # Chapter 2: Animated A* explored frontier nodes
        if chapter == 2:
            n_show = int(len(explored_nodes) * min(1.0, prog * 1.15))
            for node in explored_nodes[:n_show]:
                nx, ny = node
                x0 = geom["px1"] + nx * cell_w + 3
                y0 = geom["py2"] - (ny + 1) * cell_h + 3
                draw.rectangle([x0, y0, x0 + cell_w - 6, y0 + cell_h - 6], fill=(37, 99, 235), outline=(96, 165, 250))
        elif chapter >= 3:
            # Faint A* footprint
            for node in explored_nodes[::2]:
                nx, ny = node
                x0 = geom["px1"] + nx * cell_w + 6
                y0 = geom["py2"] - (ny + 1) * cell_h + 6
                draw.rectangle([x0, y0, x0 + cell_w - 12, y0 + cell_h - 12], fill=(24, 52, 92))

        # Chapter 3 & 4: Draw optimal routes
        if chapter >= 3:
            alpha_segs = prog if chapter == 3 else 1.0
            for d_idx, ds in enumerate(schedules):
                col = PALETTE["uav_colors"][d_idx % len(PALETTE["uav_colors"])]
                segs = ds["segments"]
                if not segs:
                    continue
                n_segs = max(1, int(math.ceil(len(segs) * alpha_segs))) if chapter == 3 else len(segs)
                for seg in segs[:n_segs]:
                    path = seg["path"]
                    if len(path) >= 2:
                        pts = [to_px(p[0], p[1]) for p in path]
                        draw.line(pts, fill=col, width=4 if not seg["is_reload_trip"] else 2)

        # Draw Depot
        dx, dy = to_px(depot[0], depot[1])
        draw.rectangle([dx - 14, dy - 14, dx + 14, dy + 14], fill=(242, 106, 54), outline=(255, 255, 255), width=3)
        draw.text((dx + 18, dy - 10), "BASE DEPOT", fill=PALETTE["ink"], font=f_mono)

        # Determine current simulation mission time
        sim_t = prog * makespan if chapter == 4 else 0.0

        # Draw Camps
        visible_camps = len(camps) if chapter > 1 else max(1, int(math.ceil(len(camps) * min(1.0, prog * 1.25))))
        for idx, c in enumerate(camps[:visible_camps]):
            cx, cy = to_px(c["x"], c["y"])
            delivered = chapter == 4 and sim_t >= camp_arrival.get(c["id"], 9999.0)
            if delivered:
                c_fill = PALETTE["ok"]
            elif c["urgency"] == "KRITIS":
                c_fill = PALETTE["crit"]
            elif c["urgency"] == "TINGGI":
                c_fill = PALETTE["warn"]
            else:
                c_fill = (96, 165, 250)
            draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=c_fill, outline=(255, 255, 255), width=2)
            label = f"P{c['id']} {c['name'].replace('Posko ', '')}"
            if delivered:
                label += " [OK]"
            draw.text((cx + 13, cy - 9), label, fill=PALETTE["ink"], font=f_mono_sm)

        # Chapter 4: Animate Drones
        if chapter == 4:
            for d_idx, ds in enumerate(schedules):
                col = PALETTE["uav_colors"][d_idx % len(PALETTE["uav_colors"])]
                d_pos = depot
                for seg in ds["segments"]:
                    if seg["start_min"] <= sim_t <= seg["end_min"] and seg["path"]:
                        span = max(seg["end_min"] - seg["start_min"], 1e-6)
                        frac = (sim_t - seg["start_min"]) / span
                        path = seg["path"]
                        fi = frac * (len(path) - 1)
                        i0 = int(math.floor(fi))
                        i1 = min(i0 + 1, len(path) - 1)
                        al = fi - i0
                        d_pos = (path[i0][0] * (1 - al) + path[i1][0] * al, path[i0][1] * (1 - al) + path[i1][1] * al)
                        break
                else:
                    if ds["segments"] and sim_t >= ds["segments"][-1]["end_min"]:
                        d_pos = depot
                    else:
                        for seg in ds["segments"]:
                            if sim_t < seg["start_min"] and seg["path"]:
                                d_pos = tuple(seg["path"][0])
                                break
                ux, uy = to_px(d_pos[0], d_pos[1])
                draw_uav_sprite(draw, ux, uy, col, ds["callsign"])

        # Right Sidebar Telemetry
        sx = side_box[0] + 24
        sy = side_box[1] + 22
        draw.text((sx, sy), "TELEMETRI & PERFORMA ALGORITMA", fill=PALETTE["ink"], font=f_h2)
        sy += 38

        # Clock & Phase Card
        draw.rounded_rectangle([sx, sy, side_box[2] - 24, sy + 88], radius=10, fill=PALETTE["panel_alt"], outline=PALETTE["border"], width=1)
        draw.text((sx + 16, sy + 12), f"WAKTU MISI : {sim_t:05.1f} / {makespan:05.1f} menit", fill=PALETTE["accent"], font=f_mono)
        delivered_n = sum(1 for cid, arr in camp_arrival.items() if chapter == 4 and sim_t >= arr)
        draw.text((sx + 16, sy + 46), f"POSKO TERLAYANI : {delivered_n} / {len(camps)} Posko", fill=PALETTE["ok"] if delivered_n == len(camps) else PALETTE["ink"], font=f_mono)
        sy += 108

        # Pathfinding Benchmark Box
        draw.rounded_rectangle([sx, sy, side_box[2] - 24, sy + 204], radius=10, fill=PALETTE["panel_alt"], outline=PALETTE["border"], width=1)
        draw.text((sx + 16, sy + 12), "1. BENCHMARK PENCARIAN JALUR (PYTHON)", fill=PALETTE["ink"], font=f_h3)
        by = sy + 48
        max_exp = max(r["total_explored_nodes"] for r in bench) or 1
        for r in bench:
            lbl = "A* Search" if r["algorithm"] == "astar" else ("UCS" if r["algorithm"] == "ucs" else "Greedy BFS")
            col = (88, 153, 255) if r["algorithm"] == "astar" else ((159, 176, 194) if r["algorithm"] == "ucs" else (242, 106, 54))
            draw.text((sx + 16, by), f"{lbl:<11} {r['total_explored_nodes']:>6} simpul | Gap {r['optimality_gap_pct']:.1f}%", fill=PALETTE["ink"], font=f_mono_sm)
            bw = int((r["total_explored_nodes"] / max_exp) * 470)
            draw.rectangle([sx + 16, by + 22, sx + 16 + max(8, bw), by + 34], fill=col)
            by += 48
        sy += 224

        # GA Convergence Mini-Chart Box
        draw.rounded_rectangle([sx, sy, side_box[2] - 24, sy + 240], radius=10, fill=PALETTE["panel_alt"], outline=PALETTE["border"], width=1)
        draw.text((sx + 16, sy + 12), "2. KONVERGENSI GENETIC ALGORITHM", fill=PALETTE["ink"], font=f_h3)
        gx1, gy1, gx2, gy2 = sx + 22, sy + 52, side_box[2] - 42, sy + 218
        draw.rectangle([gx1, gy1, gx2, gy2], fill=(13, 21, 30), outline=PALETTE["border"], width=1)

        if chapter >= 3:
            gen_limit = len(ga_hist) if chapter >= 4 else max(2, int(len(ga_hist) * prog))
            all_vals = [h["best_objective"] for h in ga_hist] + [h["best_objective"] for h in sa_hist]
            vmin, vmax = min(all_vals) * 0.96, max(all_vals) * 1.03

            def chart_pt(idx_g: int, val: float) -> Tuple[float, float]:
                px = gx1 + (idx_g / max(1, len(ga_hist) - 1)) * (gx2 - gx1 - 16) + 8
                py = gy2 - ((val - vmin) / max(1e-5, vmax - vmin)) * (gy2 - gy1 - 16) - 8
                return (px, py)

            sa_pts = [chart_pt(i, sa_hist[i]["best_objective"]) for i in range(gen_limit)]
            ga_pts = [chart_pt(i, ga_hist[i]["best_objective"]) for i in range(gen_limit)]
            if len(sa_pts) >= 2:
                draw.line(sa_pts, fill=(242, 106, 54), width=2)
            if len(ga_pts) >= 2:
                draw.line(ga_pts, fill=(88, 153, 255), width=3)
            draw.text((gx1 + 10, gy1 + 8), f"GA Best: {ga_hist[gen_limit-1]['best_objective']:.1f}  |  SA: {sa_hist[gen_limit-1]['best_objective']:.1f}", fill=PALETTE["ink"], font=f_mono_sm)
        else:
            draw.text((gx1 + 40, (gy1 + gy2) // 2 - 8), "Menunggu matriks A* selesai...", fill=PALETTE["muted"], font=f_mono_sm)
        sy += 260

        # Active Fleet Summary Box
        draw.rounded_rectangle([sx, sy, side_box[2] - 24, side_box[3] - 20], radius=10, fill=PALETTE["panel_alt"], outline=PALETTE["border"], width=1)
        draw.text((sx + 16, sy + 12), "3. STATUS ARMADA MULTI-DRONE", fill=PALETTE["ink"], font=f_h3)
        dy_row = sy + 48
        for d_idx, ds in enumerate(schedules):
            col = PALETTE["uav_colors"][d_idx % len(PALETTE["uav_colors"])]
            draw.rectangle([sx + 16, dy_row + 4, sx + 26, dy_row + 24], fill=col)
            route_txt = " -> ".join(ds["route_labels"])
            if len(route_txt) > 52:
                route_txt = route_txt[:49] + "..."
            draw.text((sx + 36, dy_row), f"{ds['callsign']} ({len(ds['assigned_camp_indices'])} posko, {ds['total_distance_km']} km)", fill=PALETTE["ink"], font=f_body)
            draw.text((sx + 36, dy_row + 22), f"Rute: {route_txt}", fill=PALETTE["muted"], font=f_mono_sm)
            dy_row += 54

        # Scene 1 Opening Title Overlay (fade cleanly at start)
        if frame_idx < 65:
            draw.rounded_rectangle([140, 410, 1180, 620], radius=16, fill=(13, 21, 30), outline=PALETTE["accent"], width=3)
            draw.text((178, 438), "AERORELIEF : LOGISTIK MEDIS DRONE", fill=PALETTE["ink"], font=f_title_lg)
            draw.text((178, 502), "Optimasi Rute Multi-Drone Pasca Bencana Menggunakan A* & Genetic Algorithm", fill=PALETTE["accent"], font=f_h2)
            draw.text((178, 550), "Final Project EK234201 Konsep Kecerdasan Artifisial - Teknik Informatika ITS", fill=PALETTE["muted"], font=f_body)

        # Scene 4 Ending Hold Banner
        if frame_idx >= 610:
            draw.rounded_rectangle([240, 880, 1080, 968], radius=12, fill=(15, 65, 45), outline=PALETTE["ok"], width=3)
            draw.text(
                (278, 908),
                f"MISI SELESAI : {len(camps)}/{len(camps)} Posko Terlayani | Total Jarak {active_eval['total_distance_km']} km",
                fill=(255, 255, 255),
                font=f_h2,
            )

        # Save poster frame mid-flight (frame 525)
        if frame_idx == 525 and not poster_saved:
            frame.save(poster_path, optimize=True)
            frame.save(root_mockup_path, optimize=True)
            poster_saved = True

        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    stderr_out = proc.stderr.read().decode("utf-8", errors="ignore")
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"FFmpeg MP4 encode failed ({ret}): {stderr_out}")
    print(f"Saved HD MP4 video ({time.time() - t_start:.1f}s): {mp4_path}")

    # Convert MP4 -> compact 960x540 GIF (sped up 2.2x so full story fits in ~10s < 4MB)
    palette_png = os.path.join(MEDIA_DIR, "_palette_tmp.png")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", mp4_path,
            "-vf", "setpts=0.45*PTS,fps=12,scale=960:-1:flags=lanczos,palettegen=stats_mode=diff",
            palette_png,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", mp4_path, "-i", palette_png,
            "-lavfi", "setpts=0.45*PTS,fps=12,scale=960:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5",
            gif_path,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if os.path.exists(palette_png):
        os.remove(palette_png)
    print(f"Saved GIF preview: {gif_path}")


def main() -> None:
    print("1. Exporting precomputed JSON for 3 scenarios...")
    export_precomputed_json(os.path.join(WEB_STATIC_DIR, "precomputed.json"))

    print("2. Solving Semeru mission for charts and HD video...")
    semeru_mission = solve_mission({"scenario_id": "semeru", "num_drones": 3, "generations": 80})

    print("3. Generating flowchart PNG...")
    generate_flowchart_png(os.path.join(MEDIA_DIR, "flowchart_sistem.png"))

    print("4. Generating algorithm benchmark chart PNG...")
    generate_benchmark_png(semeru_mission, os.path.join(MEDIA_DIR, "benchmark_algorithms.png"))

    print("5. Rendering 1080p HD Video Mockup + GIF + Poster...")
    generate_video_and_gif(
        semeru_mission,
        mp4_path=os.path.join(MEDIA_DIR, "aerorelief_mockup_demo.mp4"),
        gif_path=os.path.join(MEDIA_DIR, "aerorelief_simulation.gif"),
        poster_path=os.path.join(MEDIA_DIR, "video_poster.png"),
        root_mockup_path=os.path.join(ROOT_DIR, "mockup_simulation.png"),
    )


if __name__ == "__main__":
    main()
