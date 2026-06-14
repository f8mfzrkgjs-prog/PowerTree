"""
连线功能动画演示测试工具
运行方式: python tests/edge_demo.py
"""
import sys
sys.path.insert(0, '.')
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QGraphicsView
)
from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import QFont

from core.tree_model import TreeModel
from core.library_manager import LibraryManager
from app.canvas_scene import CanvasScene
from app.node_item import NodeItem


class EdgeDemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PowerTree 连线功能演示")
        self.setGeometry(100, 100, 1200, 800)
        
        self.test_step = 0
        self.test_steps = []
        self.nodes = {}
        self.edges = []
        
        self.setup_ui()
        self.setup_scene()
        self.build_test_steps()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        
        self.view = QGraphicsView()
        from PySide6.QtGui import QPainter
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setMinimumSize(800, 600)
        layout.addWidget(self.view, 3)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        title = QLabel("测试步骤")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        right_layout.addWidget(title)
        
        self.step_label = QLabel("点击 [开始测试] 运行演示")
        self.step_label.setWordWrap(True)
        self.step_label.setMinimumHeight(60)
        self.step_label.setStyleSheet("padding: 10px; background: #f0f0f0; border-radius: 5px;")
        right_layout.addWidget(self.step_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        right_layout.addWidget(self.log_text)
        
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始测试")
        self.start_btn.clicked.connect(self.start_demo)
        btn_layout.addWidget(self.start_btn)
        
        self.next_btn = QPushButton("下一步")
        self.next_btn.clicked.connect(self.next_step)
        self.next_btn.setEnabled(False)
        btn_layout.addWidget(self.next_btn)
        
        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self.reset_demo)
        btn_layout.addWidget(self.reset_btn)
        
        right_layout.addLayout(btn_layout)
        layout.addWidget(right_panel, 1)
        
    def setup_scene(self):
        self.library = LibraryManager()
        self.library.add_template('ROOT', 'root', 180, 100, '#288C28', 0, 1)
        self.library.add_template('BUCK', 'switching', 220, 120, '#2864B4', 1, 1)
        self.library.add_template('LDO', 'ldo', 180, 100, '#A07828', 1, 1)
        self.library.add_template('LOAD', 'load', 160, 80, '#646464', 1, 0)
        
        self.model = TreeModel()
        self.model.set_library(self.library)
        self.scene = CanvasScene(self.model)
        self.view.setScene(self.scene)
        
    def build_test_steps(self):
        self.test_steps = [
            ("初始化", self.step_init),
            ("创建输入源", self.step_create_root),
            ("创建BUCK变换器", self.step_create_buck),
            ("连接输入源到BUCK", self.step_connect_1),
            ("验证连线正交性", self.step_verify_ortho),
            ("创建第二个BUCK", self.step_create_buck2),
            ("分支连接", self.step_branch_connect),
            ("移动节点测试", self.step_move_node),
            ("验证端口对齐", self.step_verify_alignment),
            ("创建LDO和负载", self.step_create_ldo_load),
            ("手动途经点连线", self.step_manual_waypoints),
            ("移动节点验证手动路径", self.step_move_manual),
            ("完成", self.step_finish),
        ]
        
    def log(self, msg: str, success: bool = True):
        prefix = "[OK] " if success else "[FAIL] "
        self.log_text.append(prefix + msg)
        
    def start_demo(self):
        self.test_step = 0
        self.log_text.clear()
        self.start_btn.setEnabled(False)
        self.next_btn.setEnabled(True)
        self.next_step()
        
    def next_step(self):
        if self.test_step >= len(self.test_steps):
            return
        name, func = self.test_steps[self.test_step]
        self.step_label.setText(f"步骤 {self.test_step + 1}/{len(self.test_steps)}: {name}")
        func()
        self.test_step += 1
        
        if self.test_step >= len(self.test_steps):
            self.next_btn.setEnabled(False)
            self.start_btn.setEnabled(True)
            
    def reset_demo(self):
        self.scene.clear_scene()
        self.nodes.clear()
        self.edges.clear()
        self.test_step = 0
        self.log_text.clear()
        self.step_label.setText("点击 [开始测试] 运行演示")
        self.start_btn.setEnabled(True)
        self.next_btn.setEnabled(False)
        
    def animate_move(self, node: NodeItem, target_pos: QPointF, callback=None):
        start_pos = node.pos()
        steps = 20
        current_step = [0]
        
        def do_move():
            if current_step[0] >= steps:
                if callback:
                    callback()
                return
            t = current_step[0] / steps
            new_x = start_pos.x() + (target_pos.x() - start_pos.x()) * t
            new_y = start_pos.y() + (target_pos.y() - start_pos.y()) * t
            node.setPos(QPointF(new_x, new_y))
            self.scene.update_all_edges()
            current_step[0] += 1
            QTimer.singleShot(30, do_move)
            
        do_move()
        
    def step_init(self):
        self.log("场景初始化完成")
        
    def step_create_root(self):
        root = self.scene.create_node(0, 'VIN_12V', 'root', QPointF(50, 200))
        self.nodes['root'] = root
        self.log(f"创建输入源节点: {root.node_name}")
        QTimer.singleShot(100, lambda: self.view.centerOn(root))
        
    def step_create_buck(self):
        buck = self.scene.create_node(1, 'BUCK_5V', 'switching', QPointF(350, 100))
        self.nodes['buck1'] = buck
        self.log(f"创建BUCK变换器: {buck.node_name}")
        
    def step_connect_1(self):
        root = self.nodes.get('root')
        buck = self.nodes.get('buck1')
        if root and buck:
            root_node = self.model.find_node_by_id(root.node_id)
            buck_node = self.model.find_node_by_id(buck.node_id)
            self.model.connect_node(root_node, buck_node)
            self.scene._create_edge(root.node_id, buck.node_id)
            self.log("创建连线: VIN_12V -> BUCK_5V")
            
    def step_verify_ortho(self):
        if self.scene._edge_items:
            edge = self.scene._edge_items[0]
            all_ortho = True
            for i in range(len(edge.waypoints) - 1):
                p1, p2 = edge.waypoints[i], edge.waypoints[i+1]
                if p1.x() != p2.x() and p1.y() != p2.y():
                    all_ortho = False
                    break
            self.log("连线正交性检查: " + ("通过" if all_ortho else "失败"), all_ortho)
            
    def step_create_buck2(self):
        buck2 = self.scene.create_node(1, 'BUCK_3V3', 'switching', QPointF(350, 300))
        self.nodes['buck2'] = buck2
        self.log(f"创建第二个BUCK变换器: {buck2.node_name}")
        
    def step_branch_connect(self):
        root = self.nodes.get('root')
        buck2 = self.nodes.get('buck2')
        if root and buck2:
            root_node = self.model.find_node_by_id(root.node_id)
            buck2_node = self.model.find_node_by_id(buck2.node_id)
            self.model.connect_node(root_node, buck2_node)
            self.scene._create_edge(root.node_id, buck2.node_id)
            self.log("创建分支连线: VIN_12V -> BUCK_3V3")
            self.log(f"当前连线数: {len(self.scene._edge_items)}")
            
    def step_move_node(self):
        root = self.nodes.get('root')
        if root:
            self.log("移动输入源节点...")
            self.animate_move(root, QPointF(100, 200))
            
    def step_verify_alignment(self):
        for i, edge in enumerate(self.scene._edge_items):
            parent = self.scene._node_items.get(edge.parent_id)
            child = self.scene._node_items.get(edge.child_id)
            if parent and child:
                expected_start = parent.output_port_pos(edge.parent_port)
                actual_start = edge.waypoints[0]
                aligned = (abs(actual_start.x() - expected_start.x()) < 1 and 
                          abs(actual_start.y() - expected_start.y()) < 1)
                self.log(f"连线{i}起点对齐: {'通过' if aligned else '失败'}", aligned)
                
    def step_create_ldo_load(self):
        ldo = self.scene.create_node(2, 'LDO_1V8', 'ldo', QPointF(650, 100))
        load = self.scene.create_node(3, 'LOAD_MCU', 'load', QPointF(900, 100))
        self.nodes['ldo'] = ldo
        self.nodes['load'] = load
        
        buck1 = self.nodes.get('buck1')
        if buck1 and ldo:
            buck1_node = self.model.find_node_by_id(buck1.node_id)
            ldo_node = self.model.find_node_by_id(ldo.node_id)
            self.model.connect_node(buck1_node, ldo_node)
            self.scene._create_edge(buck1.node_id, ldo.node_id)
            
        if ldo and load:
            ldo_node = self.model.find_node_by_id(ldo.node_id)
            load_node = self.model.find_node_by_id(load.node_id)
            self.model.connect_node(ldo_node, load_node)
            self.scene._create_edge(ldo.node_id, load.node_id)
            
        self.log("创建LDO和负载节点")
        self.log(f"当前节点数: {len(self.scene._node_items)}")
        self.log(f"当前连线数: {len(self.scene._edge_items)}")
        
    def step_manual_waypoints(self):
        buck2 = self.nodes.get('buck2')
        if buck2:
            load2 = self.scene.create_node(3, 'LOAD_LED', 'load', QPointF(900, 300))
            self.nodes['load2'] = load2
            
            buck2_node = self.model.find_node_by_id(buck2.node_id)
            load2_node = self.model.find_node_by_id(load2.node_id)
            self.model.connect_node(buck2_node, load2_node)
            
            manual_waypoints = [
                buck2.output_port_pos(),
                QPointF(700, 350),
                QPointF(850, 350),
                load2.input_port_pos()
            ]
            self.scene._create_routed_edge(buck2.node_id, load2.node_id, 
                                           manual_waypoints, 0, 0, is_manual=True)
            self.log("创建带手动途经点的连线")
            
    def step_move_manual(self):
        ldo = self.nodes.get('ldo')
        if ldo:
            self.log("移动LDO节点（验证手动路径正交性）...")
            self.animate_move(ldo, QPointF(650, 150))
            
    def step_finish(self):
        self.log("=" * 40)
        self.log("演示完成!")
        self.log(f"节点总数: {len(self.scene._node_items)}")
        self.log(f"连线总数: {len(self.scene._edge_items)}")
        
        all_ortho = True
        all_aligned = True
        
        for i, edge in enumerate(self.scene._edge_items):
            for j in range(len(edge.waypoints) - 1):
                p1, p2 = edge.waypoints[j], edge.waypoints[j+1]
                if p1.x() != p2.x() and p1.y() != p2.y():
                    all_ortho = False
                    self.log(f"连线{i}存在非正交线段", False)
                    break
                    
            parent = self.scene._node_items.get(edge.parent_id)
            child = self.scene._node_items.get(edge.child_id)
            if parent and child:
                expected_start = parent.output_port_pos(edge.parent_port)
                actual_start = edge.waypoints[0]
                if abs(actual_start.x() - expected_start.x()) > 1 or \
                   abs(actual_start.y() - expected_start.y()) > 1:
                    all_aligned = False
                    self.log(f"连线{i}起点未对齐", False)
                    
        if all_ortho:
            self.log("所有连线正交性: 通过")
        if all_aligned:
            self.log("所有端口对齐: 通过")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = EdgeDemoWindow()
    window.show()
    sys.exit(app.exec())
