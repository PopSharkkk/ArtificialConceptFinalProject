"""Predefined Indonesian post-disaster scenarios for AeroRelief."""

from typing import Dict, List
from .models import Camp, DroneSpec, HazardZone, Hill, Scenario

DRONE_COLORS = ["#1D5BD6", "#B86B00", "#0F7B58", "#B4234E"]
DRONE_CALLSIGNS = [
    "UAV-01 Rajawali",
    "UAV-02 Garuda",
    "UAV-03 Elang",
    "UAV-04 Merpati",
]


def build_drone_fleet(
    num_drones: int = 3,
    max_payload_kg: float = 5.0,
    max_battery_km: float = 80.0,
    speed_kmh: float = 72.0,
) -> List[DroneSpec]:
    fleet: List[DroneSpec] = []
    for i in range(max(1, min(4, num_drones))):
        fleet.append(
            DroneSpec(
                id=i + 1,
                callsign=DRONE_CALLSIGNS[i],
                max_payload_kg=max_payload_kg,
                max_battery_km=max_battery_km,
                speed_kmh=speed_kmh,
                color=DRONE_COLORS[i],
            )
        )
    return fleet


SCENARIOS: Dict[str, Scenario] = {
    "semeru": Scenario(
        id="semeru",
        title="Erupsi Gunung Semeru (Lumajang)",
        region="Kabupaten Lumajang, Jawa Timur",
        description=(
            "Jembatan Gladak Perak dan jalur darat terputus akibat aliran lahar dingin dan "
            "awan panas guguran. Armada drone menyuplai obat pernapasan, oksigen portabel, dan "
            "logistik medis dari Pos Komando Penanggal ke 8 posko pengungsian."
        ),
        grid_width=36,
        grid_height=26,
        depot=(3, 4),
        depot_name="Pos Komando Penanggal",
        camps=[
            Camp(1, "Posko Supiturang", 7, 17, "KRITIS", 2.2, 32.0, "Inhaler & Masker N95"),
            Camp(2, "Posko Pronojiwo", 11, 22, "KRITIS", 2.4, 42.0, "Tabung Oksigen Mini"),
            Camp(3, "Posko Oro-Oro Ombo", 5, 22, "TINGGI", 1.8, 48.0, "Obat Luka Bakar"),
            Camp(4, "Posko Sumberwuluh", 22, 20, "KRITIS", 2.5, 45.0, "Antibiotik & Infus"),
            Camp(5, "Posko Sumbermujur", 19, 6, "TINGGI", 1.6, 38.0, "Kit P3K & Cairan IV"),
            Camp(6, "Posko Candipuro", 28, 13, "TINGGI", 2.0, 50.0, "Obat Pernapasan"),
            Camp(7, "Posko Pasirian", 32, 6, "SEDANG", 1.5, 60.0, "Logistik Sanitasi"),
            Camp(8, "Posko Tempursari", 31, 22, "SEDANG", 2.1, 65.0, "Vaksin Tetanus"),
        ],
        hazard_zones=[
            HazardZone(
                "Zona Awan Panas Guguran", 11, 17, 11, 18, "Zona Erupsi"
            ),
            HazardZone(
                "Aliran Lahar Besuk Kobokan", 21, 25, 11, 15, "Bahaya Termal"
            ),
        ],
        hills=[
            Hill(14.0, 14.5, 5.5, 620.0),
            Hill(25.0, 18.0, 4.5, 360.0),
            Hill(7.5, 11.0, 4.0, 290.0),
        ],
        default_drones=build_drone_fleet(3, 5.0, 80.0, 72.0),
    ),
    "cianjur": Scenario(
        id="cianjur",
        title="Gempa Bumi & Longsor Cianjur",
        region="Kecamatan Cugenang, Jawa Barat",
        description=(
            "Guncangan gempa memicu longsor di lereng Cugenang dan memutus akses ambulans "
            "menuju desa-desa perbukitan. Drone mengirimkan darah donor, kit trauma ortopedi, "
            "serta serum darurat dari RSUD Sayang."
        ),
        grid_width=36,
        grid_height=26,
        depot=(4, 13),
        depot_name="Helipad RSUD Sayang",
        camps=[
            Camp(1, "Posko Cugenang", 12, 20, "KRITIS", 2.3, 35.0, "Kantong Darah O-"),
            Camp(2, "Posko Cipendawa", 10, 5, "KRITIS", 2.1, 38.0, "Kit Trauma Darurat"),
            Camp(3, "Posko Gasol", 19, 17, "TINGGI", 1.9, 45.0, "Analgesik & Perban"),
            Camp(4, "Posko Sarampad", 22, 6, "KRITIS", 2.4, 48.0, "Cairan Infus & Antibiotik"),
            Camp(5, "Posko Benjot", 29, 20, "TINGGI", 1.7, 55.0, "Obat Anak & Oralit"),
            Camp(6, "Posko Cibulakan", 28, 12, "SEDANG", 1.5, 62.0, "Peralatan Bedah Ringan"),
            Camp(7, "Posko Mangunkerta", 32, 5, "SEDANG", 2.0, 68.0, "Tenda Medis Lipat"),
        ],
        hazard_zones=[
            HazardZone(
                "Zona Longsor Tebing Cugenang", 13, 17, 9, 15, "Material Runtuhan"
            ),
            HazardZone(
                "Kabut Tebal Punggung Bukit", 23, 26, 13, 18, "Visibilitas Nol"
            ),
        ],
        hills=[
            Hill(15.0, 12.0, 5.0, 540.0),
            Hill(25.0, 15.0, 4.2, 410.0),
            Hill(9.0, 20.0, 3.8, 310.0),
        ],
        default_drones=build_drone_fleet(3, 5.0, 80.0, 72.0),
    ),
    "demak": Scenario(
        id="demak",
        title="Banjir Bandang Karanganyar (Demak)",
        region="Demak - Kudus, Jawa Tengah",
        description=(
            "Tanggul sungai jebol merendam jalur Pantura dan memutus akses perahu di area arus "
            "deras. Armada UAV mengantarkan antibiotik leptospirosis, insulin, dan logistik bayi "
            "sambil menghindari koridor menara SUTET dan zona badai angin."
        ),
        grid_width=36,
        grid_height=26,
        depot=(4, 20),
        depot_name="Posko Induk Tanggulangin",
        camps=[
            Camp(1, "Posko Karanganyar", 9, 9, "KRITIS", 2.0, 30.0, "Insulin & Obat Kronis"),
            Camp(2, "Posko Wonorejo", 15, 22, "KRITIS", 2.2, 34.0, "Antibiotik Leptospirosis"),
            Camp(3, "Posko Ketanjung", 16, 4, "TINGGI", 1.8, 42.0, "Kit Sanitasi & Oralit"),
            Camp(4, "Posko Undaan Kidul", 23, 19, "KRITIS", 2.3, 46.0, "Nutrisi & Obat Bayi"),
            Camp(5, "Posko Cangkring", 23, 8, "TINGGI", 1.7, 50.0, "Salep Infeksi & P3K"),
            Camp(6, "Posko Ngemplik", 29, 22, "SEDANG", 1.5, 58.0, "Tablet Penjernih Air"),
            Camp(7, "Posko Kedungwaru", 31, 14, "TINGGI", 2.1, 56.0, "Cairan Infus"),
            Camp(8, "Posko Jatirejo", 31, 5, "SEDANG", 1.9, 64.0, "Obat Demam & Vitamin"),
            Camp(9, "Posko Tuwang", 8, 15, "TINGGI", 1.4, 28.0, "Paket Gawat Darurat"),
        ],
        hazard_zones=[
            HazardZone(
                "Koridor Menara SUTET 500kV", 11, 13, 11, 18, "Interferensi Magnetik"
            ),
            HazardZone(
                "Sel Angin Badai Lokal", 19, 22, 11, 16, "Cuaca Ekstrem"
            ),
            HazardZone(
                "Area Tiang Pemancar", 26, 28, 8, 12, "Halangan Tinggi"
            ),
        ],
        hills=[
            Hill(20.0, 13.0, 4.5, 240.0),
            Hill(12.0, 14.0, 3.5, 190.0),
        ],
        default_drones=build_drone_fleet(4, 5.0, 80.0, 72.0),
    ),
}


def get_scenario(scenario_id: str) -> Scenario:
    return SCENARIOS.get(scenario_id, SCENARIOS["semeru"])


def list_scenarios() -> List[Dict[str, object]]:
    return [s.to_dict() for s in SCENARIOS.values()]
