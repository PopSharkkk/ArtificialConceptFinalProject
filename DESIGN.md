# DESIGN.md : AeroRelief Tactical Cartography & Dispatch System

Dial: ENERGY 2 / RHYTHM 2 / MOTION 2

## 1. Visual Identity & Concept
AeroRelief uses an **Indonesian Disaster Response & Aviation Tactical Cartography** visual language inspired by BASARNAS/BNPB operational situation boards and aviation dispatch consoles. Every element serves tactical legibility: terrain contours, no-fly hazard zones, UAV callsign paths, and real-time search telemetry.

## 2. Color Palette (WCAG AA Verified)
Palette strictly uses 3 core surface/ink roles + 1 deliberate rescue accent, plus 4 colorblind-distinguishable UAV callsign colors on the tactical canvas.

### Light Mode ("Peta Topografi Terang")
- Surface Base: `#F6F5F0` (Topographic Chart Paper)
- Panel Surface: `#FFFFFF`
- Muted Surface: `#EAE7DF`
- Primary Ink: `#14202B` (Contrast on `#F6F5F0` > 13:1)
- Secondary Ink: `#425262` (Contrast on `#FFFFFF` > 7.5:1)
- Border Hairline: `#CFD6DE`
- Terrain Contour: `#236B59`
- Deliberate Accent: `#C84318` (SAR Rescue Orange, `#FFFFFF` label contrast > 4.6:1)

### Dark Mode ("Mode Operasi Malam")
- Surface Base: `#0D151E` (Night Operations Console)
- Panel Surface: `#14202D`
- Muted Surface: `#1C2B3B`
- Primary Ink: `#EDF2F7` (Contrast on `#0D151E` > 14:1)
- Secondary Ink: `#9FB0C2` (Contrast on `#14202D` > 6.5:1)
- Border Hairline: `#2A3B4E`
- Terrain Contour: `#34D399`
- Deliberate Accent: `#F26A36` (`#0D151E` label contrast > 6.8:1)

### UAV Callsign Palette (Light / Dark)
- UAV-01 Rajawali: `#1D5BD6` / `#5899FF`
- UAV-02 Garuda: `#B86B00` / `#F59E0B`
- UAV-03 Elang: `#0F7B58` / `#2DD4BF`
- UAV-04 Merpati: `#B4234E` / `#FB7185`

## 3. Typography
- **UI & Headings**: `Plus Jakarta Sans` (high legibility at compact telemetry sizes and clean Indonesian readability).
- **Telemetry & Formulas**: `IBM Plex Mono` (tabular numerals for grid coordinates, distance km, battery %, runtime ms, and mathematical formulas `f(n) = g(n) + h(n)`).

## 4. Layout & Rhythm
- Asymmetric command console at `#simulasi` (sidebar parameter & editor controls paired with full-height tactical canvas and transport bar).
- Analytical comparison at `#analitik` (question-titled canvas charts + interactive dispatch manifest table).
- Video & presentation artifacts at `#video-demo` (native HD video player, modal preview, and direct file downloads).
- Mathematical formulation & flowchart at `#metodologi` (two-column theory layout + system diagram + references).

## 5. Motion & States
- Motion serves simulation state only: smooth UAV interpolation along A* waypoints, play/pause/scrubbing controls, and subtle panel focus transitions.
- Explicit **Empty State** (when camp list is cleared), **Loading State** (while Python solver executes), and **Error State** (when hazard zones isolate a camp).
- Zero em-dashes (`—`), zero decorative emojis in UI chrome, zero fabricated statistics.
