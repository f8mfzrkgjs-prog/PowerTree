from dataclasses import dataclass, field
from typing import List, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CalculatorConfig

from .tree_model import TreeModel, TreeNode
from .component import Component, PowerModule, Load


@dataclass
class CalcResult:
    node_id: str
    name: str
    comp_type: str
    calc_type: str
    vin: float
    vout: float
    iin: float
    iout: float
    pin: float
    pout: float
    ploss: float
    efficiency: float

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in [
            "node_id", "name", "comp_type", "calc_type",
            "vin", "vout", "iin", "iout",
            "pin", "pout", "ploss", "efficiency",
        ]}


@dataclass
class CalcWarnings:
    voltage_mismatch: List[str] = field(default_factory=list)
    overcurrent: List[str] = field(default_factory=list)
    low_efficiency: List[str] = field(default_factory=list)


class Calculator:
    VOLTAGE_TOLERANCE = CalculatorConfig.VOLTAGE_TOLERANCE

    @staticmethod
    def calculate(tree_model: TreeModel) -> tuple[List[CalcResult], CalcWarnings]:
        results = []
        warnings = CalcWarnings()
        for root in tree_model.root_nodes:
            r, w = Calculator._calc_subtree(root, None)
            results.extend(r)
            warnings.voltage_mismatch.extend(w.voltage_mismatch)
            warnings.overcurrent.extend(w.overcurrent)
            warnings.low_efficiency.extend(w.low_efficiency)
        return results, warnings

    @staticmethod
    def _calc_subtree(node: TreeNode, parent_vin: Optional[float]) -> tuple[List[CalcResult], CalcWarnings]:
        results = []
        warnings = CalcWarnings()
        component = node.component
        ct = getattr(component, 'calc_type', 'switching')

        effective_vout = component.output_voltage
        if ct != "load":
            for child in node.children:
                cv = child.component.input_voltage
                if cv > 0:
                    effective_vout = max(effective_vout, cv)

        total_child_iin = 0.0
        for child in node.children:
            child_results, child_w = Calculator._calc_subtree(child, effective_vout)
            results.extend(child_results)
            warnings.voltage_mismatch.extend(child_w.voltage_mismatch)
            warnings.overcurrent.extend(child_w.overcurrent)
            warnings.low_efficiency.extend(child_w.low_efficiency)
            if child_results and child_results[-1].iin > 0:
                total_child_iin += child_results[-1].iin

        vin = 0.0
        vout = effective_vout
        iout = component.output_current
        iin = 0.0
        efficiency = 100.0

        if ct == "load":
            vin = parent_vin if parent_vin is not None else component.input_voltage
            vout = 0.0
            iin = component.output_current
            iout = iin
            pin = vin * iin
            pout = 0.0
            ploss = pin
            efficiency = 0.0

            if parent_vin is not None and vin > 0:
                expected = component.input_voltage
                if expected > 0 and abs(vin - expected) / expected > Calculator.VOLTAGE_TOLERANCE:
                    warnings.voltage_mismatch.append(
                        f"负载「{component.name}」电压不匹配："
                        f"上游输出 {vin:.2f}V，负载期望 {expected:.2f}V"
                    )

        elif ct == "root":
            vin = component.output_voltage
            vout = vin
            if node.children:
                iout = total_child_iin
            iin = iout
            pin = vin * iin
            pout = pin
            ploss = 0.0
            efficiency = 100.0

        elif ct == "isolated":
            vin = parent_vin if parent_vin is not None else 0.0
            vout = vin
            if node.children:
                iout = total_child_iin
            iin = iout
            pin = vin * iin
            pout = pin
            ploss = 0.0
            efficiency = 100.0

        elif ct == "ldo":
            vin = parent_vin if parent_vin is not None else component.input_voltage
            if node.children:
                iout = total_child_iin
            iin = iout
            pin = vin * iin
            pout = vout * iout
            ploss = pin - pout
            efficiency = round(vout / vin * 100, 1) if vin > 0 else 0.0

            if component.max_current > 0 and iout > component.max_current:
                warnings.overcurrent.append(
                    f"「{component.name}」过流：Iout={iout:.3f}A > 最大 {component.max_current:.3f}A"
                )

        else:  # switching
            vin = parent_vin if parent_vin is not None else component.input_voltage
            if node.children:
                iout = total_child_iin
            eff = component.efficiency / 100.0
            if getattr(component, 'efficiency_mode', 'fixed') == "curve":
                curve = getattr(component, 'efficiency_curve', [])
                if curve:
                    eff = Calculator._interpolate_efficiency(curve, vout, iout) / 100.0
            if eff > 0 and vin > 0:
                iin = (vout * iout) / (eff * vin)
            else:
                iin = 0.0
            pin = vin * iin
            pout = vout * iout
            ploss = pin - pout
            efficiency = eff * 100.0

            if component.max_current > 0 and iout > component.max_current:
                warnings.overcurrent.append(
                    f"「{component.name}」过流：Iout={iout:.3f}A > 最大 {component.max_current:.3f}A"
                )
            if efficiency < CalculatorConfig.LOW_EFFICIENCY_THRESHOLD and iout > 0:
                warnings.low_efficiency.append(
                    f"「{component.name}」效率偏低：η={efficiency:.1f}%"
                )

        results.append(CalcResult(
            node_id=node.node_id,
            name=component.name,
            comp_type=component.comp_type,
            calc_type=ct,
            vin=round(vin, 4),
            vout=round(vout, 4),
            iin=round(iin, 4),
            iout=round(iout, 4),
            pin=round(pin, 4),
            pout=round(pout, 4),
            ploss=round(ploss, 4),
            efficiency=round(efficiency, 2),
        ))
        return results, warnings

    @staticmethod
    def _interpolate_efficiency(curve, vout: float, iout: float) -> float:
        if not curve:
            return 100.0
        target_x = iout
        points = sorted(curve, key=lambda p: p[0])
        if not points:
            return 100.0
        if target_x <= points[0][0]:
            return points[0][1]
        if target_x >= points[-1][0]:
            return points[-1][1]
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            if x1 <= target_x <= x2:
                ratio = (target_x - x1) / (x2 - x1) if x2 != x1 else 0
                return y1 + ratio * (y2 - y1)
        return points[-1][1]

    @staticmethod
    def summary(results: List[CalcResult]) -> dict:
        total_pin = sum(r.pin for r in results if r.calc_type == "root")
        total_pout = sum(r.pout for r in results if r.calc_type == "root")
        total_ploss = sum(r.ploss for r in results)
        system_eff = (total_pout / total_pin * 100) if total_pin > 0 else 0.0
        max_iin = max((r.iin for r in results), default=0.0)
        return {
            "total_input_power": round(total_pin, 4),
            "total_output_power": round(total_pout, 4),
            "total_loss": round(total_ploss, 4),
            "system_efficiency": round(system_eff, 2),
            "max_bus_current": round(max_iin, 4),
        }
