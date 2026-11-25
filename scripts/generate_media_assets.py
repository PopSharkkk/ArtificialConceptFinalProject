"""
Generate all visual, analytical, and video assets for AeroRelief (with Dynamic Obstacles):
1. web/static/precomputed.json (3 solved disaster scenarios with dynamic obstacle events)
2. media/flowchart_sistem.png (Architectural flowchart + Mid-Flight Re-planning loop)
3. media/benchmark_algorithms.png (A* vs UCS vs Greedy & GA vs SA benchmark)
4. media/aerorelief_mockup_demo.mp4 (1920x1080 30fps 24s Mission Control & Dynamic Re-plan video)
5. media/video_poster.png & mockup_simulation.png (1920x1080 crisp UI frame showing dynamic obstacle detour)
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
    "dyn_fill": (120, 68, 12),
    "dyn_edge": (251, 191, 36),
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
    """Draw high-resolution system architecture flowchart including Dynamic Obstacle Re-planning."""
    W, H = 1800, 1020
    img = Image.new("RGB", (W, H), (246, 245, 240))
    draw = ImageDraw.Draw(img)

    f_title = load_font(FONT_BOLD, 33)
    f_sub = load_font(FONT_REG, 19)
    f_box_t = load_font(FONT_BOLD, 20)
    f_box_b = load_font(FONT_REG, 16)
    f_tag = load_font(FONT_MONO_BOLD, 14)

    draw.rectangle([0, 0, W, 110], fill=(20, 32, 43))
    draw.rectangle([0, 104, W, 110], fill=(200, 67, 24))
    draw.text((54, 20), "ARSITEKTUR SISTEM AERORELIEF & ADAPTASI RINTANGAN DINAMIS", fill=(255, 255, 255), font=f_title)
    draw.text(
        (54, 63),
        "Two-Tier AI Search (A* + Genetic Algorithm) dengan Umpan Balik Event-Driven Mid-Flight Re-planning",
        fill=(185, 200, 214),
        font=f_sub,
    )

    def draw_box(x1, y1, x2, y2, title, lines, fill=(255, 255, 255), border=(20, 32, 43), tag=None, tag_col=(200, 67, 24)):
        draw.rounded_rectangle([x1 + 4, y1 + 5, x2 + 4, y2 + 5], radius=12, fill=(215, 217, 220))
        draw.rounded_rectangle([x1, y1, x2, y2], radius=12, fill=fill, outline=border, width=3)
        ty = y1 + 16
        if tag:
            draw.rounded_rectangle([x1 + 16, y1 + 12, x1 + 16 + len(tag) * 9 + 22, y1 + 38], radius=6, fill=tag_col)
            draw.text((x1 + 26, y1 + 16), tag, fill=(255, 255, 255), font=f_tag)
            ty = y1 + 46
        draw.text((x1 + 18, ty), title, fill=(20, 32, 43), font=f_box_t)
        ly = ty + 30
        for line in lines:
            draw.text((x1 + 18, ly), line, fill=(66, 82, 98), font=f_box_b)
            ly += 23

    def draw_arrow(x1, y1, x2, y2, color=(20, 32, 43), label=None, label_bg=(246, 245, 240)):
        draw.line([x1, y1, x2, y2], fill=color, width=4)
        ang = math.atan2(y2 - y1, x2 - x1)
        ah = 13
        p1 = (x2 - ah * math.cos(ang - 0.45), y2 - ah * math.sin(ang - 0.45))
        p2 = (x2 - ah * math.cos(ang + 0.45), y2 - ah * math.sin(ang + 0.45))
        draw.polygon([(x2, y2), p1, p2], fill=color)
        if label:
            mx, my = (x1 + x2) // 2, (y1 + y2) // 2
            w_lbl = max(44, len(label) * 5 + 14)
            draw.rectangle([mx - w_lbl, my - 13, mx + w_lbl, my + 13], fill=label_bg)
            draw.text((mx - w_lbl + 8, my - 9), label, fill=color, font=f_tag)

    # Row 1
    draw_box(
        56, 148, 490, 336,
        "1. Input Data Bencana",
        [
            "- Peta grid & kontur elevasi (m)",
            "- Koordinat Depot & Posko Darurat",
            "- Zona Bahaya Tetap & Prakiraan Cuaca",
            "- Batas baterai & muatan armada UAV",
        ],
        tag="INPUT",
        tag_col=(35, 107, 89),
    )
    draw_arrow(490, 242, 585, 242)

    draw_box(
        585, 148, 1175, 336,
        "2. Perencanaan Jalur Aman (Algoritma A*)",
        [
            "- Hitung rute terpendek bebas rintangan aktif",
            "- Fungsi evaluasi: f(n) = g(n) + h(n) Euclidean",
            "- Penalti tanjakan elevasi & anti corner-cutting",
            "- Mendukung re-plan instan dari koordinat udara",
        ],
        tag="TIER 1: INFORMED SEARCH",
        tag_col=(29, 91, 214),
    )
    draw_arrow(1175, 242, 1270, 242)

    draw_box(
        1270, 148, 1744, 336,
        "3. Inisialisasi Populasi Rute",
        [
            "- Kromosom: permutasi Posko + pemisah UAV",
            "- Populasi awal N kandidat solusi",
            "- Penjadwalan awal seluruh armada drone",
        ],
        tag="TIER 2: LOCAL SEARCH",
        tag_col=(200, 67, 24),
    )

    draw_arrow(1507, 336, 1507, 412)

    # Row 2: GA Loop
    draw.rounded_rectangle([56, 412, 1744, 700], radius=16, fill=(234, 231, 223), outline=(200, 67, 24), width=3)
    draw.text((84, 430), "4. Optimasi Penjadwalan Multi-Drone (Genetic Algorithm VRPTW-BL)", fill=(200, 67, 24), font=f_box_t)

    draw_box(
        1270, 478, 1710, 668,
        "4a. Evaluasi Fitness VRPTW-BL",
        [
            "- Simulasi jarak, muatan, & reload Depot",
            "- Penalti keterlambatan urgensi Posko",
            "- Hitung nilai fungsi objektif armada",
        ],
        border=(200, 67, 24),
    )
    draw_arrow(1270, 573, 1155, 573)

    draw_box(
        815, 478, 1155, 668,
        "4b. Konvergen / Maks?",
        [
            "- Cek Generasi == Maksimal",
            "- Jika BELUM: lanjut operator GA",
            "- Jika YA: eksekusi penerbangan",
        ],
        border=(20, 32, 43),
    )
    draw_arrow(815, 573, 700, 573, label="BELUM", label_bg=(234, 231, 223))

    draw_box(
        90, 478, 700, 668,
        "4c. Seleksi, Crossover & Mutasi",
        [
            "- Elitism (2 individu terbaik dipertahankan)",
            "- Tournament Selection (k = 3)",
            "- Order Crossover (OX) & Mutasi Swap / 2-Opt",
        ],
        border=(29, 91, 214),
    )
    draw.line([395, 478, 395, 458, 1490, 458, 1490, 478], fill=(29, 91, 214), width=3)
    draw.polygon([(1490, 478), (1482, 464), (1498, 464)], fill=(29, 91, 214))

    draw_arrow(985, 668, 985, 765, label="YA")

    # Row 3: Execution + Dynamic Obstacle Feedback Loop
    draw_box(
        56, 765, 635, 965,
        "5. Deteksi Rintangan Dinamis / Baru",
        [
            "- Pantau bencana susulan, awan bergerak, & input user",
            "- Cek tabrakan jalur aktif: Path(t..end) vs Obs(t)",
            "- Hitung ulang rute A* langsung dari koordinat udara!",
        ],
        tag="ADAPTASI REAL-TIME",
        tag_col=(180, 83, 9),
        border=(180, 83, 9),
    )

    draw_box(
        720, 765, 1245, 965,
        "6. Eksekusi Penerbangan Multi-Drone",
        [
            "- Terbangkan armada mengikuti waypoints A*",
            "- Pantau sisa baterai, reload Depot, & status kirim",
            "- Perbarui lintasan seketika saat ada obstacle baru",
        ],
        tag="EKSEKUSI MISI",
        tag_col=(15, 123, 88),
    )

    draw_box(
        1325, 765, 1744, 965,
        "7. Web Interaktif & Video HD",
        [
            "- Visualisasi jalur lama vs jalur adaptif",
            "- Log waktu komputasi re-plan A*",
            "- Grafik analitik & manifes armada",
        ],
        tag="OUTPUT",
        tag_col=(20, 32, 43),
    )

    # Bidirectional / feedback arrows on Row 3 + loop up to A*
    draw_arrow(720, 845, 635, 845, color=(180, 83, 9))
    draw_arrow(635, 895, 720, 895, color=(29, 91, 214))
    draw_arrow(1245, 865, 1325, 865)

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
    f_lbl = load_font(FONT_BOLD, 14)

    draw.rectangle([0, 0, W, 84], fill=PALETTE["panel"])
    draw.line([0, 84, W, 84], fill=PALETTE["border"], width=2)
    draw.rectangle([28, 22, 42, 62], fill=PALETTE["accent"])
    draw.text((58, 16), "AERORELIEF MISSION CONTROL", fill=PALETTE["ink"], font=f_h1)
    draw.text(
        (58, 50),
        f"Skenario: {mission['scenario']['title']}  |  Dynamic A* Re-Planning + Genetic Algorithm",
        fill=PALETTE["muted"],
        font=f_sub,
    )

    map_box = (36, 108, 1284, 1012)
    side_box = (1308, 108, 1884, 1012)
    draw.rounded_rectangle(map_box, radius=14, fill=PALETTE["panel"], outline=PALETTE["border"], width=2)
    draw.rounded_rectangle(side_box, radius=14, fill=PALETTE["panel"], outline=PALETTE["border"], width=2)

    gw = mission["scenario"]["grid_width"]
    gh = mission["scenario"]["grid_height"]
    pad_l, pad_t, pad_r, pad_b = 56, 62, 36, 48
    px1 = map_box[0] + pad_l
    py1 = map_box[1] + pad_t
    px2 = map_box[2] - pad_r
    py2 = map_box[3] - pad_b
    cell_w = (px2 - px1) / gw
    cell_h = (py2 - py1) / gh

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

    for gx in range(gw + 1):
        x = px1 + gx * cell_w
        draw.line([x, py1, x, py2], fill=(35, 50, 66), width=1)
    for gy in range(gh + 1):
        y = py1 + gy * cell_h
        draw.line([px1, y, px2, y], fill=(35, 50, 66), width=1)

    for gx in range(0, gw + 1, 5):
        x = px1 + gx * cell_w
        draw.text((x - 8, py2 + 10), str(gx), fill=PALETTE["muted"], font=f_mono)
    for gy in range(0, gh + 1, 5):
        y = py2 - gy * cell_h
        draw.text((px1 - 32, y - 8), str(gy), fill=PALETTE["muted"], font=f_mono)

    for hz in mission["scenario"]["hazard_zones"]:
        hx1 = px1 + hz["x_min"] * cell_w
        hx2 = px1 + (hz["x_max"] + 1) * cell_w
        hy2 = py2 - hz["y_min"] * cell_h
        hy1 = py2 - (hz["y_max"] + 1) * cell_h
        draw.rectangle([hx1, hy1, hx2, hy2], fill=PALETTE["hazard_fill"], outline=PALETTE["hazard_edge"], width=3)
        step = 18
        for s in range(0, int((hx2 - hx1) + (hy2 - hy1)), step):
            sx1 = max(hx1, hx1 + s - (hy2 - hy1))
            sy1 = min(hy2, hy1 + s)
            sx2 = min(hx2, hx1 + s)
            sy2 = max(hy1, hy1 + s - (hx2 - hx1))
            if sx1 < sx2 and sy1 > sy2:
                draw.line([sx1, sy1, sx2, sy2], fill=(185, 45, 45), width=2)
        draw.text((hx1 + 8, hy1 + 8), hz["name"].upper(), fill=(254, 202, 202), font=f_lbl)

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


def _draw_dashed_polyline(draw: ImageDraw.ImageDraw, pts: List[Tuple[float, float]], color: Tuple[int, int, int], width: int = 2):
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        if i % 2 == 0:
            draw.line([(x1, y1), (x2, y2)], fill=color, width=width)


def generate_video_and_gif(
    static_mission: dict,
    dyn_mission: dict,
    mp4_path: str,
    gif_path: str,
    poster_path: str,
    root_mockup_path: str,
) -> None:
    """Render 720 frames at 1920x1080 (30fps, 24s) showcasing Dynamic Obstacle Re-planning."""
    t_start = time.time()
    base_img, geom = _build_video_base_canvas(dyn_mission)
    to_px = geom["to_px"]
    side_box = geom["side_box"]
    map_box = geom["map_box"]
    cell_w = geom["cell_w"]
    cell_h = geom["cell_h"]

    f_title_lg = load_font(FONT_BOLD, 42)
    f_h2 = load_font(FONT_BOLD, 21)
    f_h3 = load_font(FONT_BOLD, 17)
    f_body = load_font(FONT_REG, 15)
    f_mono = load_font(FONT_MONO_BOLD, 15)
    f_mono_sm = load_font(FONT_MONO, 13)

    depot = tuple(dyn_mission["depot"])
    camps = dyn_mission["camps"]
    explored_nodes = dyn_mission["pathfinding"]["explored_union"]
    bench = dyn_mission["pathfinding"]["benchmark"]
    ga_hist = dyn_mission["routing"]["ga_summary"]["history"]
    sa_hist = dyn_mission["routing"]["sa_summary"]["history"]

    static_schedules = static_mission["routing"]["active"]["evaluation"]["drone_schedules"]
    active_eval = dyn_mission["routing"]["active"]["evaluation"]
    schedules = active_eval["drone_schedules"]
    makespan = active_eval["makespan_min"]
    dyn_events = dyn_mission["dynamic"]["events"]
    replan_log = dyn_mission["dynamic"]["replan_log"]
    superseded_routes = dyn_mission["dynamic"]["superseded_routes"]

    camp_arrival: Dict[int, float] = {}
    for ds in schedules:
        for d_info in ds["deliveries"]:
            camp_arrival[d_info["camp_id"]] = d_info["arrival_min"]

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

    TOTAL_FRAMES = 720  # 24 seconds @ 30fps
    poster_saved = False

    def draw_uav_sprite(draw: ImageDraw.ImageDraw, cx: float, cy: float, color: Tuple[int, int, int], tag: str, alert: bool):
        r = 14
        draw.line([cx - r, cy - r, cx + r, cy + r], fill=color, width=3)
        draw.line([cx - r, cy + r, cx + r, cy - r], fill=color, width=3)
        for rx, ry in [(cx - r, cy - r), (cx + r, cy - r), (cx - r, cy + r), (cx + r, cy + r)]:
            draw.ellipse([rx - 5, ry - 5, rx + 5, ry + 5], outline=color, width=2, fill=(13, 21, 30))
        draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=color, outline=(255, 255, 255), width=2)
        box_w = len(tag) * 8 + 16
        b_col = PALETTE["accent"] if alert else color
        draw.rounded_rectangle([cx + 14, cy - 11, cx + 14 + box_w, cy + 10], radius=4, fill=(13, 21, 30), outline=b_col, width=2 if alert else 1)
        draw.text((cx + 20, cy - 9), tag, fill=(255, 255, 255), font=f_mono_sm)

    for frame_idx in range(TOTAL_FRAMES):
        frame = base_img.copy()
        draw = ImageDraw.Draw(frame)

        if frame_idx < 90:
            chapter = 1
            chapter_title = "TAHAP 0 : INISIALISASI PETA BENCANA & POSKO DARURAT"
            prog = frame_idx / 90.0
        elif frame_idx < 230:
            chapter = 2
            chapter_title = "TAHAP 1 : INFORMED SEARCH (ALGORITMA A* PATHFINDING)"
            prog = (frame_idx - 90) / 140.0
        elif frame_idx < 370:
            chapter = 3
            chapter_title = "TAHAP 2 : LOCAL SEARCH (GENETIC ALGORITHM VRPTW-BL)"
            prog = (frame_idx - 230) / 140.0
        else:
            chapter = 4
            chapter_title = "TAHAP 3 : PENERBANGAN & ADAPTASI RINTANGAN DINAMIS"
            prog = min(1.0, (frame_idx - 370) / 305.0)

        draw.text((map_box[0] + 56, map_box[1] + 18), chapter_title, fill=PALETTE["accent"], font=f_h2)
        sim_t = prog * makespan if chapter == 4 else 0.0

        # Chapter 2: A* explored frontier
        if chapter == 2:
            n_show = int(len(explored_nodes) * min(1.0, prog * 1.15))
            for node in explored_nodes[:n_show]:
                nx, ny = node
                x0 = geom["px1"] + nx * cell_w + 3
                y0 = geom["py2"] - (ny + 1) * cell_h + 3
                draw.rectangle([x0, y0, x0 + cell_w - 6, y0 + cell_h - 6], fill=(37, 99, 235), outline=(96, 165, 250))
        elif chapter >= 3:
            for node in explored_nodes[::2]:
                nx, ny = node
                x0 = geom["px1"] + nx * cell_w + 6
                y0 = geom["py2"] - (ny + 1) * cell_h + 6
                draw.rectangle([x0, y0, x0 + cell_w - 12, y0 + cell_h - 12], fill=(24, 52, 92))

        # Chapter 4: Render Active Dynamic / Moving Obstacles
        if chapter == 4:
            for ev in dyn_events:
                is_active = sim_t >= ev["trigger_min"] and (ev["expire_min"] is None or sim_t < ev["expire_min"])
                if is_active:
                    dx1 = geom["px1"] + ev["x_min"] * cell_w
                    dx2 = geom["px1"] + (ev["x_max"] + 1) * cell_w
                    dy2 = geom["py2"] - ev["y_min"] * cell_h
                    dy1 = geom["py2"] - (ev["y_max"] + 1) * cell_h
                    draw.rectangle([dx1, dy1, dx2, dy2], fill=PALETTE["dyn_fill"], outline=PALETTE["dyn_edge"], width=3)
                    step = 16
                    for s in range(0, int((dx2 - dx1) + (dy2 - dy1)), step):
                        sx1 = max(dx1, dx1 + s - (dy2 - dy1))
                        sy1 = min(dy2, dy1 + s)
                        sx2 = min(dx2, dx1 + s)
                        sy2 = max(dy1, dy1 + s - (dx2 - dx1))
                        if sx1 < sx2 and sy1 > sy2:
                            draw.line([sx1, sy1, sx2, sy2], fill=(217, 119, 6), width=2)
                    draw.text((dx1 + 6, dy1 + 6), f"BARU: {ev['name']}", fill=(254, 243, 199), font=f_mono_sm)

            # Render Superseded (Blocked Old) Routes as red dashed lines
            for sr in superseded_routes:
                if sim_t >= sr["trigger_min"] and len(sr["path"]) >= 2:
                    pts = [to_px(p[0], p[1]) for p in sr["path"]]
                    _draw_dashed_polyline(draw, pts, PALETTE["crit"], width=2)

        # Chapter 3 shows initial planned routes; Chapter 4 transitions from initial (<6.0m) to adapted routes
        if chapter == 3:
            for d_idx, ds in enumerate(static_schedules):
                col = PALETTE["uav_colors"][d_idx % len(PALETTE["uav_colors"])]
                segs = ds["segments"]
                if not segs:
                    continue
                n_segs = max(1, int(math.ceil(len(segs) * prog)))
                for seg in segs[:n_segs]:
                    if len(seg["path"]) >= 2:
                        pts = [to_px(p[0], p[1]) for p in seg["path"]]
                        draw.line(pts, fill=col, width=4 if not seg["is_reload_trip"] else 2)
        elif chapter == 4:
            first_trig = min((e["trigger_min"] for e in dyn_events), default=3.5)
            cur_scheds = static_schedules if sim_t < first_trig else schedules
            for d_idx, ds in enumerate(cur_scheds):
                col = PALETTE["uav_colors"][d_idx % len(PALETTE["uav_colors"])]
                for seg in ds["segments"]:
                    if len(seg["path"]) >= 2:
                        pts = [to_px(p[0], p[1]) for p in seg["path"]]
                        draw.line(pts, fill=col, width=4 if not seg["is_reload_trip"] else 2)

        # Depot
        dx, dy = to_px(depot[0], depot[1])
        draw.rectangle([dx - 14, dy - 14, dx + 14, dy + 14], fill=(242, 106, 54), outline=(255, 255, 255), width=3)
        draw.text((dx + 18, dy - 10), "BASE DEPOT", fill=PALETTE["ink"], font=f_mono)

        # Camps
        visible_camps = len(camps) if chapter > 1 else max(1, int(math.ceil(len(camps) * min(1.0, prog * 1.25))))
        for c in camps[:visible_camps]:
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

        # Chapter 4: Animate Drones + Re-plan Alert Banner
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
                recent_replan = any(
                    ds["callsign"] in r["affected_drones"] and r["time_min"] <= sim_t <= r["time_min"] + 6.5
                    for r in replan_log
                )
                tag = f"{ds['callsign'].split()[0]} RE-PLAN" if recent_replan else ds["callsign"].split()[0]
                draw_uav_sprite(draw, ux, uy, col, tag, recent_replan)

            # Dynamic Alert Overlay Banner when obstacle triggers
            active_alert = next(
                (r for r in replan_log if r["time_min"] <= sim_t <= r["time_min"] + 6.5),
                None,
            )
            if active_alert:
                draw.rounded_rectangle([96, 152, 1224, 214], radius=10, fill=(68, 32, 10), outline=PALETTE["warn"], width=2)
                draw.text(
                    (118, 162),
                    f"RINTANGAN BARU MUNCUL (MNT {active_alert['time_min']:.1f}) : {active_alert['event_name'].upper()}",
                    fill=PALETTE["warn"],
                    font=f_h3,
                )
                draw.text(
                    (118, 187),
                    f"Mid-Flight A* Re-planning otomatis pada {', '.join(active_alert['affected_drones'])} ({active_alert['runtime_ms']} ms)",
                    fill=PALETTE["ink"],
                    font=f_body,
                )

        # Right Sidebar Telemetry
        sx = side_box[0] + 24
        sy = side_box[1] + 20
        draw.text((sx, sy), "TELEMETRI & ADAPTASI DINAMIS", fill=PALETTE["ink"], font=f_h2)
        sy += 36

        draw.rounded_rectangle([sx, sy, side_box[2] - 24, sy + 88], radius=10, fill=PALETTE["panel_alt"], outline=PALETTE["border"], width=1)
        draw.text((sx + 16, sy + 12), f"WAKTU MISI : {sim_t:05.1f} / {makespan:05.1f} menit", fill=PALETTE["accent"], font=f_mono)
        replan_sofar = sum(1 for r in replan_log if chapter == 4 and sim_t >= r["time_min"])
        delivered_n = sum(1 for cid, arr in camp_arrival.items() if chapter == 4 and sim_t >= arr)
        draw.text(
            (sx + 16, sy + 44),
            f"TERKIRIM: {delivered_n}/{len(camps)}  |  RE-PLAN A*: {replan_sofar}x",
            fill=PALETTE["ok"] if delivered_n == len(camps) else PALETTE["ink"],
            font=f_mono,
        )
        sy += 104

        # Benchmark Box
        draw.rounded_rectangle([sx, sy, side_box[2] - 24, sy + 190], radius=10, fill=PALETTE["panel_alt"], outline=PALETTE["border"], width=1)
        draw.text((sx + 16, sy + 12), "1. BENCHMARK PENCARIAN JALUR (PYTHON)", fill=PALETTE["ink"], font=f_h3)
        by = sy + 44
        max_exp = max(r["total_explored_nodes"] for r in bench) or 1
        for r in bench:
            lbl = "A* Search" if r["algorithm"] == "astar" else ("UCS" if r["algorithm"] == "ucs" else "Greedy BFS")
            col = (88, 153, 255) if r["algorithm"] == "astar" else ((159, 176, 194) if r["algorithm"] == "ucs" else (242, 106, 54))
            draw.text((sx + 16, by), f"{lbl:<11} {r['total_explored_nodes']:>6} simpul | Gap {r['optimality_gap_pct']:.1f}%", fill=PALETTE["ink"], font=f_mono_sm)
            bw = int((r["total_explored_nodes"] / max_exp) * 470)
            draw.rectangle([sx + 16, by + 20, sx + 16 + max(8, bw), by + 31], fill=col)
            by += 45
        sy += 206

        # GA Convergence Mini-Chart
        draw.rounded_rectangle([sx, sy, side_box[2] - 24, sy + 216], radius=10, fill=PALETTE["panel_alt"], outline=PALETTE["border"], width=1)
        draw.text((sx + 16, sy + 12), "2. KONVERGENSI GENETIC ALGORITHM", fill=PALETTE["ink"], font=f_h3)
        gx1, gy1, gx2, gy2 = sx + 20, sy + 46, side_box[2] - 42, sy + 198
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
        sy += 232

        # Fleet & Dynamic Log Box
        draw.rounded_rectangle([sx, sy, side_box[2] - 24, side_box[3] - 18], radius=10, fill=PALETTE["panel_alt"], outline=PALETTE["border"], width=1)
        draw.text((sx + 16, sy + 12), "3. STATUS ARMADA & RE-PLANNING", fill=PALETTE["ink"], font=f_h3)
        dy_row = sy + 44
        for d_idx, ds in enumerate(schedules):
            col = PALETTE["uav_colors"][d_idx % len(PALETTE["uav_colors"])]
            draw.rectangle([sx + 16, dy_row + 4, sx + 26, dy_row + 24], fill=col)
            route_txt = " -> ".join(ds["route_labels"])
            if len(route_txt) > 50:
                route_txt = route_txt[:47] + "..."
            draw.text((sx + 36, dy_row), f"{ds['callsign']} [{ds['status']}] ({ds['total_distance_km']} km)", fill=PALETTE["ink"], font=f_body)
            draw.text((sx + 36, dy_row + 21), f"Rute: {route_txt}", fill=PALETTE["muted"], font=f_mono_sm)
            dy_row += 52

        if frame_idx < 60:
            draw.rounded_rectangle([140, 410, 1180, 620], radius=16, fill=(13, 21, 30), outline=PALETTE["accent"], width=3)
            draw.text((176, 438), "AERORELIEF : LOGISTIK DRONE ADAPTIF", fill=PALETTE["ink"], font=f_title_lg)
            draw.text((176, 502), "Optimasi A* & Genetic Algorithm dengan Adaptasi Rintangan Dinamis", fill=PALETTE["accent"], font=f_h2)
            draw.text((176, 550), "Final Project EK234201 Konsep Kecerdasan Artifisial - Teknik Informatika ITS", fill=PALETTE["muted"], font=f_body)

        if frame_idx >= 675:
            draw.rounded_rectangle([210, 880, 1110, 968], radius=12, fill=(15, 65, 45), outline=PALETTE["ok"], width=3)
            draw.text(
                (244, 908),
                f"MISI SELESAI : {len(camps)}/{len(camps)} Posko Terlayani | {len(replan_log)}x Manuver Re-plan Sukses",
                fill=(255, 255, 255),
                font=f_h2,
            )

        # Save poster at frame 425 (sim_t ~18.6m: both dynamic obstacles active + red dashed old paths + alert banner!)
        if frame_idx == 425 and not poster_saved:
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

    palette_png = os.path.join(MEDIA_DIR, "_palette_tmp.png")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", mp4_path,
            "-vf", "setpts=0.42*PTS,fps=12,scale=960:-1:flags=lanczos,palettegen=stats_mode=diff",
            palette_png,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", mp4_path, "-i", palette_png,
            "-lavfi", "setpts=0.42*PTS,fps=12,scale=960:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5",
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
    print("1. Exporting precomputed JSON for 3 scenarios (with dynamic events)...")
    export_precomputed_json(os.path.join(WEB_STATIC_DIR, "precomputed.json"))

    print("2. Solving Semeru static & dynamic missions for charts and HD video...")
    static_semeru = solve_mission({"scenario_id": "semeru", "num_drones": 3, "generations": 80, "enable_dynamic_events": False})
    dyn_semeru = solve_mission({"scenario_id": "semeru", "num_drones": 3, "generations": 80, "enable_dynamic_events": True})

    print("3. Generating flowchart PNG...")
    generate_flowchart_png(os.path.join(MEDIA_DIR, "flowchart_sistem.png"))

    print("4. Generating algorithm benchmark chart PNG...")
    generate_benchmark_png(dyn_semeru, os.path.join(MEDIA_DIR, "benchmark_algorithms.png"))

    print("5. Rendering 1080p HD Video Mockup + GIF + Poster...")
    generate_video_and_gif(
        static_semeru,
        dyn_semeru,
        mp4_path=os.path.join(MEDIA_DIR, "aerorelief_mockup_demo.mp4"),
        gif_path=os.path.join(MEDIA_DIR, "aerorelief_simulation.gif"),
        poster_path=os.path.join(MEDIA_DIR, "video_poster.png"),
        root_mockup_path=os.path.join(ROOT_DIR, "mockup_simulation.png"),
    )


if __name__ == "__main__":
    main()
