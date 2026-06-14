"""测试核心组件：Component, TreeModel, Calculator"""
import sys
import pytest
from PySide6.QtCore import QObject

sys.path.insert(0, '.')
from core.component import Component, PowerModule, Load
from core.tree_model import TreeNode, TreeModel
from core.calculator import Calculator, CalcResult, CalcWarnings


class TestComponent:
    def test_power_module_creation(self):
        pm = PowerModule(name="BUCK", comp_type="switching", calc_type="switching",
                         output_voltage=5.0, efficiency=90.0)
        assert pm.name == "BUCK"
        assert pm.calc_type == "switching"
        assert pm.output_voltage == 5.0
        assert pm.efficiency == 90.0

    def test_load_creation(self):
        ld = Load(name="负载1", input_voltage=3.3, output_current=1.5)
        assert ld.name == "负载1"
        assert ld.calc_type == "load"
        assert ld.output_current == 1.5

    def test_to_dict_from_dict(self):
        pm = PowerModule(name="LDO", comp_type="ldo", calc_type="ldo",
                         output_voltage=3.3, max_current=2.0,
                         efficiency_mode="curve", efficiency_curve=[(0.1, 85), (0.5, 90)])
        d = pm.to_dict()
        pm2 = PowerModule.from_dict(d)
        assert pm2.name == "LDO"
        assert pm2.output_voltage == 3.3
        assert pm2.efficiency_mode == "curve"
        assert len(pm2.efficiency_curve) == 2

    def test_load_from_dict(self):
        d = {"name": "L", "calc_type": "load", "input_voltage": 5.0, "output_current": 2.0}
        from core.component import Component
        c = Component.from_dict(d)
        assert isinstance(c, Load)
        assert c.calc_type == "load"


class TestTreeModel:
    def test_create_and_add_root(self):
        app = __import__('PySide6.QtWidgets', fromlist=['QApplication']).QApplication.instance()
        if app is None:
            app = __import__('PySide6.QtWidgets', fromlist=['QApplication']).QApplication(sys.argv)
        model = TreeModel()
        comp = PowerModule(name="R", comp_type="root", calc_type="root")
        node = model.create_tree_node(comp)
        model.add_root_node(node)
        assert len(model.root_nodes) == 1
        assert model.find_node_by_id(node.node_id) is not None

    def test_connect_and_disconnect(self):
        app = __import__('PySide6.QtWidgets', fromlist=['QApplication']).QApplication.instance()
        if app is None:
            app = __import__('PySide6.QtWidgets', fromlist=['QApplication']).QApplication(sys.argv)
        model = TreeModel()
        root = model.create_tree_node(PowerModule(name="R", comp_type="root", calc_type="root"))
        child = model.create_tree_node(Load(name="L"))
        model.add_root_node(root)
        ok = model.connect_node(root, child)
        assert ok
        assert child.parent_node is root
        assert len(root.children) == 1

        model.disconnect_node(child)
        assert child.parent_node is None
        assert len(root.children) == 0
        assert child in model.root_nodes

    def test_cycle_detection(self):
        app = __import__('PySide6.QtWidgets', fromlist=['QApplication']).QApplication.instance()
        if app is None:
            app = __import__('PySide6.QtWidgets', fromlist=['QApplication']).QApplication(sys.argv)
        model = TreeModel()
        a = model.create_tree_node(PowerModule(name="A", comp_type="root", calc_type="root"))
        b = model.create_tree_node(PowerModule(name="B", comp_type="switching"))
        model.add_root_node(a)
        model.connect_node(a, b)
        ok = model.connect_node(b, a)  # 尝试形成环
        assert not ok

    def test_clear_all(self):
        app = __import__('PySide6.QtWidgets', fromlist=['QApplication']).QApplication.instance()
        if app is None:
            app = __import__('PySide6.QtWidgets', fromlist=['QApplication']).QApplication(sys.argv)
        model = TreeModel()
        r1 = model.create_tree_node(PowerModule(name="R1", comp_type="root", calc_type="root"))
        r2 = model.create_tree_node(PowerModule(name="R2", comp_type="root", calc_type="root"))
        model.add_root_node(r1)
        model.add_root_node(r2)
        model.clear_all()
        assert len(model.root_nodes) == 0


class TestCalculator:
    def test_root_alone(self):
        model = TreeModel()
        comp = PowerModule(name="Vin", comp_type="root", calc_type="root", output_voltage=12.0)
        node = model.create_tree_node(comp)
        model.add_root_node(node)
        results, warnings = Calculator.calculate(model)
        assert len(results) == 1
        r = results[0]
        assert r.vin == 12.0
        assert r.vout == 12.0
        assert r.ploss == 0.0
        assert r.efficiency == 100.0

    def test_load_with_parent(self):
        model = TreeModel()
        root = model.create_tree_node(PowerModule(name="Vin", comp_type="root", calc_type="root",
                                                   output_voltage=12.0))
        load = model.create_tree_node(Load(name="L", input_voltage=5.0, output_current=2.0))
        buck = model.create_tree_node(PowerModule(name="BUCK", comp_type="switching", calc_type="switching",
                                                   efficiency=90.0))
        model.add_root_node(root)
        model.connect_node(root, buck)
        model.connect_node(buck, load)

        results, warnings = Calculator.calculate(model)
        assert len(results) == 3
        r_load = [r for r in results if r.name == "L"][0]
        r_buck = [r for r in results if r.name == "BUCK"][0]

        # 负载电流流经 BUCK
        assert r_buck.iout == pytest.approx(2.0, 0.01)
        # BUCK Vout 自动匹配负载 (自下而上)
        assert r_load.vin > 0
        # 功率为正
        assert r_buck.pin > 0
        assert r_buck.pout > 0

    def test_voltage_mismatch_warning(self):
        model = TreeModel()
        root = model.create_tree_node(PowerModule(name="Vin", comp_type="root", calc_type="root",
                                                   output_voltage=12.0))
        load = model.create_tree_node(Load(name="L", input_voltage=5.0, output_current=1.0))
        buck = model.create_tree_node(PowerModule(name="BUCK", comp_type="switching", calc_type="switching",
                                                   output_voltage=9.0, efficiency=90.0))
        model.add_root_node(root)
        model.connect_node(root, buck)
        model.connect_node(buck, load)

        results, warnings = Calculator.calculate(model)
        assert len(warnings.voltage_mismatch) >= 1

    def test_ldo_efficiency(self):
        model = TreeModel()
        root = model.create_tree_node(PowerModule(name="Vin", comp_type="root", calc_type="root",
                                                   output_voltage=5.0))
        ldo = model.create_tree_node(PowerModule(name="LDO", comp_type="ldo", calc_type="ldo",
                                                  output_voltage=3.3))
        model.add_root_node(root)
        model.connect_node(root, ldo)

        results, warnings = Calculator.calculate(model)
        r_ldo = [r for r in results if r.name == "LDO"][0]
        expected_eff = round(3.3 / 5.0 * 100, 1)
        assert r_ldo.efficiency == pytest.approx(expected_eff, 0.1)

    def test_system_summary(self):
        model = TreeModel()
        root = model.create_tree_node(PowerModule(name="Vin", comp_type="root", calc_type="root",
                                                   output_voltage=12.0))
        buck = model.create_tree_node(PowerModule(name="BUCK", comp_type="switching", calc_type="switching",
                                                   output_voltage=5.0, efficiency=90.0))
        load = model.create_tree_node(Load(name="L", input_voltage=5.0, output_current=3.0))
        model.add_root_node(root)
        model.connect_node(root, buck)
        model.connect_node(buck, load)

        results, warnings = Calculator.calculate(model)
        summary = Calculator.summary(results)
        assert summary['total_input_power'] > 0
        assert summary['system_efficiency'] > 0
        assert summary['total_loss'] >= 0
