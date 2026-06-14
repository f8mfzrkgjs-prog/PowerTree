from dataclasses import dataclass, field
from typing import Optional, List, Tuple


@dataclass
class Component:
    name: str
    comp_type: str
    calc_type: str = "switching"  # root, switching, ldo, isolated, load
    input_voltage: float = 0.0
    output_voltage: float = 0.0
    input_current: float = 0.0
    output_current: float = 0.0
    power_loss: float = 0.0
    efficiency: float = 100.0
    max_current: float = 0.0
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "comp_type": self.comp_type,
            "calc_type": self.calc_type,
            "input_voltage": self.input_voltage,
            "output_voltage": self.output_voltage,
            "input_current": self.input_current,
            "output_current": self.output_current,
            "power_loss": self.power_loss,
            "efficiency": self.efficiency,
            "max_current": self.max_current,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Component":
        calc_type = d.get("calc_type", "switching")
        if calc_type == "load":
            return Load.from_dict(d)
        return PowerModule.from_dict(d)


@dataclass
class PowerModule(Component):
    efficiency_mode: str = "fixed"
    efficiency_curve: List[Tuple[float, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["efficiency_mode"] = self.efficiency_mode
        d["efficiency_curve"] = self.efficiency_curve
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PowerModule":
        return cls(
            name=d.get("name", ""),
            comp_type=d.get("comp_type", "buck"),
            calc_type=d.get("calc_type", "switching"),
            input_voltage=d.get("input_voltage", 0.0),
            output_voltage=d.get("output_voltage", 0.0),
            input_current=d.get("input_current", 0.0),
            output_current=d.get("output_current", 0.0),
            power_loss=d.get("power_loss", 0.0),
            efficiency=d.get("efficiency", 100.0),
            max_current=d.get("max_current", 0.0),
            description=d.get("description", ""),
            efficiency_mode=d.get("efficiency_mode", "fixed"),
            efficiency_curve=[tuple(p) for p in d.get("efficiency_curve", [])],
        )


@dataclass
class Load(Component):
    comp_type: str = "load"
    calc_type: str = "load"

    @classmethod
    def from_dict(cls, d: dict) -> "Load":
        return cls(
            name=d.get("name", ""),
            comp_type="load",
            calc_type="load",
            input_voltage=d.get("input_voltage", 0.0),
            output_voltage=d.get("output_voltage", 0.0),
            input_current=d.get("input_current", 0.0),
            output_current=d.get("output_current", 0.0),
            power_loss=d.get("power_loss", 0.0),
            efficiency=d.get("efficiency", 100.0),
            max_current=d.get("max_current", 0.0),
            description=d.get("description", ""),
        )
