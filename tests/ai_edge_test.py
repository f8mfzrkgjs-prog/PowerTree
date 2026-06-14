"""
PowerTree 连线功能智能自动化测试工具
运行方式: python tests/ai_edge_test.py
"""
import sys
sys.path.insert(0, '.')
import random
import time
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QProgressBar, QGroupBox, QCheckBox,
    QSpinBox, QComboBox
)
from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import QPainter, QFont, QColor

from core.tree_model import TreeModel
from core.library_manager import LibraryManager
from app.canvas_scene import CanvasScene
from app.node_item import NodeItem
from app.edge_item import EdgeItem


class TestSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class TestResult:
    test_name: str
    passed: bool
    message: str
    severity: TestSeverity = TestSeverity.INFO
    details: dict = field(default_factory=dict)


class EdgeAnalyzer:
    """连线分析器 - 检测连线异常"""
    
    GRID_SIZE = 20
    
    @staticmethod
    def check_orthogonality(edge: EdgeItem) -> Tuple[bool, List[str]]:
        """检查连线正交性"""
        issues = []
        for i in range(len(edge.waypoints) - 1):
            p1, p2 = edge.waypoints[i], edge.waypoints[i+1]
            if p1.x() != p2.x() and p1.y() != p2.y():
                issues.append(f"线段{i}: ({p1.x():.1f},{p1.y():.1f})->({p2.x():.1f},{p2.y():.1f}) 非正交")
        return len(issues) == 0, issues
    
    @staticmethod
    def check_port_alignment(edge: EdgeItem, parent: NodeItem, child: NodeItem) -> Tuple[bool, List[str]]:
        """检查端口对齐"""
        issues = []
        expected_start = parent.output_port_pos(edge.parent_port)
        expected_end = child.input_port_pos(edge.child_port)
        actual_start = edge.waypoints[0]
        actual_end = edge.waypoints[-1]
        
        if abs(actual_start.x() - expected_start.x()) > 0.5 or \
           abs(actual_start.y() - expected_start.y()) > 0.5:
            issues.append(f"起点偏移: 期望({expected_start.x():.1f},{expected_start.y():.1f}), "
                         f"实际({actual_start.x():.1f},{actual_start.y():.1f})")
        
        if abs(actual_end.x() - expected_end.x()) > 0.5 or \
           abs(actual_end.y() - expected_end.y()) > 0.5:
            issues.append(f"终点偏移: 期望({expected_end.x():.1f},{expected_end.y():.1f}), "
                         f"实际({actual_end.x():.1f},{actual_end.y():.1f})")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def check_grid_alignment(edge: EdgeItem) -> Tuple[bool, List[str]]:
        """检查格点对齐"""
        issues = []
        for i, wp in enumerate(edge.waypoints):
            if wp.x() % EdgeAnalyzer.GRID_SIZE != 0 or wp.y() % EdgeAnalyzer.GRID_SIZE != 0:
                issues.append(f"途经点{i}: ({wp.x():.1f},{wp.y():.1f}) 未对齐格点")
        return len(issues) == 0, issues
    
    @staticmethod
    def check_edge_overlap(edges: List[EdgeItem]) -> Tuple[bool, List[str]]:
        """检查连线重叠"""
        issues = []
        for i, e1 in enumerate(edges):
            for j, e2 in enumerate(edges[i+1:], i+1):
                if (e1.parent_id == e2.parent_id and e1.child_id == e2.child_id):
                    issues.append(f"连线{i}和{j}重复连接相同节点")
        return len(issues) == 0, issues
    
    @staticmethod
    def check_self_connection(edge: EdgeItem) -> bool:
        """检查自连接"""
        return edge.parent_id == edge.child_id


class TestScenario:
    """测试场景生成器"""
    
    @staticmethod
    def generate_linear_chain(scene: CanvasScene, model: TreeModel, count: int = 4) -> List[NodeItem]:
        """生成线性链式拓扑"""
        nodes = []
        x = 50
        for i in range(count):
            if i == 0:
                node = scene.create_node(0, f'VIN_{i+1}', 'root', QPointF(x, 200))
            elif i == count - 1:
                node = scene.create_node(3, f'LOAD_{i+1}', 'load', QPointF(x, 200))
            else:
                node = scene.create_node(1, f'BUCK_{i+1}', 'switching', QPointF(x, 200))
            nodes.append(node)
            x += 280
        return nodes
    
    @staticmethod
    def generate_star_topology(scene: CanvasScene, model: TreeModel, branches: int = 3) -> List[NodeItem]:
        """生成星型拓扑（一个源连接多个负载）"""
        nodes = []
        root = scene.create_node(0, 'VIN_MAIN', 'root', QPointF(50, 200))
        nodes.append(root)
        
        y_start = 100
        y_step = 150
        for i in range(branches):
            buck = scene.create_node(1, f'BUCK_{i+1}', 'switching', QPointF(350, y_start + i * y_step))
            nodes.append(buck)
        return nodes
    
    @staticmethod
    def generate_tree_topology(scene: CanvasScene, model: TreeModel, depth: int = 2) -> List[NodeItem]:
        """生成树形拓扑"""
        nodes = []
        root = scene.create_node(0, 'VIN_ROOT', 'root', QPointF(50, 250))
        nodes.append(root)
        
        positions = [(250, 100), (250, 400)]
        current_parents = [root]
        
        for d in range(depth):
            new_nodes = []
            for idx, parent in enumerate(current_parents):
                for j in range(2):
                    y_offset = (j - 0.5) * 150
                    x = parent.pos().x() + 250
                    y = parent.pos().y() + y_offset
                    if d == depth - 1:
                        node = scene.create_node(3, f'LOAD_d{d}_{j}', 'load', QPointF(x, y))
                    else:
                        node = scene.create_node(1, f'BUCK_d{d}_{j}', 'switching', QPointF(x, y))
                    nodes.append(node)
                    new_nodes.append(node)
            current_parents = new_nodes
        
        return nodes


class AIEdgeTester:
    """AI智能测试器"""
    
    def __init__(self, scene: CanvasScene, model: TreeModel):
        self.scene = scene
        self.model = model
        self.results: List[TestResult] = []
        self.analyzer = EdgeAnalyzer()
        
    def log(self, result: TestResult):
        self.results.append(result)
        return result.passed
        
    def test_basic_connection(self, parent: NodeItem, child: NodeItem) -> TestResult:
        """测试基本连线创建"""
        parent_node = self.model.find_node_by_id(parent.node_id)
        child_node = self.model.find_node_by_id(child.node_id)
        
        if not parent_node or not child_node:
            return TestResult("基本连线", False, "节点不存在", TestSeverity.ERROR)
        
        self.model.connect_node(parent_node, child_node)
        self.scene._create_edge(parent.node_id, child.node_id)
        
        edge = None
        for e in self.scene._edge_items:
            if e.parent_id == parent.node_id and e.child_id == child.node_id:
                edge = e
                break
        
        if not edge:
            return TestResult("基本连线", False, "连线创建失败", TestSeverity.ERROR)
        
        return TestResult("基本连线", True, f"连线创建成功: {parent.node_name} -> {child.node_name}")
    
    def test_edge_orthogonality(self, edge: EdgeItem) -> TestResult:
        """测试连线正交性"""
        passed, issues = self.analyzer.check_orthogonality(edge)
        if passed:
            return TestResult("正交性检查", True, f"所有线段正交")
        else:
            return TestResult("正交性检查", False, "; ".join(issues), TestSeverity.ERROR)
    
    def test_port_alignment(self, edge: EdgeItem) -> TestResult:
        """测试端口对齐"""
        parent = self.scene._node_items.get(edge.parent_id)
        child = self.scene._node_items.get(edge.child_id)
        
        if not parent or not child:
            return TestResult("端口对齐", False, "节点不存在", TestSeverity.ERROR)
        
        passed, issues = self.analyzer.check_port_alignment(edge, parent, child)
        if passed:
            return TestResult("端口对齐", True, "端口完美对齐")
        else:
            return TestResult("端口对齐", False, "; ".join(issues), TestSeverity.ERROR)
    
    def test_node_movement(self, nodes: List[NodeItem], move_distance: QPointF = QPointF(50, 50)) -> List[TestResult]:
        """测试节点移动后的连线更新"""
        results = []
        
        for node in nodes:
            old_pos = node.pos()
            new_pos = old_pos + move_distance
            node.setPos(new_pos)
            
            self.scene.update_all_edges()
            
            related_edges = [e for e in self.scene._edge_items 
                          if e.parent_id == node.node_id or e.child_id == node.node_id]
            
            for edge in related_edges:
                parent = self.scene._node_items.get(edge.parent_id)
                child = self.scene._node_items.get(edge.child_id)
                
                if parent and child:
                    passed, issues = self.analyzer.check_port_alignment(edge, parent, child)
                    if not passed:
                        results.append(TestResult(
                            f"移动{node.node_name}后连线检查",
                            False,
                            f"{edge.parent_id[:8]}->{edge.child_id[:8]}: {', '.join(issues)}",
                            TestSeverity.ERROR,
                            {"node": node.node_name, "edge": f"{edge.parent_id}->{edge.child_id}"}
                        ))
            
            ortho_passed = True
            for edge in related_edges:
                passed, _ = self.analyzer.check_orthogonality(edge)
                if not passed:
                    ortho_passed = False
                    break
            
            if ortho_passed:
                results.append(TestResult(
                    f"移动{node.node_name}正交性",
                    True,
                    "所有相关连线保持正交"
                ))
        
        return results
    
    def test_multi_selection_move(self, nodes: List[NodeItem], move_distance: QPointF = QPointF(100, 0)) -> List[TestResult]:
        """测试多选节点整体移动"""
        results = []
        
        for node in nodes:
            node.setSelected(True)
        
        old_positions = {n.node_id: n.pos() for n in nodes}
        
        for node in nodes:
            node.setPos(node.pos() + move_distance)
        
        self.scene.update_all_edges()
        
        all_edges = self.scene._edge_items
        all_ortho = True
        all_aligned = True
        
        for edge in all_edges:
            passed, _ = self.analyzer.check_orthogonality(edge)
            if not passed:
                all_ortho = False
            
            parent = self.scene._node_items.get(edge.parent_id)
            child = self.scene._node_items.get(edge.child_id)
            if parent and child:
                passed, _ = self.analyzer.check_port_alignment(edge, parent, child)
                if not passed:
                    all_aligned = False
        
        results.append(TestResult(
            "多选移动-正交性",
            all_ortho,
            "所有连线保持正交" if all_ortho else "存在非正交连线",
            TestSeverity.INFO if all_ortho else TestSeverity.ERROR
        ))
        
        results.append(TestResult(
            "多选移动-端口对齐",
            all_aligned,
            "所有端口对齐" if all_aligned else "存在未对齐端口",
            TestSeverity.INFO if all_aligned else TestSeverity.ERROR
        ))
        
        for node in nodes:
            node.setSelected(False)
        
        return results
    
    def test_branch_connection(self, source: NodeItem, target: NodeItem) -> TestResult:
        """测试分支连线"""
        existing_edges = [e for e in self.scene._edge_items if e.parent_id == source.node_id]
        
        source_node = self.model.find_node_by_id(source.node_id)
        target_node = self.model.find_node_by_id(target.node_id)
        
        if not source_node or not target_node:
            return TestResult("分支连线", False, "节点不存在", TestSeverity.ERROR)
        
        self.model.connect_node(source_node, target_node)
        self.scene._create_edge(source.node_id, target.node_id)
        
        new_edges = [e for e in self.scene._edge_items if e.parent_id == source.node_id]
        
        if len(new_edges) > len(existing_edges):
            return TestResult(
                "分支连线",
                True,
                f"从{source.node_name}创建分支连线到{target.node_name}"
            )
        else:
            return TestResult("分支连线", False, "分支连线创建失败", TestSeverity.WARNING)
    
    def test_manual_waypoints(self, parent: NodeItem, child: NodeItem, 
                               waypoints: List[QPointF]) -> TestResult:
        """测试手动途经点连线"""
        parent_node = self.model.find_node_by_id(parent.node_id)
        child_node = self.model.find_node_by_id(child.node_id)
        
        if not parent_node or not child_node:
            return TestResult("手动途经点", False, "节点不存在", TestSeverity.ERROR)
        
        self.model.connect_node(parent_node, child_node)
        self.scene._create_routed_edge(parent.node_id, child.node_id, 
                                       waypoints, 0, 0, is_manual=True)
        
        edge = None
        for e in self.scene._edge_items:
            if e.parent_id == parent.node_id and e.child_id == child.node_id:
                edge = e
                break
        
        if not edge:
            return TestResult("手动途经点", False, "连线创建失败", TestSeverity.ERROR)
        
        if not edge.is_manual_route:
            return TestResult("手动途经点", False, "未标记为手动路径", TestSeverity.WARNING)
        
        passed, issues = self.analyzer.check_orthogonality(edge)
        if passed:
            return TestResult("手动途经点", True, f"创建成功，途经点{len(waypoints)}个")
        else:
            return TestResult("手动途经点", False, "; ".join(issues), TestSeverity.ERROR)
    
    def test_input_port_uniqueness(self, target: NodeItem, source1: NodeItem, 
                                    source2: NodeItem) -> TestResult:
        """测试输入端口唯一性"""
        target_node = self.model.find_node_by_id(target.node_id)
        source1_node = self.model.find_node_by_id(source1.node_id)
        source2_node = self.model.find_node_by_id(source2.node_id)
        
        if not all([target_node, source1_node, source2_node]):
            return TestResult("输入端口唯一性", False, "节点不存在", TestSeverity.ERROR)
        
        self.model.connect_node(source1_node, target_node)
        self.scene._create_edge(source1.node_id, target.node_id)
        
        occupied = self.scene.is_input_port_occupied(target.node_id, 0)
        
        if not occupied:
            return TestResult("输入端口唯一性", False, "端口占用检测失败", TestSeverity.ERROR)
        
        return TestResult("输入端口唯一性", True, "端口占用检测正常")
    
    def run_comprehensive_test(self) -> List[TestResult]:
        """运行综合测试"""
        results = []
        
        results.append(TestResult("综合测试开始", True, "=" * 40, TestSeverity.INFO))
        
        passed, issues = self.analyzer.check_edge_overlap(self.scene._edge_items)
        if not passed:
            for issue in issues:
                results.append(TestResult("连线重叠检查", False, issue, TestSeverity.WARNING))
        else:
            results.append(TestResult("连线重叠检查", True, "无重叠连线"))
        
        for i, edge in enumerate(self.scene._edge_items):
            if self.analyzer.check_self_connection(edge):
                results.append(TestResult(
                    f"自连接检查-{i}",
                    False,
                    f"连线{i}存在自连接",
                    TestSeverity.CRITICAL
                ))
        
        all_ortho = True
        all_aligned = True
        
        for i, edge in enumerate(self.scene._edge_items):
            passed, _ = self.analyzer.check_orthogonality(edge)
            if not passed:
                all_ortho = False
                results.append(TestResult(
                    f"正交性-{i}",
                    False,
                    f"连线{i}存在非正交线段",
                    TestSeverity.ERROR
                ))
            
            parent = self.scene._node_items.get(edge.parent_id)
            child = self.scene._node_items.get(edge.child_id)
            if parent and child:
                passed, _ = self.analyzer.check_port_alignment(edge, parent, child)
                if not passed:
                    all_aligned = False
                    results.append(TestResult(
                        f"端口对齐-{i}",
                        False,
                        f"连线{i}端口未对齐",
                        TestSeverity.ERROR
                    ))
        
        if all_ortho:
            results.append(TestResult("整体正交性", True, "所有连线正交"))
        if all_aligned:
            results.append(TestResult("整体端口对齐", True, "所有端口对齐"))
        
        return results


class AITestWindow(QMainWindow):
    """AI测试主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PowerTree AI 连线测试工具")
        self.setGeometry(100, 100, 1400, 900)
        
        self.test_results: List[TestResult] = []
        self.test_nodes: List[NodeItem] = []
        self.current_test = 0
        self.auto_mode = False
        
        self.setup_ui()
        self.setup_scene()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        view_group = QGroupBox("画布视图")
        view_layout = QVBoxLayout(view_group)
        from PySide6.QtWidgets import QGraphicsView
        self.view = QGraphicsView()
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setMinimumSize(600, 500)
        view_layout.addWidget(self.view)
        left_layout.addWidget(view_group)
        
        ctrl_group = QGroupBox("测试控制")
        ctrl_layout = QVBoxLayout(ctrl_group)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("拓扑类型:"))
        self.topology_combo = QComboBox()
        self.topology_combo.addItems(["线性链式", "星型拓扑", "树形拓扑", "随机生成"])
        row1.addWidget(self.topology_combo)
        ctrl_layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("节点数量:"))
        self.node_count_spin = QSpinBox()
        self.node_count_spin.setRange(3, 10)
        self.node_count_spin.setValue(4)
        row2.addWidget(self.node_count_spin)
        ctrl_layout.addLayout(row2)
        
        row3 = QHBoxLayout()
        self.auto_check = QCheckBox("自动运行模式")
        row3.addWidget(self.auto_check)
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(100, 2000)
        self.delay_spin.setValue(500)
        self.delay_spin.setSuffix("ms")
        row3.addWidget(QLabel("延迟:"))
        row3.addWidget(self.delay_spin)
        ctrl_layout.addLayout(row3)
        
        btn_row = QHBoxLayout()
        self.generate_btn = QPushButton("生成拓扑")
        self.generate_btn.clicked.connect(self.generate_topology)
        btn_row.addWidget(self.generate_btn)
        
        self.test_btn = QPushButton("开始测试")
        self.test_btn.clicked.connect(self.start_test)
        btn_row.addWidget(self.test_btn)
        
        self.move_test_btn = QPushButton("移动测试")
        self.move_test_btn.clicked.connect(self.run_move_test)
        btn_row.addWidget(self.move_test_btn)
        
        ctrl_layout.addLayout(btn_row)
        
        btn_row2 = QHBoxLayout()
        self.multi_move_btn = QPushButton("多选移动测试")
        self.multi_move_btn.clicked.connect(self.run_multi_move_test)
        btn_row2.addWidget(self.multi_move_btn)
        
        self.report_btn = QPushButton("生成报告")
        self.report_btn.clicked.connect(self.generate_report)
        btn_row2.addWidget(self.report_btn)
        
        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self.reset_all)
        btn_row2.addWidget(self.reset_btn)
        
        ctrl_layout.addLayout(btn_row2)
        left_layout.addWidget(ctrl_group)
        
        layout.addWidget(left_panel, 2)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        status_group = QGroupBox("测试状态")
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel("就绪 - 点击 [生成拓扑] 开始")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("padding: 10px; background: #e8f5e9; border-radius: 5px;")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.progress_bar)
        right_layout.addWidget(status_group)
        
        log_group = QGroupBox("测试日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        right_layout.addWidget(log_group, 1)
        
        stats_group = QGroupBox("统计信息")
        stats_layout = QVBoxLayout(stats_group)
        self.stats_label = QLabel("节点: 0 | 连线: 0 | 通过: 0 | 失败: 0")
        stats_layout.addWidget(self.stats_label)
        right_layout.addWidget(stats_group)
        
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
        
        self.tester = AIEdgeTester(self.scene, self.model)
        
    def log(self, msg: str, severity: TestSeverity = TestSeverity.INFO):
        colors = {
            TestSeverity.INFO: "#2196F3",
            TestSeverity.WARNING: "#FF9800",
            TestSeverity.ERROR: "#f44336",
            TestSeverity.CRITICAL: "#9C27B0"
        }
        color = colors.get(severity, "#000000")
        self.log_text.append(f'<span style="color:{color}">[{severity.value}]</span> {msg}')
        
    def update_stats(self):
        nodes = len(self.scene._node_items)
        edges = len(self.scene._edge_items)
        passed = sum(1 for r in self.test_results if r.passed)
        failed = len(self.test_results) - passed
        self.stats_label.setText(f"节点: {nodes} | 连线: {edges} | 通过: {passed} | 失败: {failed}")
        
    def generate_topology(self):
        self.scene.clear_scene()
        self.test_nodes.clear()
        self.test_results.clear()
        self.log_text.clear()
        
        topology = self.topology_combo.currentText()
        count = self.node_count_spin.value()
        
        self.log(f"生成拓扑: {topology}, 节点数: {count}")
        
        if topology == "线性链式":
            self.test_nodes = TestScenario.generate_linear_chain(self.scene, self.model, count)
        elif topology == "星型拓扑":
            self.test_nodes = TestScenario.generate_star_topology(self.scene, self.model, count - 1)
        elif topology == "树形拓扑":
            self.test_nodes = TestScenario.generate_tree_topology(self.scene, self.model, 2)
        else:
            for i in range(count):
                x = random.randint(50, 600)
                y = random.randint(50, 500)
                x = (x // 20) * 20
                y = (y // 20) * 20
                if i == 0:
                    node = self.scene.create_node(0, f'VIN_{i}', 'root', QPointF(x, y))
                elif i == count - 1:
                    node = self.scene.create_node(3, f'LOAD_{i}', 'load', QPointF(x, y))
                else:
                    tmpl = random.choice([1, 2])
                    node = self.scene.create_node(tmpl, f'DEV_{i}', 
                                                 'switching' if tmpl == 1 else 'ldo', 
                                                 QPointF(x, y))
                self.test_nodes.append(node)
        
        self.log(f"创建了 {len(self.test_nodes)} 个节点", TestSeverity.INFO)
        self.status_label.setText(f"拓扑已生成: {len(self.test_nodes)} 个节点")
        self.status_label.setStyleSheet("padding: 10px; background: #e3f2fd; border-radius: 5px;")
        self.update_stats()
        
    def start_test(self):
        if not self.test_nodes:
            self.log("请先生成拓扑", TestSeverity.WARNING)
            return
        
        self.log("=" * 50)
        self.log("开始连线测试")
        self.log("=" * 50)
        
        self.test_results.clear()
        
        for i in range(len(self.test_nodes) - 1):
            parent = self.test_nodes[i]
            child = self.test_nodes[i + 1]
            result = self.tester.test_basic_connection(parent, child)
            self.test_results.append(result)
            self.log(result.message, TestSeverity.INFO if result.passed else TestSeverity.ERROR)
        
        for edge in self.scene._edge_items:
            result = self.tester.test_edge_orthogonality(edge)
            self.test_results.append(result)
            self.log(f"正交性: {result.message}", TestSeverity.INFO if result.passed else TestSeverity.ERROR)
            
            result = self.tester.test_port_alignment(edge)
            self.test_results.append(result)
            self.log(f"端口对齐: {result.message}", TestSeverity.INFO if result.passed else TestSeverity.ERROR)
        
        results = self.tester.run_comprehensive_test()
        self.test_results.extend(results)
        for r in results:
            self.log(r.message, r.severity)
        
        self.update_stats()
        passed = sum(1 for r in self.test_results if r.passed)
        total = len(self.test_results)
        self.progress_bar.setValue(int(passed / total * 100) if total > 0 else 0)
        
        self.status_label.setText(f"测试完成: {passed}/{total} 通过")
        self.status_label.setStyleSheet("padding: 10px; background: #c8e6c9; border-radius: 5px;")
        
    def run_move_test(self):
        if not self.test_nodes:
            self.log("请先生成拓扑", TestSeverity.WARNING)
            return
        
        self.log("=" * 50)
        self.log("开始节点移动测试")
        self.log("=" * 50)
        
        move_vectors = [
            QPointF(50, 0),
            QPointF(0, 50),
            QPointF(-50, 0),
            QPointF(0, -50),
            QPointF(30, 30),
        ]
        
        for i, move in enumerate(move_vectors):
            self.log(f"移动测试 {i+1}: 偏移 ({move.x()}, {move.y()})")
            
            results = self.tester.test_node_movement(self.test_nodes, move)
            self.test_results.extend(results)
            
            for r in results:
                self.log(f"  {r.message}", r.severity)
        
        results = self.tester.run_comprehensive_test()
        self.test_results.extend(results)
        for r in results:
            self.log(r.message, r.severity)
        
        self.update_stats()
        passed = sum(1 for r in self.test_results if r.passed)
        total = len(self.test_results)
        self.progress_bar.setValue(int(passed / total * 100) if total > 0 else 0)
        
        self.status_label.setText(f"移动测试完成: {passed}/{total} 通过")
        
    def run_multi_move_test(self):
        if not self.test_nodes or len(self.test_nodes) < 2:
            self.log("节点数量不足", TestSeverity.WARNING)
            return
        
        self.log("=" * 50)
        self.log("开始多选移动测试")
        self.log("=" * 50)
        
        select_count = min(3, len(self.test_nodes))
        selected = self.test_nodes[:select_count]
        
        self.log(f"选中 {select_count} 个节点进行整体移动")
        
        results = self.tester.test_multi_selection_move(selected, QPointF(100, 50))
        self.test_results.extend(results)
        
        for r in results:
            self.log(f"  {r.message}", r.severity)
        
        results = self.tester.test_multi_selection_move(selected, QPointF(-100, -50))
        self.test_results.extend(results)
        
        for r in results:
            self.log(f"  {r.message}", r.severity)
        
        results = self.tester.run_comprehensive_test()
        self.test_results.extend(results)
        for r in results:
            self.log(r.message, r.severity)
        
        self.update_stats()
        passed = sum(1 for r in self.test_results if r.passed)
        total = len(self.test_results)
        self.progress_bar.setValue(int(passed / total * 100) if total > 0 else 0)
        
        self.status_label.setText(f"多选移动测试完成: {passed}/{total} 通过")
        
    def generate_report(self):
        if not self.test_results:
            self.log("没有测试结果", TestSeverity.WARNING)
            return
        
        self.log("=" * 50)
        self.log("测试报告")
        self.log("=" * 50)
        
        passed = sum(1 for r in self.test_results if r.passed)
        failed = len(self.test_results) - passed
        total = len(self.test_results)
        
        self.log(f"总测试数: {total}")
        self.log(f"通过: {passed}")
        self.log(f"失败: {failed}")
        self.log(f"通过率: {passed/total*100:.1f}%" if total > 0 else "通过率: 0%")
        
        errors = [r for r in self.test_results if not r.passed and r.severity == TestSeverity.ERROR]
        if errors:
            self.log("\n错误详情:")
            for e in errors:
                self.log(f"  - {e.test_name}: {e.message}", TestSeverity.ERROR)
        
        warnings = [r for r in self.test_results if r.severity == TestSeverity.WARNING]
        if warnings:
            self.log("\n警告:")
            for w in warnings:
                self.log(f"  - {w.message}", TestSeverity.WARNING)
        
    def reset_all(self):
        self.scene.clear_scene()
        self.test_nodes.clear()
        self.test_results.clear()
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("就绪 - 点击 [生成拓扑] 开始")
        self.status_label.setStyleSheet("padding: 10px; background: #e8f5e9; border-radius: 5px;")
        self.update_stats()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AITestWindow()
    window.show()
    sys.exit(app.exec())
