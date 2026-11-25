"""Data models for AeroRelief disaster logistics simulation."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict, Any


@dataclass
class Camp:
    id: int
    name: str
    x: int
    y: int
    urgency: str = "TINGGI"  # KRITIS, TINGGI, SEDANG
    demand_kg: float = 2.0
    time_window_min: float = 45.0
    supply_type: str = "Obat Darurat & P3K"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DroneSpec:
    id: int
    callsign: str
    max_payload_kg: float = 5.0
    max_battery_km: float = 80.0
    speed_kmh: float = 72.0
    color: str = "#1D5BD6"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HazardZone:
    name: str
    x_min: int
    x_max: int
    y_min: int
    y_max: int
    hazard_type: str = "No-Fly Zone"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DynamicHazardEvent:
    id: str
    name: str
    trigger_min: float
    x_min: int
    x_max: int
    y_min: int
    y_max: int
    expire_min: Optional[float] = None
    hazard_type: str = "Rintangan Dinamis"
    cells: Optional[List[Tuple[int, int]]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.cells is not None:
            data["cells"] = [list(c) for c in self.cells]
        return data


@dataclass
class Hill:
    cx: float
    cy: float
    radius: float
    height_m: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Scenario:
    id: str
    title: str
    region: str
    description: str
    grid_width: int
    grid_height: int
    depot: Tuple[int, int]
    depot_name: str
    camps: List[Camp] = field(default_factory=list)
    hazard_zones: List[HazardZone] = field(default_factory=list)
    dynamic_events: List[DynamicHazardEvent] = field(default_factory=list)
    hills: List[Hill] = field(default_factory=list)
    default_drones: List[DroneSpec] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "region": self.region,
            "description": self.description,
            "grid_width": self.grid_width,
            "grid_height": self.grid_height,
            "depot": list(self.depot),
            "depot_name": self.depot_name,
            "camps": [c.to_dict() for c in self.camps],
            "hazard_zones": [h.to_dict() for h in self.hazard_zones],
            "dynamic_events": [e.to_dict() for e in self.dynamic_events],
            "hills": [hill.to_dict() for hill in self.hills],
            "default_drones": [d.to_dict() for d in self.default_drones],
        }
