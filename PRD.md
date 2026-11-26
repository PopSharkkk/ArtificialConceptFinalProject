# Product Requirements Document (PRD): AeroRelief

> **Versi:** 1.0  
> **Tanggal:** 26 November 2026  
> **Proyek:** AeroRelief — Emergency Medical Drone Logistics Simulator  
> **Konteks Akademik:** Final Project Konsep Kecerdasan Artifisial (KKA) — Departemen Teknik Informatika ITS  
> **Dokumen Terkait:** [README.md](README.md), [PROPOSAL_PROJECT_KKA.md](PROPOSAL_PROJECT_KKA.md), [aero_relief_prototype.py](aero_relief_prototype.py), [app_mockup.py](app_mockup.py)

---

## 1. Ringkasan Produk (Product Overview)

**AeroRelief** adalah aplikasi simulasi dan optimasi rute berbasis Python & Streamlit untuk mendistribusikan logistik medis darurat (darah, obat-obatan esensial, serum anti-bisa, dan perban) menggunakan armada drone otonom (UAV) pada wilayah pasca bencana yang akses daratnya terputus.

Sistem ini menggabungkan dua pendekatan kecerdasan artifisial secara berjenjang (*two-tier optimization*):
1. **Local Pathfinding (`A*` pada Ruang 2.5D):** Menentukan jalur terbang terpendek dan teraman antar-titik pada peta grid hingga `100×100` dengan memperhitungkan elevasi medan (penalti menanjak), zona terlarang statis (*no-fly zone*), serta *re-routing* saat muncul halangan dinamis di tengah penerbangan.
2. **Global Fleet Scheduling (`Genetic Algorithm` untuk Multi-Depot VRPTW-BL):** Mengalokasikan posko dan mengurutkan rute dari beberapa depot ke armada drone dengan mempertimbangkan kapasitas baterai, kapasitas muatan, serta batas waktu (*time window*) sesuai tingkat urgensi *golden hour*.

---

## 2. Latar Belakang & Tujuan

### 2.1 Masalah yang Diselesaikan
* Jalur darat di daerah bencana (gempa, banjir bandang, tanah longsor) sering lumpuh sehingga suplai medis kritis terhambat melewati *golden hour*.
* Pengiriman multi-drone secara manual tidak efisien dan rentan gagal jika drone kehabisan baterai, kelebihan muatan, melewati area berbahaya, atau terlambat menjangkau posko prioritas tinggi.
* Lingkungan pasca bencana bersifat dinamis (cuaca buruk atau reruntuhan baru dapat muncul mendadak saat drone sudah mengudara).

### 2.2 Tujuan Produk (Product Goals)
1. Menghasilkan rute dan jadwal pengiriman multi-depot, multi-drone yang aman, hemat energi, dan meminimalkan keterlambatan pengiriman kritis.
2. Memodelkan medan 2.5D secara realistis (memperhitungkan kerugian energi akibat naik elevasi) tanpa membebani komputasi seberat grid 3D penuh.
3. Menyediakan dashboard simulasi **Streamlit** yang interaktif dengan animasi *real-time*, kontrol parameter penuh, dan telemetri armada per drone.

---

## 3. Target Pengguna & User Stories

### 3.1 Persona Utama
1. **Koordinator Logistik Bencana (Operator Simulasi):** Mengatur lokasi depot, posko, urgensi medis, serta memantau jalannya misi pengiriman dan telemetri drone.
2. **Pengembang / Evaluator Akademik (KKA):** Menguji parameter algoritma `A*` dan `Genetic Algorithm`, menyuntikkan halangan dinamis saat simulasi berlangsung, dan mengevaluasi efektivitas rute.

### 3.2 User Stories
* **US-01 (Konfigurasi Peta & Skala):** Sebagai operator, saya ingin mengatur ukuran grid (hingga `100×100`), skala jarak horizontal/vertikal, serta peta elevasi agar simulasi sesuai kondisi wilayah bencana.
* **US-02 (Manajemen Depot & Posko):** Sebagai operator, saya ingin menambah, memindah, atau menghapus beberapa Depot, titik Posko, kebutuhan muatan medis (kg), tingkat urgensi, dan *time window* langsung dari UI.
* **US-03 (Manajemen Armada & Parameter GA):** Sebagai pengguna, saya ingin mengatur jumlah drone, kapasitas baterai, muatan maksimal, kecepatan, serta bobot penalti & parameter GA di sidebar.
* **US-04 (No-Fly Zone Statis & Dinamis):** Sebagai operator, saya ingin menempatkan *no-fly zone* statis sebelum simulasi dan memicu munculnya *dynamic obstacle* saat drone sedang terbang untuk melihat kemampuan *re-routing* otomatis.
* **US-05 (Simulasi Real-Time & Telemetri):** Sebagai operator, saya ingin melihat animasi pergerakan setiap drone di peta beserta sisa baterai, muatan, ETA, dan status pengiriman tiap posko secara langsung.

---

## 4. Cakupan Fitur (Scope)

### 4.1 Masuk Cakupan (In-Scope)
* Peta grid **2.5D** fleksibel (maksimal `100×100`) dengan skala horizontal & elevasi yang dapat dikonfigurasi.
* Penalti elevasi pada `A*` (memodelkan biaya energi ekstra saat menanjak).
* Dukungan **Multi-Depot** (1 atau lebih basecamp).
* **VRPTW-BL** pada Genetic Algorithm: batas baterai, batas kapasitas muatan, *time window*, dan urgensi posko.
* **No-Fly Zone statis** dan **Dynamic Obstacles** dengan *event-driven re-routing* (`A*` ulang saat jalur aktif terhalang).
* Antarmuka **Streamlit** dengan konfigurasi peta interaktif, animasi pergerakan drone *real-time*, dan panel telemetri per drone.

### 4.2 Di Luar Cakupan (Out-of-Scope / Pengembangan Lanjutan)
* Visualisasi grid **3D penuh** $(X, Y, Z)$ volumetrik.
* Grafik konvergensi *fitness* GA per generasi dan modul *benchmark* perbandingan `A*` vs `Dijkstra` / `Greedy Best-First Search` (dicatat di proposal awal, namun tidak masuk cakupan rilis utama PRD ini).
* Integrasi perangkat keras drone fisik (MAVLink/PX4) atau data GIS satelit eksternal *live*.

---

## 5. Persyaratan Fungsional (Functional Requirements)

### 5.1 Lingkungan 2.5D & Skala Spasial (`FR-ENV`)
* **FR-ENV-01 — Ukuran Grid Kustom:** Sistem harus mendukung konfigurasi dimensi grid `(width, height)` dari `10×10` hingga maksimal **`100×100`** (default: `30×30`).
* **FR-ENV-02 — Skala Jarak & Elevasi Konsisten:** Sistem harus menyediakan pilihan preset atau input skala horizontal (mis. `100 m/petak` atau `1 km/petak`) serta elevasi medan per petak dalam satuan meter (kelipatan `10 m`), dan mengonversi seluruh perhitungan jarak & heuristik ke satuan metrik yang seragam (meter/km).
* **FR-ENV-03 — Peta Elevasi 2.5D:** Setiap sel `(x, y)` memiliki nilai ketinggian permukaan `elevation[x][y]`. Sistem mendukung preset elevasi (datar, perbukitan sintetis, atau input zona elevasi).
* **FR-ENV-04 — Zona Terlarang Statis (*Static No-Fly Zone*):** Pengguna dapat mendefinisikan satu atau lebih area terlarang (mis. koordinat kotak atau daftar sel) yang tidak dapat dilalui drone sepanjang misi.

### 5.2 Pathfinding `A*` 2.5D & Dynamic Obstacles (`FR-PATH`)
* **FR-PATH-01 — Pencarian Jalur 8 Arah + Penalti Elevasi:** `A*` menavigasi 8 arah horizontal pada grid 2.5D dengan fungsi biaya:
  $$g(n) = g(n_{\text{prev}}) + d_{\text{horizontal}} + w_{\text{climb}} \cdot \max(0, \Delta z) + w_{\text{descent}} \cdot \max(0, -\Delta z)$$
  di mana penalti menanjak ($w_{\text{climb}}$) lebih besar untuk mencerminkan borosnya daya baterai saat naik altitude, serta heuristik *admissible* jarak Euclidean 3D (menghitung $\Delta x, \Delta y, \Delta z$ dalam satuan meter yang sama).
* **FR-PATH-02 — Batas Ketinggian (*Ceiling*):** Sel dengan elevasi melebihi batas ketinggian operasi drone (*max altitude*) diperlakukan sebagai sel tidak dapat dilalui (*impassable*).
* **FR-PATH-03 — Jenis & Simulasi Gerak *Dynamic Obstacles*:** Lingkungan mendukung dua jenis halangan dinamis yang berevolusi di setiap langkah waktu (*tick*) selama simulasi penerbangan berlangsung:
  1. **Cuaca Buruk (*Severe Weather / Storm Cell*):**
     * Dimodelkan sebagai klaster/zona badai bergerak yang mengalami **translasi posisi** secara kontinu sesuai **vektor angin global/lokal** (`wind_dx, wind_dy`) dan dapat berubah radius/intensitasnya.
     * Inti badai ekstrem bersifat **terlarang total (*impassable*)**, sedangkan area pinggiran angin kencang (*turbulence/headwind buffer*) dapat dimodelkan sebagai penalti biaya terbang & konsumsi baterai ekstra.
  2. **Daerah Api / Karhutla (*Wildfire Spread*):**
     * Dimodelkan sebagai zona kebakaran yang **merambat/menyebar (*propagation*)** dari sel terbakar ke sel tetangga menggunakan aturan *cellular automata* probabilistik.
     * Laju dan arah penyebaran api dipengaruhi oleh **arah & kecepatan angin** (lebih cepat searah angin) serta **kemiringan elevasi 2.5D** (api cenderung lebih cepat merambat naik ke kontur lebih tinggi), dan tidak merambat ke sel yang memang tidak mudah terbakar (mis. area penghalang/air jika dikonfigurasi).
     * Sel api aktif (beserta zona panas/asap tebal di atasnya) bersifat **terlarang total (*impassable*)** bagi drone.
* **FR-PATH-04 — Event-Driven Re-routing:** Pada setiap pembaruan langkah waktu ketika **Cuaca Buruk** berpindah atau **Api/Karhutla** meluas:
  1. Sistem memeriksa apakah sisa waypoint drone yang sedang mengudara berpotongan dengan sel badai/api baru (atau memasuki zona penalti cuaca yang tidak lagi efisien/aman).
  2. Hanya drone yang jalurnya terdampak yang menjalankan ulang `A*` dari posisi saat ini menuju target berikutnya untuk menghindar secara real-time.
  3. Jika jalur baru menyebabkan pelanggaran batas baterai untuk menyelesaikan sisa rute atau posko tujuan tertutup api/badai, sistem menandai kebutuhan *re-scheduling* sisa posko yang belum terkirim ke armada yang tersedia (atau mengarahkan drone kembali ke depot terdekat).

### 5.3 Optimasi Armada Multi-Depot VRPTW-BL dengan Genetic Algorithm (`FR-GA`)
* **FR-GA-01 — Multi-Depot:** Sistem mendukung $\ge 1$ Depot sebagai titik asal dan akhir rute drone. Setiap drone memiliki `home_depot` (atau dapat kembali ke depot terdekat sesuai aturan konfigurasi).
* **FR-GA-02 — Kapasitas Muatan & Baterai:**
  * Setiap posko memiliki permintaan muatan medis (kg). Total muatan dalam satu perjalanan drone tidak boleh melebihi `max_payload_kg`.
  * Total konsumsi energi satu perjalanan (dipengaruhi jarak, elevasi menanjak, dan beban muatan) tidak boleh melebihi `max_battery_capacity`.
* **FR-GA-03 — Time Window & Urgensi Posko:** Setiap posko memiliki tingkat urgensi (mis. `Kritis`, `Tinggi`, `Normal`) dan batas waktu kedatangan (*time window* `due_time`).
* **FR-GA-04 — Fungsi Fitness VRPTW-BL:** Genetic Algorithm mengevaluasi kromosom berdasarkan biaya gabungan:
  $$\text{Fitness} = \frac{1}{\alpha \cdot \text{Total Cost (Jarak/Energi)} + \beta \cdot \text{Late Penalty (berbobot urgensi)} + \gamma \cdot \text{Battery/Payload Violation Penalty} + \epsilon}$$
  dengan operator *Tournament Selection*, *Order Crossover (OX)* / pemisah rute valid, serta mutasi (*Swap / Inversion*).
* **FR-GA-05 — Penanganan Rute Tidak Terjangkau:** Jika tidak ada jalur aman menuju suatu posko (terisolasi total oleh obstacle) atau kendala fisik mustahil dipenuhi, sistem menampilkan peringatan eksplisit di UI tanpa mengalami *crash*.

### 5.4 Antarmuka Streamlit, Animasi & Telemetri (`FR-UI`)
* **FR-UI-01 — Konfigurasi Interaktif di Sidebar/Panel:**
  * Pengaturan ukuran grid (maks `100×100`), skala sel, dan preset/edit elevasi.
  * Pengaturan depot, posko (koordinat, berat muatan, urgensi, *time window*), *no-fly zone* statis, serta **konfigurasi simulasi *dynamic obstacle*** (arah & kecepatan angin, titik awal & radius *Cuaca Buruk*, titik sumber & laju rambat *Api/Karhutla*).
  * Konfigurasi spesifikasi drone: jumlah drone, kapasitas baterai, muatan maksimal (kg), kecepatan jelajah, serta parameter GA (`pop_size`, `generations`, bobot $\alpha, \beta, \gamma$) dengan nilai default siap pakai.
* **FR-UI-02 — Visualisasi Peta 2.5D Interaktif:**
  * Menampilkan depot, posko (dengan warna/ikon sesuai tingkat urgensi & status pengiriman), zona elevasi (*contour/heatmap* ringan), *no-fly zone* statis, **sel Cuaca Buruk bergerak** (mis. biru/ungu transparan + indikator arah angin), **sel Daerah Api/Karhutla** (mis. oranye/merah menyala untuk api aktif & abu-abu asap/hangus), serta lintasan optimal tiap drone dengan warna berbeda.
* **FR-UI-03 — Animasi Pergerakan Real-Time:**
  * Kontrol simulasi (`Play / Pause / Step / Reset`, pengatur kecepatan simulasi, serta tombol injeksi/toggle **Cuaca Buruk** dan **Titik Api Karhutla** saat drone sedang terbang).
  * Menampilkan posisi tiap drone bergerak mengikuti waypoint `A*` sekaligus pergerakan awan badai dan penyebaran api per langkah waktu (*tick*).
* **FR-UI-04 — Panel Telemetri Per Drone & Status Posko:**
  * Menampilkan per drone: status misi (`Standby`, `Flying`, `Delivering`, `Re-routing`, `Returning`, `Low Battery`), sisa baterai (`%`), sisa muatan (`kg`), target posko aktif, dan **ETA** (estimasi waktu tiba).
  * Menampilkan daftar posko beserta status (`Pending`, `In Transit`, `Delivered On-Time`, `Delivered Late`, `Unreachable`).

---

## 6. Persyaratan Non-Fungsional (Non-Functional Requirements)

1. **Performa & Responsivitas (`NFR-PERF`):**
   * Perhitungan matriks jarak `A*` pada grid **`100×100`** 2.5D dengan 10 posko harus selesai dalam **$\le 2$ detik** (dicapai melalui pemanfaatan simetri matriks / *multi-target search* dan pengindeksan efisien).
   * Di Streamlit, hasil matriks jarak statis harus di-cache (`@st.cache_data`) agar mengubah parameter GA tidak menghitung ulang seluruh `A*`.
   * *Event-driven re-routing* untuk 1 segmen drone terdampak pada `100×100` harus selesai dalam **$\le 100$ ms** agar animasi tidak macet.
2. **Keandalan & Validitas Solusi (`NFR-REL`):**
   * Tidak ada jalur drone yang melintasi sel *no-fly zone* statis maupun dinamis aktif.
   * Tidak ada posko valid yang dikunjungi ganda atau terlewat tanpa status yang jelas.
3. **Maintainability (`NFR-MAINT`):**
   * Pemisahan tegas antara *Simulation & Optimization Engine* (logika grid 2.5D, `A*`, `GA`, model telemetri) dan *Presentation Layer* (Streamlit UI), melanjutkan struktur dari [aero_relief_prototype.py](aero_relief_prototype.py) dan [app_mockup.py](app_mockup.py).
4. **Usability (`NFR-USE`):**
   * Aplikasi langsung dapat dijalankan dengan skenario default tanpa wajib mengisi seluruh data secara manual terlebih dahulu.

---

## 7. Model Data Konseptual

| Entitas | Atribut Utama |
| :--- | :--- |
| **`GridEnvironment25D`** | `width` ($\le 100$), `height` ($\le 100$), `cell_size_m`, `elevation_grid` (m), `max_altitude_m`, `wind_vector (dx, dy, speed)`, `static_obstacles` |
| **`WeatherStormCell`** | `id`, `center (x, y)`, `core_radius`, `turbulence_radius`, `velocity (dx, dy)`, `penalty_multiplier`, `active` |
| **`WildfireHazard`** | `id`, `active_fire_cells`, `burned_cells`, `base_spread_prob`, `wind_bias`, `slope_bias`, `active` |
| **`Depot`** | `id`, `name`, `position (x, y)` |
| **`DisasterCamp`** | `id`, `name`, `position (x, y)`, `demand_kg`, `urgency` (`CRITICAL` / `HIGH` / `NORMAL`), `time_window_end_min`, `status` |
| **`DroneConfig`** | `id`, `home_depot_id`, `max_battery_wh` (atau unit energi), `max_payload_kg`, `speed_mps`, `climb_penalty_factor` |
| **`DroneState` (Runtime)** | `drone_id`, `current_pos (x, y)`, `remaining_battery_pct`, `current_payload_kg`, `assigned_route`, `active_waypoints`, `eta_min`, `state` |

---

## 8. Kesenjangan Prototipe Saat Ini vs. Target PRD

| Komponen | Kondisi Saat Ini ([aero_relief_prototype.py](aero_relief_prototype.py) & [app_mockup.py](app_mockup.py)) | Target PRD Ini |
| :--- | :--- | :--- |
| **Dimensi & Skala** | 2D tetap `30×30` (hardcoded) | 2.5D kustom hingga `100×100` dengan skala m/km & peta elevasi |
| **Depot** | 1 depot tetap di `(2, 2)` | Multi-depot ($\ge 1$) dapat diatur dari UI |
| **Kendala Rute** | Hanya total jarak, dibagi rata per chunk | VRPTW-BL (baterai, muatan, *time window*, urgensi) |
| **Halangan** | 1 kotak statis `(10..18, 10..18)` | Multi *no-fly zone* statis + **Cuaca Buruk bergerak** & **Api/Karhutla merambat** + *re-routing* `A*` saat terbang |
| **Visualisasi** | Peta statis Matplotlib + teks jadwal | Peta interaktif + heatmap elevasi + animasi gerak cuaca, api & drone *real-time* + telemetri per drone |

---

## 9. Kriteria Penerimaan (Acceptance Criteria)

1. **Grid & Elevasi 2.5D:** Pengguna dapat mengubah ukuran grid hingga `100×100`, memilih skala jarak, dan jalur `A*` terbukti memilih memutar atau memilih kontur rendah saat penalti elevasi melebihi biaya memutar.
2. **Multi-Depot & VRPTW-BL:** Dengan $\ge 2$ depot, beberapa posko bervariasi urgensi & berat muatan, serta batas baterai aktif, GA menghasilkan pembagian rute yang tidak melebihi kapasitas muatan dan baterai masing-masing drone, serta memprioritaskan posko *time window* ketat.
3. **Simulasi Gerak Cuaca Buruk & Api Karhutla:** Selama simulasi berjalan (`Play`), sel *Cuaca Buruk* terlihat berpindah mengikuti vektor angin dan sel *Api Karhutla* terlihat merambat ke sel tetangga (dipengaruhi arah angin & kemiringan elevasi).
4. **Dynamic Obstacle Re-routing:** Saat pergerakan badai atau rambatan api memotong jalur aktif drone, drone yang terdampak menghitung ulang jalurnya via `A*` secara otomatis tanpa menabrak inti badai/api aktif dan memperbarui telemetri ETA/baterai.
5. **Telemetri Real-Time:** Selama animasi berjalan, sisa baterai, sisa muatan setelah pengantaran di tiap posko, ETA, dan status posko (`Pending` $\rightarrow$ `Delivered`) diperbarui konsisten hingga seluruh armada kembali ke depot.
6. **Integrasi Streamlit:** Seluruh fitur konfigurasi, simulasi, dan telemetri berjalan lancar melalui `streamlit run` tanpa perlu mengedit kode sumber secara manual.
