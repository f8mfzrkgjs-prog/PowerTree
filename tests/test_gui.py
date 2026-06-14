"""GUI集成测试：场景交互、连线功能"""
import sys
sys.path.insert(0, '.')
import pytest
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QColor, QUndoStack

from core.tree_model import TreeModel
from core.library_manager import LibraryManager
from core.component import PowerModule, Load
from app.canvas_scene import CanvasScene
from app.node_item import NodeItem
from app.edge_item import EdgeItem, TempLineItem, snap_to_edge_grid, build_ortho_path, EDGE_GRID


@pytest.fixture(scope='session')
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


class TestNodeItem:
    def test_creation(self, qapp):
        ni = NodeItem("n1", "buck", "BUCK_5V", node_width=220, node_height=120)
        assert ni.node_id == "n1"
        assert ni.node_name == "BUCK_5V"
        assert ni.comp_type == "buck"
        assert ni.node_width == 220
        assert ni.node_height == 120

    def test_set_component(self, qapp):
        ni = NodeItem("n1", "switching", "BUCK")
        comp = PowerModule(name="BUCK", calc_type="switching", comp_type="switching",
                           output_voltage=5.0, efficiency=90.0)
        ni.set_component(comp)
        assert ni._component is not None

    def test_fit_to_content(self, qapp):
        ni = NodeItem("n1", "switching", "BUCK", node_width=220, node_height=110)
        comp = PowerModule(name="BUCK", calc_type="switching", comp_type="switching")
        ni.set_component(comp)
        # switching: in=2, out=3 → content_h = 36+3*18+20+2=112 → snap to 120
        assert ni.node_height % 20 == 0
        assert ni.node_height >= 60

    def test_port_positions_grid_aligned(self, qapp):
        ni = NodeItem("n1", "load", "L", node_width=180, node_height=100)
        ni.setPos(QPointF(100, 100))
        port = ni.input_port_pos(0)
        assert int(port.x()) % 20 == 0  # node x is on grid, port at x=0 relative → same
        assert int(port.y()) % 20 == 0  # snapped to grid

    def test_is_editable(self, qapp):
        ni = NodeItem("n1", "switching", "BUCK")
        comp = PowerModule(name="BUCK", calc_type="switching", comp_type="switching")
        ni.set_component(comp)
        assert ni._is_editable_attr("vout")
        assert ni._is_editable_attr("vin")
        assert not ni._is_editable_attr("iin")  # switching iin is calculated
        assert not ni._is_editable_attr("ploss")


class TestEdgeItem:
    def test_ortho_path(self):
        wp = build_ortho_path(QPointF(0, 0), QPointF(200, 100))
        assert len(wp) >= 3
        all_ortho = all(wp[i].x() == wp[i+1].x() or wp[i].y() == wp[i+1].y()
                        for i in range(len(wp) - 1))
        assert all_ortho

    def test_edge_with_waypoints(self):
        wp = [QPointF(0, 0), QPointF(100, 0), QPointF(100, 60), QPointF(200, 60)]
        edge = EdgeItem("p1", "c1")
        edge.set_waypoints(wp)
        assert len(edge.waypoints) == 4
        assert edge.waypoints[0].x() == 0
        assert edge.waypoints[-1].x() == 200

    def test_contains_method(self):
        wp = [QPointF(0, 0), QPointF(100, 0), QPointF(100, 100)]
        edge = EdgeItem("p1", "c1")
        edge.set_waypoints(wp)
        # 线段上的点应被检测到
        assert edge.contains(QPointF(50, 0))
        # 远离线的点不应被检测到
        assert not edge.contains(QPointF(200, 200))


class TestCanvasScene:
    def test_scene_creation(self, qapp):
        library = LibraryManager()
        model = TreeModel()
        model.set_library(library)
        scene = CanvasScene(model)
        assert scene.tree_model is model

    def test_create_node(self, qapp):
        library = LibraryManager()
        library.add_template("BUCK", "switching", 220, 120, "#2864B4", 1, 1)
        model = TreeModel()
        model.set_library(library)
        scene = CanvasScene(model)
        item = scene.create_node(0, "BUCK_3V3", "switching", QPointF(100, 100))
        assert item is not None
        assert item.node_name == "BUCK_3V3"
        assert len(scene._node_items) == 1

    def test_node_position_snapped(self, qapp):
        library = LibraryManager()
        library.add_template("BUCK", "switching", 220, 120, "#2864B4", 1, 1)
        model = TreeModel()
        model.set_library(library)
        scene = CanvasScene(model)
        item = scene.create_node(0, "B", "switching", QPointF(33, 67))
        pos = item.pos()
        assert int(pos.x()) % 20 == 0
        assert int(pos.y()) % 20 == 0

    def test_snap_point(self, qapp):
        library = LibraryManager()
        model = TreeModel()
        model.set_library(library)
        scene = CanvasScene(model)
        assert scene.snap_point(QPointF(33, 67)) == QPointF(40, 60)
        assert scene.snap_point(QPointF(0, 0)) == QPointF(0, 0)

        scene.set_grid_snap(False)
        assert scene.snap_point(QPointF(33, 67)) == QPointF(33, 67)
        scene.set_grid_snap(True)

    def test_connect_two_nodes(self, qapp):
        library = LibraryManager()
        library.add_template("ROOT", "root", 180, 100, "#288C28", 0, 1)
        library.add_template("LOAD", "load", 180, 100, "#646464", 1, 0)
        model = TreeModel()
        model.set_library(library)
        scene = CanvasScene(model)

        root_item = scene.create_node(0, "Vin", "root", QPointF(0, 0))
        load_item = scene.create_node(1, "L", "load", QPointF(300, 0))

        root_node = model.find_node_by_id(root_item.node_id)
        load_node = model.find_node_by_id(load_item.node_id)
        assert model.connect_node(root_node, load_node)

        scene._create_edge(root_item.node_id, load_item.node_id)
        assert len(scene._edge_items) == 1
        edge = scene._edge_items[0]
        assert edge.parent_id == root_item.node_id
        assert edge.child_id == load_item.node_id

    def test_grid_background(self, qapp):
        library = LibraryManager()
        model = TreeModel()
        model.set_library(library)
        scene = CanvasScene(model)
        assert scene.grid_visible
        assert scene.grid_snap
        assert scene.grid_size == 20

        scene.set_grid_visible(False)
        assert not scene.grid_visible
        scene.set_grid_size(50)
        assert scene.grid_size == 50


class TestSnapAndAlignment:
    def test_grid_alignment_consistency(self):
        """验证格点系统一致性。"""
        from app.node_item import NODE_GRID_SIZE
        from app.edge_item import EDGE_GRID
        from app.canvas_scene import CanvasScene
        assert NODE_GRID_SIZE == 20
        assert EDGE_GRID == 20
        assert CanvasScene.GRID_SIZE == 20

    def test_port_snap(self, qapp):
        ni = NodeItem("n1", "buck", "B", node_width=220, node_height=120)
        comp = PowerModule(name="B", calc_type="switching", comp_type="switching")
        ni.set_component(comp)
        y = ni._port_y(0, 1)
        assert y % 20 == 0, f"Port Y should be grid-aligned, got {y}"
