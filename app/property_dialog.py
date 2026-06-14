from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox,
    QDialogButtonBox, QVBoxLayout, QLabel, QGroupBox,
    QHBoxLayout, QPushButton, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QWidget
)
from PySide6.QtCore import Qt

from core.component import PowerModule

CALC_TYPE_LABELS = {
    "root": "根结点",
    "switching": "开关电源",
    "ldo": "线性稳压 (LDO)",
    "isolated": "隔离器件",
    "load": "负载",
}


class PropertyDialog(QDialog):
    def __init__(self, component, parent=None):
        super().__init__(parent)
        self._component = component
        ct = getattr(component, 'calc_type', 'switching')
        label = CALC_TYPE_LABELS.get(ct, ct)
        self.setWindowTitle(f"属性编辑 - {component.name} ({label})")
        self.setMinimumWidth(400)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_edit = QLineEdit()
        form.addRow("名称:", self._name_edit)

        ct = getattr(self._component, 'calc_type', 'switching')
        self._calc_label = QLabel(CALC_TYPE_LABELS.get(ct, ct))
        form.addRow("计算类型:", self._calc_label)

        self._desc_edit = QLineEdit()
        form.addRow("描述:", self._desc_edit)

        layout.addLayout(form)

        if ct == "load":
            self._setup_load_fields(layout)
        elif ct == "root":
            self._setup_root_fields(layout)
        elif ct == "switching":
            self._setup_switching_fields(layout)
        elif ct == "ldo":
            self._setup_ldo_fields(layout)
        elif ct == "isolated":
            self._setup_isolated_note(layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _setup_load_fields(self, layout):
        group = QGroupBox("负载参数")
        form = QFormLayout()

        self._vload_spin = QDoubleSpinBox()
        self._vload_spin.setRange(0, 1000)
        self._vload_spin.setSuffix(" V")
        self._vload_spin.setDecimals(2)
        self._vload_spin.setToolTip("负载工作电压，需与上游模块输出电压匹配")
        form.addRow("负载电压:", self._vload_spin)

        self._iload_spin = QDoubleSpinBox()
        self._iload_spin.setRange(0, 1000)
        self._iload_spin.setSuffix(" A")
        self._iload_spin.setDecimals(3)
        form.addRow("负载电流:", self._iload_spin)

        group.setLayout(form)
        layout.addWidget(group)

    def _setup_root_fields(self, layout):
        group = QGroupBox("源参数")
        form = QFormLayout()

        self._vout_spin = QDoubleSpinBox()
        self._vout_spin.setRange(0, 1000)
        self._vout_spin.setSuffix(" V")
        self._vout_spin.setDecimals(2)
        form.addRow("输出电压:", self._vout_spin)

        group.setLayout(form)
        layout.addWidget(group)

    def _setup_switching_fields(self, layout):
        group = QGroupBox("电气参数")
        form = QFormLayout()

        self._vout_spin = QDoubleSpinBox()
        self._vout_spin.setRange(0, 1000)
        self._vout_spin.setSuffix(" V")
        self._vout_spin.setDecimals(2)
        form.addRow("输出电压:", self._vout_spin)

        self._imax_spin = QDoubleSpinBox()
        self._imax_spin.setRange(0, 1000)
        self._imax_spin.setSuffix(" A")
        self._imax_spin.setDecimals(3)
        form.addRow("最大电流:", self._imax_spin)

        self._eff_mode_combo = QComboBox()
        self._eff_mode_combo.addItems(["fixed", "curve"])
        form.addRow("效率模式:", self._eff_mode_combo)

        self._eff_spin = QDoubleSpinBox()
        self._eff_spin.setRange(0.1, 100)
        self._eff_spin.setSuffix(" %")
        self._eff_spin.setDecimals(1)
        form.addRow("效率:", self._eff_spin)

        self._eff_mode_combo.currentTextChanged.connect(self._on_efficiency_mode_changed)

        self._curve_table = QTableWidget()
        self._curve_table.setColumnCount(2)
        self._curve_table.setHorizontalHeaderLabels(["负载电流 (A)", "效率 (%)"])
        self._curve_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._curve_table.setMinimumHeight(120)
        self._curve_table.setVisible(False)
        form.addRow("效率曲线:", self._curve_table)

        self._curve_btn_widget = QWidget()
        curve_btn_layout = QHBoxLayout(self._curve_btn_widget)
        curve_btn_layout.setContentsMargins(0, 0, 0, 0)
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(40)
        add_btn.clicked.connect(self._add_curve_row)
        remove_btn = QPushButton("-")
        remove_btn.setFixedWidth(40)
        remove_btn.clicked.connect(self._remove_curve_row)
        curve_btn_layout.addWidget(add_btn)
        curve_btn_layout.addWidget(remove_btn)
        curve_btn_layout.addStretch()
        self._curve_btn_widget.setVisible(False)
        form.addRow("", self._curve_btn_widget)

        group.setLayout(form)
        layout.addWidget(group)

    def _setup_ldo_fields(self, layout):
        group = QGroupBox("电气参数")
        form = QFormLayout()

        self._vout_spin = QDoubleSpinBox()
        self._vout_spin.setRange(0, 1000)
        self._vout_spin.setSuffix(" V")
        self._vout_spin.setDecimals(2)
        form.addRow("输出电压:", self._vout_spin)

        self._imax_spin = QDoubleSpinBox()
        self._imax_spin.setRange(0, 1000)
        self._imax_spin.setSuffix(" A")
        self._imax_spin.setDecimals(3)
        form.addRow("最大电流:", self._imax_spin)

        group.setLayout(form)
        layout.addWidget(group)

    def _setup_isolated_note(self, layout):
        note = QLabel("隔离器件无需配置电气参数。\n"
                      "Vin = Vout（来自上游），Iin = Iout（来自下游），零损耗。")
        note.setStyleSheet("color: #666; padding: 12px;")
        layout.addWidget(note)

    def _load_data(self):
        c = self._component
        self._name_edit.setText(c.name)
        self._desc_edit.setText(c.description)

        if hasattr(self, "_vload_spin"):
            self._vload_spin.setValue(c.input_voltage)
        if hasattr(self, "_iload_spin"):
            self._iload_spin.setValue(c.output_current)
        if hasattr(self, "_vout_spin"):
            self._vout_spin.setValue(c.output_voltage)
        if hasattr(self, "_imax_spin"):
            self._imax_spin.setValue(c.max_current)
        if hasattr(self, "_eff_mode_combo") and hasattr(c, "efficiency_mode"):
            self._eff_mode_combo.setCurrentText(c.efficiency_mode)
        if hasattr(self, "_eff_spin"):
            self._eff_spin.setValue(c.efficiency)
        if hasattr(self, "_curve_table") and hasattr(c, "efficiency_curve"):
            self._curve_table.setRowCount(0)
            for x_val, y_val in c.efficiency_curve:
                row = self._curve_table.rowCount()
                self._curve_table.insertRow(row)
                self._curve_table.setItem(row, 0, QTableWidgetItem(str(x_val)))
                self._curve_table.setItem(row, 1, QTableWidgetItem(str(y_val)))
        if hasattr(self, "_eff_mode_combo"):
            self._on_efficiency_mode_changed(self._eff_mode_combo.currentText())

    def _on_efficiency_mode_changed(self, text):
        self._eff_spin.setEnabled(text == "fixed")
        show_curve = (text == "curve")
        self._curve_table.setVisible(show_curve)
        self._curve_btn_widget.setVisible(show_curve)

    def _add_curve_row(self):
        row = self._curve_table.rowCount()
        self._curve_table.insertRow(row)
        self._curve_table.setItem(row, 0, QTableWidgetItem("0"))
        self._curve_table.setItem(row, 1, QTableWidgetItem("100"))

    def _remove_curve_row(self):
        row = self._curve_table.currentRow()
        if row >= 0:
            self._curve_table.removeRow(row)

    def _on_accept(self):
        c = self._component
        c.name = self._name_edit.text().strip()
        if not c.name:
            QMessageBox.warning(self, "错误", "名称不能为空")
            return
        c.description = self._desc_edit.text().strip()

        if hasattr(self, "_vload_spin"):
            c.input_voltage = self._vload_spin.value()
        if hasattr(self, "_iload_spin"):
            c.output_current = self._iload_spin.value()
        if hasattr(self, "_vout_spin"):
            c.output_voltage = self._vout_spin.value()
        if hasattr(self, "_imax_spin"):
            c.max_current = self._imax_spin.value()
        if hasattr(self, "_eff_mode_combo") and hasattr(c, "efficiency_mode"):
            c.efficiency_mode = self._eff_mode_combo.currentText()
        if hasattr(self, "_eff_spin"):
            c.efficiency = self._eff_spin.value()
        if hasattr(self, "_curve_table") and hasattr(c, "efficiency_curve"):
            c.efficiency_curve.clear()
            for row in range(self._curve_table.rowCount()):
                try:
                    x = float(self._curve_table.item(row, 0).text())
                    y = float(self._curve_table.item(row, 1).text())
                    c.efficiency_curve.append((x, y))
                except (ValueError, AttributeError):
                    pass

        self.accept()

    @property
    def component(self):
        return self._component
