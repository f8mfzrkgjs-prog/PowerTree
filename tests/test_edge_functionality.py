"""
连线功能测试工具 - 验证模块间连线是否有异常
运行方式: python tests/test_edge_functionality.py
"""
import sys
sys.path.insert(0, '.')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF

from core.tree_model import TreeModel
from core.library_manager import LibraryManager
from app.canvas_scene import CanvasScene
from app.node_item import NodeItem


class EdgeTestRunner:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.results = []
        self.passed = 0
        self.failed = 0
        
    def setup(self):
        self.library = LibraryManager()
        self.library.add_template('ROOT', 'root', 180, 100, '#288C28', 0, 1)
        self.library.add_template('BUCK', 'switching', 220, 120, '#2864B4', 1, 1)
        self.library.add_template('LDO', 'ldo', 180, 100, '#A07828', 1, 1)
        self.library.add_template('LOAD', 'load', 160, 80, '#646464', 1, 0)
        
        self.model = TreeModel()
        self.model.set_library(self.library)
        self.scene = CanvasScene(self.model)
        
    def log(self, test_name: str, passed: bool, message: str = ""):
        status = "[PASS]" if passed else "[FAIL]"
        self.results.append((test_name, passed, message))
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        print(f"  {status}: {test_name}")
        if message and not passed:
            print(f"         {message}")
    
    def test_basic_connection(self):
        print("\n[测试1] 基本连线创建")
        root = self.scene.create_node(0, 'VIN', 'root', QPointF(100, 100))
        buck = self.scene.create_node(1, 'BUCK_5V', 'switching', QPointF(400, 100))
        
        root_node = self.model.find_node_by_id(root.node_id)
        buck_node = self.model.find_node_by_id(buck.node_id)
        self.model.connect_node(root_node, buck_node)
        self.scene._create_edge(root.node_id, buck.node_id)
        
        self.log("创建连线", len(self.scene._edge_items) == 1)
        
        edge = self.scene._edge_items[0]
        self.log("连线起点正确", edge.parent_id == root.node_id)
        self.log("连线终点正确", edge.child_id == buck.node_id)
        self.log("存在途经点", len(edge.waypoints) >= 2)
        
    def test_orthogonal_path(self):
        print("\n[测试2] 正交路径验证")
        if not self.scene._edge_items:
            self.log("跳过（无连线）", False)
            return
            
        edge = self.scene._edge_items[0]
        is_ortho = True
        for i in range(len(edge.waypoints) - 1):
            p1, p2 = edge.waypoints[i], edge.waypoints[i+1]
            if p1.x() != p2.x() and p1.y() != p2.y():
                is_ortho = False
                break
        self.log("所有线段正交", is_ortho)
        
    def test_port_alignment(self):
        print("\n[测试3] 端口对齐验证")
        if not self.scene._edge_items:
            self.log("跳过（无连线）", False)
            return
            
        edge = self.scene._edge_items[0]
        parent = self.scene._node_items.get(edge.parent_id)
        child = self.scene._node_items.get(edge.child_id)
        
        if parent and child:
            expected_start = parent.output_port_pos(edge.parent_port)
            expected_end = child.input_port_pos(edge.child_port)
            actual_start = edge.waypoints[0]
            actual_end = edge.waypoints[-1]
            
            start_aligned = (abs(actual_start.x() - expected_start.x()) < 0.1 and 
                           abs(actual_start.y() - expected_start.y()) < 0.1)
            end_aligned = (abs(actual_end.x() - expected_end.x()) < 0.1 and 
                         abs(actual_end.y() - expected_end.y()) < 0.1)
            
            self.log("起点与端口对齐", start_aligned, 
                    f"期望({expected_start.x():.1f}, {expected_start.y():.1f}), "
                    f"实际({actual_start.x():.1f}, {actual_start.y():.1f})")
            self.log("终点与端口对齐", end_aligned,
                    f"期望({expected_end.x():.1f}, {expected_end.y():.1f}), "
                    f"实际({actual_end.x():.1f}, {actual_end.y():.1f})")
    
    def test_node_move_update(self):
        print("\n[测试4] 节点移动后连线更新")
        if not self.scene._edge_items:
            self.log("跳过（无连线）", False)
            return
            
        edge = self.scene._edge_items[0]
        parent = self.scene._node_items.get(edge.parent_id)
        
        if parent:
            old_pos = parent.pos()
            parent.setPos(QPointF(150, 150))
            
            self.scene.update_all_edges()
            
            expected_start = parent.output_port_pos(edge.parent_port)
            actual_start = edge.waypoints[0]
            aligned = (abs(actual_start.x() - expected_start.x()) < 0.1 and 
                      abs(actual_start.y() - expected_start.y()) < 0.1)
            
            self.log("移动后起点对齐", aligned,
                    f"期望({expected_start.x():.1f}, {expected_start.y():.1f}), "
                    f"实际({actual_start.x():.1f}, {actual_start.y():.1f})")
            
            parent.setPos(old_pos)
            self.scene.update_all_edges()
    
    def test_multiple_connections(self):
        print("\n[测试5] 多分支连线")
        root = self.scene.find_node_item_by_id(list(self.scene._node_items.keys())[0])
        if not root:
            root = self.scene.create_node(0, 'VIN2', 'root', QPointF(100, 300))
        
        buck2 = self.scene.create_node(1, 'BUCK_3V3', 'switching', QPointF(400, 300))
        
        root_node = self.model.find_node_by_id(root.node_id)
        buck2_node = self.model.find_node_by_id(buck2.node_id)
        self.model.connect_node(root_node, buck2_node)
        self.scene._create_edge(root.node_id, buck2.node_id)
        
        self.log("创建第二条连线", len(self.scene._edge_items) >= 2)
        
        for i, edge in enumerate(self.scene._edge_items):
            is_ortho = True
            for j in range(len(edge.waypoints) - 1):
                p1, p2 = edge.waypoints[j], edge.waypoints[j+1]
                if p1.x() != p2.x() and p1.y() != p2.y():
                    is_ortho = False
                    break
            self.log(f"连线{i}正交性", is_ortho)
    
    def test_manual_waypoints(self):
        print("\n[测试6] 手动途经点")
        ldo = self.scene.create_node(2, 'LDO_1V8', 'ldo', QPointF(600, 100))
        load = self.scene.create_node(3, 'LOAD1', 'load', QPointF(900, 100))
        
        ldo_node = self.model.find_node_by_id(ldo.node_id)
        load_node = self.model.find_node_by_id(load.node_id)
        self.model.connect_node(ldo_node, load_node)
        
        manual_waypoints = [
            ldo.output_port_pos(),
            QPointF(820, 150),
            QPointF(900, 150),
            load.input_port_pos()
        ]
        self.scene._create_routed_edge(ldo.node_id, load.node_id, manual_waypoints, 0, 0, is_manual=True)
        
        edge = None
        for e in self.scene._edge_items:
            if e.parent_id == ldo.node_id and e.child_id == load.node_id:
                edge = e
                break
        
        if edge:
            self.log("手动路径创建成功", True)
            self.log("标记为手动路径", edge.is_manual_route)
            self.log("途经点数量正确", len(edge.waypoints) == 4)
            
            ldo.setPos(QPointF(620, 120))
            self.scene.update_all_edges()
            
            is_ortho = True
            for j in range(len(edge.waypoints) - 1):
                p1, p2 = edge.waypoints[j], edge.waypoints[j+1]
                if p1.x() != p2.x() and p1.y() != p2.y():
                    is_ortho = False
                    break
            self.log("移动后保持正交", is_ortho,
                    f"路径: {[(p.x(), p.y()) for p in edge.waypoints]}")
    
    def test_input_port_occupancy(self):
        print("\n[测试7] 输入端口占用检查")
        if len(self.scene._node_items) < 2:
            self.log("跳过（节点不足）", False)
            return
        
        nodes = list(self.scene._node_items.values())
        target = None
        for n in nodes:
            if n.input_ports > 0:
                already_connected = self.scene.is_input_port_occupied(n.node_id, 0)
                if already_connected:
                    continue
                target = n
                break
        
        if not target:
            self.log("跳过（无可用节点）", False)
            return
        
        first_edge_count = len(self.scene._edge_items)
        
        source = None
        for n in nodes:
            if n.output_ports > 0 and n.node_id != target.node_id:
                source = n
                break
        
        if source:
            source_node = self.model.find_node_by_id(source.node_id)
            target_node = self.model.find_node_by_id(target.node_id)
            self.model.connect_node(source_node, target_node)
            self.scene._create_edge(source.node_id, target.node_id)
            
            self.log("连线创建成功", len(self.scene._edge_items) > first_edge_count)
            self.log("输入端口标记为占用", self.scene.is_input_port_occupied(target.node_id, 0))
    
    def test_grid_alignment(self):
        print("\n[测试8] 格点对齐检查")
        GRID = 20
        all_aligned = True
        
        for node_id, node in self.scene._node_items.items():
            pos = node.pos()
            if pos.x() % GRID != 0 or pos.y() % GRID != 0:
                all_aligned = False
                break
        
        self.log("所有节点位置格点对齐", all_aligned)
        
        for i, edge in enumerate(self.scene._edge_items):
            edge_aligned = True
            for wp in edge.waypoints:
                if wp.x() % GRID != 0 or wp.y() % GRID != 0:
                    edge_aligned = False
                    break
            self.log(f"连线{i}途经点格点对齐", edge_aligned)
    
    def run_all_tests(self):
        print("=" * 60)
        print("        PowerTree 连线功能测试")
        print("=" * 60)
        
        self.setup()
        
        self.test_basic_connection()
        self.test_orthogonal_path()
        self.test_port_alignment()
        self.test_node_move_update()
        self.test_multiple_connections()
        self.test_manual_waypoints()
        self.test_input_port_occupancy()
        self.test_grid_alignment()
        
        print("\n" + "=" * 60)
        print(f"  测试结果: {self.passed} 通过, {self.failed} 失败")
        print("=" * 60)
        
        return self.failed == 0


if __name__ == '__main__':
    runner = EdgeTestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)
