from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QLineEdit, QComboBox,
    QFormLayout, QDialogButtonBox, QMessageBox,
    QSpinBox, QColorDialog, QLabel
)
from PySide6.QtGui import QColor

from core.library_manager import CALC_TYPES

CALC_TYPE_LABELS = {
    "root": "根结点 (Vout=Vset)",
    "switching": "开关电源 (buck/boost)",
    "ldo": "线性稳压 (LDO)",
    "isolated": "隔离器件 (MOS/EFUSE/磁珠)",
    "load": "负载",
}


class LibraryDialog(QDialog):
    def __init__(self, library_manager, parent=None):
        super().__init__(parent)
        self._library = library_manager
        self.setWindowTitle("器件库管理")
        self.setMinimumSize(550, 500)
        self._setup_ui()
        self._load_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self._list_widget = QListWidget()
        layout.addWidget(self._list_widget)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("添加")
        self._edit_btn = QPushButton("编辑")
        self._delete_btn = QPushButton("删除")
        btn_layout.addWidget(self._add_btn)
        btn_layout.addWidget(self._edit_btn)
        btn_layout.addWidget(self._delete_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn.clicked.connect(self._on_edit)
        self._delete_btn.clicked.connect(self._on_delete)

    def _load_list(self):
        self._list_widget.clear()
        for tmpl in self._library.templates:
            ct = tmpl.get("calc_type", "switching")
            label = CALC_TYPE_LABELS.get(ct, ct)
            in_p = tmpl.get("input_ports", 1)
            out_p = tmpl.get("output_ports", 1)
            text = f"{tmpl['name']}  [{label}]  INx{in_p} OUTx{out_p}"
            self._list_widget.addItem(text)

    def _on_add(self):
        dialog = _TemplateEditDialog(self, title="添加模板")
        if dialog.exec() == QDialog.Accepted:
            self._library.add_template(
                dialog.template_name,
                dialog.template_calc_type,
                dialog.template_width, dialog.template_height,
                dialog.template_color,
                dialog.template_input_ports, dialog.template_output_ports,
            )
            self._load_list()

    def _on_edit(self):
        row = self._list_widget.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一个模板")
            return
        tmpl = self._library.templates[row]
        dialog = _TemplateEditDialog(
            self, title="编辑模板",
            name=tmpl["name"],
            calc_type=tmpl.get("calc_type", "switching"),
            width=tmpl.get("width", 140), height=tmpl.get("height", 60),
            color=tmpl.get("color", "#64A0E6"),
            input_ports=tmpl.get("input_ports", 1),
            output_ports=tmpl.get("output_ports", 1),
        )
        if dialog.exec() == QDialog.Accepted:
            self._library.update_template(
                row, dialog.template_name,
                dialog.template_calc_type,
                dialog.template_width, dialog.template_height,
                dialog.template_color,
                dialog.template_input_ports, dialog.template_output_ports,
            )
            self._load_list()

    def _on_delete(self):
        row = self._list_widget.currentRow()
        if row < 0:
            return
        reply = QMessageBox.question(self, "确认", "确定要删除该模板吗？")
        if reply == QMessageBox.Yes:
            self._library.remove_template(row)
            self._load_list()


class _TemplateEditDialog(QDialog):
    def __init__(self, parent=None, title="", name="", calc_type="switching",
                 width=140, height=60, color="#64A0E6",
                 input_ports=1, output_ports=1):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        layout = QFormLayout(self)

        self._name_edit = QLineEdit(name)
        layout.addRow("名称:", self._name_edit)

        self._calc_combo = QComboBox()
        for ct in CALC_TYPES:
            self._calc_combo.addItem(CALC_TYPE_LABELS.get(ct, ct), ct)
        idx = self._calc_combo.findData(calc_type)
        if idx >= 0:
            self._calc_combo.setCurrentIndex(idx)
        self._calc_combo.currentIndexChanged.connect(self._on_calc_type_changed)
        layout.addRow("计算类型:", self._calc_combo)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(60, 400)
        self._width_spin.setValue(width)
        self._width_spin.setSuffix(" px")
        layout.addRow("外框宽度:", self._width_spin)

        self._height_spin = QSpinBox()
        self._height_spin.setRange(40, 300)
        self._height_spin.setValue(height)
        self._height_spin.setSuffix(" px")
        layout.addRow("外框高度:", self._height_spin)

        self._color = color
        self._color_label = QLabel()
        self._update_color_preview()
        color_btn = QPushButton("选择颜色...")
        color_btn.clicked.connect(self._pick_color)
        color_row = QHBoxLayout()
        color_row.addWidget(self._color_label)
        color_row.addWidget(color_btn)
        color_row.addStretch()
        layout.addRow("外框颜色:", color_row)

        self._input_ports_spin = QSpinBox()
        self._input_ports_spin.setRange(0, 8)
        self._input_ports_spin.setValue(input_ports)
        layout.addRow("输入端口数:", self._input_ports_spin)

        self._output_ports_spin = QSpinBox()
        self._output_ports_spin.setRange(0, 8)
        self._output_ports_spin.setValue(output_ports)
        layout.addRow("输出端口数:", self._output_ports_spin)

        self._on_calc_type_changed()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_calc_type_changed(self):
        ct = self._calc_combo.currentData()
        if ct == "load":
            self._output_ports_spin.setValue(0)
            self._output_ports_spin.setEnabled(False)
            self._input_ports_spin.setEnabled(True)
        elif ct == "root":
            self._input_ports_spin.setValue(0)
            self._input_ports_spin.setEnabled(False)
            self._output_ports_spin.setEnabled(True)
        else:
            self._input_ports_spin.setEnabled(True)
            self._output_ports_spin.setEnabled(True)

    def _update_color_preview(self):
        self._color_label.setStyleSheet(
            f"background-color: {self._color}; border: 1px solid #888; "
            f"min-width: 40px; min-height: 20px;"
        )

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self, "选择外框颜色")
        if c.isValid():
            self._color = c.name()
            self._update_color_preview()

    @property
    def template_name(self):
        return self._name_edit.text().strip()

    @property
    def template_calc_type(self):
        return self._calc_combo.currentData()

    @property
    def template_width(self):
        return self._width_spin.value()

    @property
    def template_height(self):
        return self._height_spin.value()

    @property
    def template_color(self):
        return self._color

    @property
    def template_input_ports(self):
        return self._input_ports_spin.value()

    @property
    def template_output_ports(self):
        return self._output_ports_spin.value()

    def _on_accept(self):
        if not self.template_name:
            QMessageBox.warning(self, "错误", "名称不能为空")
            return
        self.accept()
