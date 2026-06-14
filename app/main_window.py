import logging
from PySide6.QtCore import Qt, QPointF
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QStatusBar, QMessageBox, QFileDialog
)
from PySide6.QtGui import QAction, QKeySequence, QColor
from PySide6.QtGui import QUndoStack

from .canvas_scene import CanvasScene
from .canvas_view import CanvasView
from .library_panel import LibraryPanel
from .library_dialog import LibraryDialog
from .node_item import NodeItem
from .exporter import Exporter

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, tree_model, library_manager, parent=None):
        super().__init__(parent)
        self._tree_model = tree_model
        self._library = library_manager
        self._current_file_path: str | None = None
        self._dirty = False
        self.setWindowTitle("电源树图形化设计工具 (Power Tree Designer)")
        self.resize(1280, 800)

        tree_model.set_library(library_manager)

        self._scene = CanvasScene(tree_model)
        self._view = CanvasView(self._scene)
        self._exporter = Exporter(self._scene, self)

        self._undo_stack = QUndoStack(self)
        self._scene.set_undo_stack(self._undo_stack)

        self._library_panel = LibraryPanel(library_manager)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._library_panel)
        splitter.addWidget(self._view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        self.setCentralWidget(splitter)

        self._setup_menus()
        self._setup_status_bar()

        self._library_panel._load_templates()

        tree_model.calculationRequested.connect(self._on_calculate_auto)
        self._scene.paramEdited.connect(self._mark_dirty)
        self._scene.paramEdited.connect(self._on_calculate_auto)

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._update_title()

    def _update_title(self):
        star = " *" if self._dirty else ""
        name = self._current_file_path or "未命名"
        self.setWindowTitle(f"电源树图形化设计工具 (Power Tree Designer) - {name}{star}")

    def _setup_menus(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("文件(&F)")

        new_action = QAction("新建(&N)", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._on_new)
        file_menu.addAction(new_action)

        save_action = QAction("保存(&S)", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._on_save)
        file_menu.addAction(save_action)

        load_action = QAction("打开(&O)", self)
        load_action.setShortcut(QKeySequence.Open)
        load_action.triggered.connect(self._on_load)
        file_menu.addAction(load_action)

        file_menu.addSeparator()
        export_pdf_action = QAction("导出为PDF(&P)...", self)
        export_pdf_action.triggered.connect(self._on_export_pdf)
        file_menu.addAction(export_pdf_action)

        export_png_action = QAction("导出为PNG(&G)...", self)
        export_png_action.triggered.connect(self._on_export_png)
        file_menu.addAction(export_png_action)

        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu("编辑(&E)")
        undo_action = self._undo_stack.createUndoAction(self, "撤销(&U)")
        undo_action.setShortcut(QKeySequence.Undo)
        edit_menu.addAction(undo_action)
        redo_action = self._undo_stack.createRedoAction(self, "重做(&R)")
        redo_action.setShortcut(QKeySequence.Redo)
        edit_menu.addAction(redo_action)

        library_menu = menu_bar.addMenu("器件库(&L)")
        manage_action = QAction("管理器件库(&M)...", self)
        manage_action.triggered.connect(self._on_manage_library)
        library_menu.addAction(manage_action)

        view_menu = menu_bar.addMenu("视图(&V)")
        zoom_in_action = QAction("放大", self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(lambda: self._view.scale(1.2, 1.2))
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("缩小", self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(lambda: self._view.scale(1 / 1.2, 1 / 1.2))
        view_menu.addAction(zoom_out_action)

        fit_action = QAction("适合窗口", self)
        fit_action.triggered.connect(lambda: self._view.fitInView(
            self._scene.itemsBoundingRect(), Qt.KeepAspectRatio))
        view_menu.addAction(fit_action)

        view_menu.addSeparator()
        grid_visible_action = QAction("显示格点", self)
        grid_visible_action.setCheckable(True)
        grid_visible_action.setChecked(True)
        grid_visible_action.triggered.connect(
            lambda checked: self._scene.set_grid_visible(checked))
        view_menu.addAction(grid_visible_action)

        grid_snap_action = QAction("吸附格点", self)
        grid_snap_action.setCheckable(True)
        grid_snap_action.setChecked(True)
        grid_snap_action.triggered.connect(
            lambda checked: self._scene.set_grid_snap(checked))
        view_menu.addAction(grid_snap_action)

        grid_size_menu = view_menu.addMenu("格点间距")
        for gs in [10, 20, 50, 100]:
            action = QAction(f"{gs} px", self)
            action.triggered.connect(lambda checked, s=gs: self._scene.set_grid_size(s))
            grid_size_menu.addAction(action)

        calc_menu = menu_bar.addMenu("计算(&C)")
        calc_action = QAction("执行计算(&R)", self)
        calc_action.setShortcut(QKeySequence("F5"))
        calc_action.triggered.connect(self._on_calculate)
        calc_menu.addAction(calc_action)

    def _setup_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪 - 从左侧器件库拖放模块到画布，或从节点输出端口拖拽到输入端口建立连接")

    def closeEvent(self, event):
        if not self._check_save():
            event.ignore()
            return
        super().closeEvent(event)

    def _check_save(self) -> bool:
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self, "未保存的更改",
            "当前工程有未保存的更改，是否保存？",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Save:
            return self._on_save()
        elif reply == QMessageBox.Cancel:
            return False
        return True

    def _on_new(self):
        if not self._check_save():
            return
        reply = QMessageBox.question(self, "确认", "确定要新建工程吗？当前未保存的数据将丢失。")
        if reply == QMessageBox.Yes:
            self._scene.clear_scene()
            self._tree_model.clear_all()
            self._current_file_path = None
            self._dirty = False
            self._update_title()
            self._status_bar.showMessage("新建工程")

    def _on_save(self) -> bool:
        path = self._current_file_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "保存工程", "", "JSON文件 (*.json)")
            if not path:
                return False
        from utils.file_io import ProjectIO
        tree_data = self._tree_model.to_dict()
        positions = self._scene.get_node_positions()
        ok = ProjectIO.save_project(path, tree_data, positions)
        if ok:
            self._current_file_path = path
            self._dirty = False
            self._update_title()
            self._status_bar.showMessage(f"已保存: {path}")
        else:
            QMessageBox.warning(self, "保存失败", f"无法保存到:\n{path}\n请检查磁盘空间和权限。")
        return ok

    def _on_load(self):
        if not self._check_save():
            return
        path, _ = QFileDialog.getOpenFileName(self, "打开工程", "", "JSON文件 (*.json)")
        if not path:
            return
        from utils.file_io import ProjectIO
        project = ProjectIO.load_project(path)
        if project is None:
            QMessageBox.critical(self, "加载失败", f"无法加载工程文件:\n{path}\n\n可能原因：\n- 文件不存在或无读取权限\n- JSON格式损坏")
            return
        try:
            self._scene.clear_scene()
            self._tree_model.clear_all()
            new_roots = type(self._tree_model).load_roots(project["tree"])
            for root in new_roots:
                self._tree_model.add_root_node(root)
            self._restore_scene(project.get("positions", {}))
            self._current_file_path = path
            self._dirty = False
            self._update_title()
            self._status_bar.showMessage(f"已加载: {path}")
        except Exception as e:
            logger.error("加载工程异常: %s", e, exc_info=True)
            QMessageBox.critical(self, "加载错误", f"加载工程时发生错误:\n{e}")

    def _restore_scene(self, positions: dict):
        for root_node in self._tree_model.root_nodes:
            self._restore_node_recursive(root_node, positions)
        self._scene.update_all_edges()

    def _restore_node_recursive(self, node, positions: dict):
        component = node.component
        node_item = self._scene.find_node_item_by_id(node.node_id)
        if node_item is None:
            pos_data = positions.get(node.node_id, {"x": 50, "y": 50})
            vw = pos_data.get("width")
            vh = pos_data.get("height")
            vc = pos_data.get("color")
            node_color = QColor(vc) if vc else None
            inp = pos_data.get("input_ports", 1)
            outp = pos_data.get("output_ports", 1)
            node_item = NodeItem(node.node_id, component.comp_type, component.name,
                                 node_width=vw, node_height=vh, node_color=node_color,
                                 input_ports=inp, output_ports=outp)
            node_item.set_component(component)
            node_item.setPos(QPointF(pos_data["x"], pos_data["y"]))
            self._scene.addItem(node_item)
            self._scene._node_items[node.node_id] = node_item
            self._scene._connect_node_signals(node_item)
        for child_node in node.children:
            self._restore_node_recursive(child_node, positions)
            self._scene._create_edge(node.node_id, child_node.node_id)

    def _on_manage_library(self):
        dlg = LibraryDialog(self._library, self)
        dlg.exec()
        self._library_panel._load_templates()

    def _on_calculate(self):
        self._do_calculate(show_result=True)

    def _on_calculate_auto(self):
        self._do_calculate(show_result=False)

    def _do_calculate(self, show_result: bool = True):
        from core.calculator import Calculator
        results, warnings = Calculator.calculate(self._tree_model)
        for r in results:
            item = self._scene.find_node_item_by_id(r.node_id)
            if item:
                item.set_calc_result(r)
        summary = Calculator.summary(results)
        text = "计算结果:\n"
        text += "-" * 70 + "\n"
        text += f"{'名称':<16} {'Vin':>8} {'Vout':>8} {'Iin':>8} {'Iout':>8} {'Pin':>8} {'Pout':>8} {'Ploss':>8} {'Eff':>6}\n"
        text += "-" * 70 + "\n"
        for r in results:
            text += f"{r.name:<16} {r.vin:>7.2f}V {r.vout:>7.2f}V {r.iin:>7.3f}A {r.iout:>7.3f}A "
            text += f"{r.pin:>7.3f}W {r.pout:>7.3f}W {r.ploss:>7.3f}W {r.efficiency:>5.1f}%\n"
        text += "-" * 70 + "\n"
        text += f"系统总输入功率: {summary['total_input_power']:.3f}W\n"
        text += f"系统总输出功率: {summary['total_output_power']:.3f}W\n"
        text += f"系统总损耗:     {summary['total_loss']:.3f}W\n"
        text += f"系统总效率:     {summary['system_efficiency']:.1f}%\n"
        text += f"母线最大电流:   {summary['max_bus_current']:.3f}A\n"

        has_warnings = (warnings.voltage_mismatch or warnings.overcurrent
                        or warnings.low_efficiency)
        if has_warnings:
            text += "\n" + "=" * 50 + "\n"
            text += "警告:\n"
            for w in warnings.voltage_mismatch:
                text += f"  [电压不匹配] {w}\n"
            for w in warnings.overcurrent:
                text += f"  [过流] {w}\n"
            for w in warnings.low_efficiency:
                text += f"  [效率偏低] {w}\n"

        if show_result:
            icon = QMessageBox.Warning if has_warnings else QMessageBox.Information
            QMessageBox(icon, "计算结果", text, QMessageBox.Ok, self).exec()

    def _on_export_pdf(self):
        if self._exporter.export_to_pdf():
            self.statusBar().showMessage("PDF导出成功", 3000)

    def _on_export_png(self):
        if self._exporter.export_to_png(scale=2.0):
            self.statusBar().showMessage("PNG导出成功", 3000)
