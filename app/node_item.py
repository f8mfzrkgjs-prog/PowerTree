from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QPainter, QBrush, QColor, QPen, QFont, QLinearGradient, QPainterPath
)
from PySide6.QtWidgets import (
    QGraphicsObject, QGraphicsSceneContextMenuEvent,
    QGraphicsProxyWidget, QStyleOptionGraphicsItem, QWidget, QMenu,
    QLineEdit, QApplication
)

from config import (
    NodeConfig, PortConfig, ResizeConfig, GridConfig, Colors
)

DEFAULT_NODE_WIDTH = NodeConfig.DEFAULT_WIDTH
DEFAULT_NODE_HEIGHT = NodeConfig.DEFAULT_HEIGHT
PORT_RADIUS = PortConfig.PORT_RADIUS
PORT_DETECT_RADIUS = PortConfig.PORT_DETECT_RADIUS
PORT_SPACING = PortConfig.PORT_SPACING
RESIZE_HANDLE_SIZE = ResizeConfig.RESIZE_HANDLE_SIZE
MIN_NODE_WIDTH = NodeConfig.MIN_WIDTH
MIN_NODE_HEIGHT = NodeConfig.MIN_HEIGHT
HEADER_HEIGHT = NodeConfig.HEADER_HEIGHT
PARAM_ROW_HEIGHT = NodeConfig.PARAM_ROW_HEIGHT
PARAM_TOP_MARGIN = NodeConfig.PARAM_TOP_MARGIN
BODY_BOTTOM_PADDING = NodeConfig.BODY_BOTTOM_PADDING
PLOSS_SECTION_HEIGHT = NodeConfig.PLOSS_SECTION_HEIGHT

NODE_GRID_SIZE = GridConfig.NODE_GRID_SIZE

DEFAULT_TYPE_COLORS = {k: QColor(v) for k, v in Colors.TYPE_COLORS.items()}
HEADER_COLORS = {k: QColor(v) for k, v in Colors.HEADER_COLORS.items()}

_cached_fonts = {
    "name": None,
    "section": None,
    "label": None,
    "value": None,
    "port": None,
}

def _get_cached_font(key: str, family: str, size: int, bold: bool = False) -> QFont:
    cache_key = f"{key}_{size}_{bold}"
    if cache_key not in _cached_fonts or _cached_fonts[cache_key] is None:
        font = QFont(family, size, QFont.Bold if bold else QFont.Normal)
        _cached_fonts[cache_key] = font
    return _cached_fonts[cache_key]

COMP_ATTR_MAP = {
    "vin": ("input_voltage", "V", "{:.2f}"),
    "vout": ("output_voltage", "V", "{:.2f}"),
    "iin": ("input_current", "A", "{:.3f}"),
    "iout": ("output_current", "A", "{:.3f}"),
    "iload": ("output_current", "A", "{:.3f}"),
    "efficiency": ("efficiency", "%", "{:.1f}"),
}

CALC_ONLY_ATTRS = {"pin", "pout", "ploss"}

BOTTOM_INFO = {
    "root": ("Pout", "pout"),
    "load": ("Puse", "pin"),
    "switching": ("Ploss", "ploss"),
    "ldo": ("Ploss", "ploss"),
}

PARAM_LAYOUTS = {
    "switching": {
        "in": [("Vin", "V", "vin"), ("Iin", "A", "iin")],
        "out": [("Vout", "V", "vout"), ("Iout", "A", "iout"), ("\u03b7", "%", "efficiency")],
    },
    "root": {
        "in": [],
        "out": [("Vout", "V", "vout"), ("Iout", "A", "iout")],
    },
    "ldo": {
        "in": [("Vin", "V", "vin"), ("Iin", "A", "iin")],
        "out": [("Vout", "V", "vout"), ("Iout", "A", "iout"), ("\u03b7", "%", "efficiency")],
    },
    "isolated": {
        "in": [("Vin", "V", "vin")],
        "out": [("Iout", "A", "iout")],
    },
    "load": {
        "in": [("Vload", "V", "vin"), ("Iload", "A", "iload")],
        "out": [],
    },
}


class NodeItem(QGraphicsObject):
    nodeMoved = Signal(str)
    nodeDoubleClicked = Signal(str)
    nodeDeleteRequested = Signal(str)
    nodeEditRequested = Signal(str)
    nodeCopyRequested = Signal(str)
    nodePasteRequested = Signal(QPointF)
    nodeResized = Signal(str)
    paramEdited = Signal(str, str, object)

    _resize_cursors = {
        "TL": Qt.SizeFDiagCursor, "T": Qt.SizeVerCursor, "TR": Qt.SizeBDiagCursor,
        "R": Qt.SizeHorCursor, "BR": Qt.SizeFDiagCursor, "B": Qt.SizeVerCursor,
        "BL": Qt.SizeBDiagCursor, "L": Qt.SizeHorCursor,
    }

    def __init__(self, node_id: str, comp_type: str, name: str, parent=None,
                 node_width: int = None, node_height: int = None,
                 node_color: QColor = None,
                 input_ports: int = 1, output_ports: int = 1):
        super().__init__(parent)
        self._node_id = node_id
        self._comp_type = comp_type
        self._name = name
        self._width = node_width or DEFAULT_NODE_WIDTH
        self._height = node_height or DEFAULT_NODE_HEIGHT
        self._color = node_color or DEFAULT_TYPE_COLORS.get(comp_type, QColor(80, 80, 80))
        self._input_ports = input_ports
        self._output_ports = output_ports
        self._component = None
        self._calc_result = None
        self._resizing = False
        self._resize_dir = None
        self._resize_start_pos = QPointF()
        self._resize_start_size = (self._width, self._height)
        self._hover_resize = None
        self._edit_proxy = None
        self._edit_attr = None
        self._edit_applied = False
        self._hover_input_port = -1
        self._hover_output_port = -1
        self.setFlags(
            QGraphicsObject.ItemIsMovable |
            QGraphicsObject.ItemIsSelectable |
            QGraphicsObject.ItemSendsGeometryChanges |
            QGraphicsObject.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.OpenHandCursor)

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def comp_type(self) -> str:
        return self._comp_type

    @comp_type.setter
    def comp_type(self, value: str):
        self._comp_type = value
        self._fit_to_content()
        self.update()

    @property
    def node_name(self) -> str:
        return self._name

    @node_name.setter
    def node_name(self, value: str):
        self._name = value
        self.update()

    @property
    def input_ports(self) -> int:
        return self._input_ports

    @property
    def output_ports(self) -> int:
        return self._output_ports

    def set_color(self, color: QColor):
        self._color = color
        self.update()

    def set_hover_port(self, port_type: str = None, port_index: int = -1):
        """设置悬停高亮的端口。port_type: 'in'/'out'/None"""
        if port_type == 'in':
            if self._hover_input_port != port_index:
                self._hover_input_port = port_index
                self._hover_output_port = -1
                self.update()
        elif port_type == 'out':
            if self._hover_output_port != port_index:
                self._hover_output_port = port_index
                self._hover_input_port = -1
                self.update()
        else:
            if self._hover_input_port != -1 or self._hover_output_port != -1:
                self._hover_input_port = -1
                self._hover_output_port = -1
                self.update()

    @property
    def node_width(self) -> int:
        return self._width

    @property
    def node_height(self) -> int:
        return self._height

    def set_component(self, comp):
        self._component = comp
        self._fit_to_content()
        self.update()

    def set_calc_result(self, result):
        self._calc_result = result
        self.update()

    def _calc_content_height(self) -> float:
        layout = self._get_param_layout()
        in_rows = len(layout.get("in", []))
        out_rows = len(layout.get("out", []))
        max_rows = max(in_rows, out_rows, 1)
        ct = getattr(self._component, 'calc_type', self._comp_type) if self._component else self._comp_type
        bottom_h = PLOSS_SECTION_HEIGHT if BOTTOM_INFO.get(ct) else 0
        return PARAM_TOP_MARGIN + max_rows * PARAM_ROW_HEIGHT + bottom_h + BODY_BOTTOM_PADDING

    def _fit_to_content(self):
        content_h = self._calc_content_height()
        gs = NODE_GRID_SIZE
        snapped_h = ((int(content_h) + gs - 1) // gs) * gs
        new_h = max(MIN_NODE_HEIGHT, snapped_h)
        if new_h != self._height:
            self.prepareGeometryChange()
            self._height = new_h
            self.nodeResized.emit(self._node_id)

    def _port_y(self, index: int, total: int) -> float:
        gs = NODE_GRID_SIZE
        if total <= 1:
            return int(self._height / 2 / gs + 0.5) * gs
        step = min(PORT_SPACING, (self._height - 10) / (total - 1)) if total > 1 else 0
        total_h = step * (total - 1)
        start_y = (self._height - total_h) / 2
        return int((start_y + index * step) / gs + 0.5) * gs

    def input_port_pos(self, index: int = 0) -> QPointF:
        return self.mapToScene(QPointF(0, self._port_y(index, self._input_ports)))

    def output_port_pos(self, index: int = 0) -> QPointF:
        return self.mapToScene(QPointF(self._width, self._port_y(index, self._output_ports)))

    def input_port_local(self, index: int = 0) -> QPointF:
        return QPointF(0, self._port_y(index, self._input_ports))

    def output_port_local(self, index: int = 0) -> QPointF:
        return QPointF(self._width, self._port_y(index, self._output_ports))

    def boundingRect(self) -> QRectF:
        m = PORT_RADIUS + 2
        return QRectF(-m, -m, self._width + m * 2, self._height + m * 2)

    def _get_resize_zones(self):
        w, h = self._width, self._height
        d = RESIZE_HANDLE_SIZE
        return {
            "TL": QRectF(-d, -d, d * 2, d * 2),
            "T": QRectF(w / 2 - d, -d, d * 2, d * 2),
            "TR": QRectF(w - d, -d, d * 2, d * 2),
            "R": QRectF(w - d, h / 2 - d, d * 2, d * 2),
            "BR": QRectF(w - d, h - d, d * 2, d * 2),
            "B": QRectF(w / 2 - d, h - d, d * 2, d * 2),
            "BL": QRectF(-d, h - d, d * 2, d * 2),
            "L": QRectF(-d, h / 2 - d, d * 2, d * 2),
        }

    def _hit_resize_zone(self, local_pos: QPointF):
        for name, rect in self._get_resize_zones().items():
            if rect.contains(local_pos):
                return name
        return None

    def _get_param_layout(self):
        ct = getattr(self._component, 'calc_type', self._comp_type) if self._component else self._comp_type
        return PARAM_LAYOUTS.get(ct, {"in": [], "out": []})

    def _get_cell_geometry(self):
        layout = self._get_param_layout()
        has_in = bool(layout.get("in", []))
        has_out = bool(layout.get("out", []))

        if has_in and has_out:
            half_w = self._width / 2
            cell_w = half_w - 10
        elif has_in or has_out:
            half_w = 0
            cell_w = self._width - 12
        else:
            half_w = 0
            cell_w = self._width - 12

        return layout, has_in, has_out, half_w, cell_w

    def _get_param_cell_rects(self):
        rects = []
        layout, has_in, has_out, half_w, cell_w = self._get_cell_geometry()

        if not has_in and not has_out:
            return rects

        row_h = PARAM_ROW_HEIGHT
        y = PARAM_TOP_MARGIN

        for label, unit, attr in layout.get("in", []):
            rects.append((QRectF(4, y, cell_w, row_h), attr, "in"))
            y += row_h

        out_x = half_w + 4 if has_in and has_out else 4
        y = PARAM_TOP_MARGIN
        for label, unit, attr in layout.get("out", []):
            rects.append((QRectF(out_x, y, cell_w, row_h), attr, "out"))
            y += row_h

        return rects

    def _hit_param_cell(self, local_pos: QPointF):
        for rect, attr, side in self._get_param_cell_rects():
            if rect.contains(local_pos):
                return attr, rect
        return None, None

    def _get_value_rect_in_cell(self, cell_rect: QRectF, side: str):
        label_w = 44 if side == "out" else 40
        return QRectF(
            cell_rect.x() + label_w + 4,
            cell_rect.y(),
            cell_rect.width() - label_w - 6,
            cell_rect.height()
        )

    def _read_param_value(self, attr: str):
        if self._calc_result is not None:
            val = getattr(self._calc_result, attr, None)
            if val is not None:
                return val
        if attr in CALC_ONLY_ATTRS:
            return 0.0
        if self._component is None:
            return 0.0
        comp_attr = COMP_ATTR_MAP.get(attr)
        if comp_attr is None:
            return 0.0
        return getattr(self._component, comp_attr[0], 0.0)

    def _format_param_value(self, unit: str, attr: str) -> str:
        val = self._read_param_value(attr)
        fmt = COMP_ATTR_MAP.get(attr, (None, unit, "{:.2f}"))[2]
        return f"{fmt.format(val)}{unit}"

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self._width, self._height
        ct = getattr(self._component, 'calc_type', self._comp_type) if self._component else self._comp_type

        body_rect = QRectF(0, 0, w, h)
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        painter.setBrush(QBrush(QColor(245, 245, 248)))
        painter.drawRoundedRect(body_rect, 6, 6)

        header_color = HEADER_COLORS.get(ct, QColor(60, 60, 60))
        header_path = QPainterPath()
        header_path.moveTo(6, 0)
        header_path.lineTo(w - 6, 0)
        header_path.arcTo(w - 12, 0, 12, 12, 90, -90)
        header_path.lineTo(w, HEADER_HEIGHT)
        header_path.lineTo(0, HEADER_HEIGHT)
        header_path.lineTo(0, 6)
        header_path.arcTo(0, 0, 12, 12, 180, -90)
        header_path.closeSubpath()
        painter.setPen(Qt.NoPen)
        grad = QLinearGradient(0, 0, 0, HEADER_HEIGHT)
        grad.setColorAt(0, header_color.lighter(110))
        grad.setColorAt(1, header_color)
        painter.setBrush(QBrush(grad))
        painter.drawPath(header_path)

        name_font = _get_cached_font("name", "Microsoft YaHei", 10, True)
        painter.setFont(name_font)
        painter.setPen(QPen(Qt.white))
        painter.drawText(QRectF(8, 1, w - 16, HEADER_HEIGHT), Qt.AlignVCenter | Qt.AlignCenter, self._name)

        mid_x = w / 2
        layout, has_in, has_out, half_w, cell_w = self._get_cell_geometry()

        if has_in and has_out:
            divider_end_y = h - PLOSS_SECTION_HEIGHT - 2 if BOTTOM_INFO.get(ct) else h - 2
            painter.setPen(QPen(QColor(200, 200, 200), 1, Qt.DotLine))
            painter.drawLine(QPointF(mid_x, HEADER_HEIGHT + 2), QPointF(mid_x, divider_end_y))

        section_font = _get_cached_font("section", "Microsoft YaHei", 8, True)
        painter.setFont(section_font)
        if has_in:
            painter.setPen(QPen(QColor(60, 100, 180, 180)))
            painter.drawText(QRectF(8, HEADER_HEIGHT + 2, 40, 12), Qt.AlignLeft, "IN")
        if has_out:
            painter.setPen(QPen(QColor(180, 60, 40, 180)))
            painter.drawText(QRectF(w - 48, HEADER_HEIGHT + 2, 40, 12), Qt.AlignRight, "OUT")

        label_font = _get_cached_font("label", "Consolas", 9, False)
        value_font = _get_cached_font("value", "Consolas", 9, True)

        row_h = PARAM_ROW_HEIGHT
        y = PARAM_TOP_MARGIN

        in_x = 4
        for label_text, unit, attr in layout.get("in", []):
            val_text = self._format_param_value(unit, attr)
            cell_rect = QRectF(in_x, y, cell_w, row_h)
            editable = self._is_editable_attr(attr)
            if editable:
                painter.setPen(QPen(QColor(180, 200, 230), 1))
                painter.setBrush(QBrush(QColor(245, 248, 255)))
            else:
                painter.setPen(QPen(QColor(210, 215, 225), 1))
                painter.setBrush(QBrush(QColor(232, 237, 245)))
            painter.drawRoundedRect(cell_rect, 2, 2)
            painter.setFont(label_font)
            painter.setPen(QPen(QColor(80, 80, 80)))
            painter.drawText(QRectF(in_x + 2, y, 40, row_h), Qt.AlignVCenter | Qt.AlignRight, label_text)
            painter.setFont(value_font)
            painter.setPen(QPen(QColor(30, 30, 30)) if editable else QPen(QColor(100, 100, 100)))
            val_rect = self._get_value_rect_in_cell(cell_rect, "in")
            painter.drawText(val_rect, Qt.AlignVCenter | Qt.AlignLeft, val_text)
            y += row_h

        out_x = half_w + 4 if has_in and has_out else 4
        y = PARAM_TOP_MARGIN
        for label_text, unit, attr in layout.get("out", []):
            val_text = self._format_param_value(unit, attr)
            cell_rect = QRectF(out_x, y, cell_w, row_h)
            editable = self._is_editable_attr(attr)
            if editable:
                painter.setPen(QPen(QColor(230, 190, 190), 1))
                painter.setBrush(QBrush(QColor(255, 248, 245)))
            else:
                painter.setPen(QPen(QColor(225, 210, 210), 1))
                painter.setBrush(QBrush(QColor(245, 232, 232)))
            painter.drawRoundedRect(cell_rect, 2, 2)
            painter.setFont(label_font)
            painter.setPen(QPen(QColor(80, 80, 80)))
            painter.drawText(QRectF(out_x + 2, y, 44, row_h), Qt.AlignVCenter | Qt.AlignRight, label_text)
            painter.setFont(value_font)
            painter.setPen(QPen(QColor(30, 30, 30)) if editable else QPen(QColor(100, 100, 100)))
            val_rect = self._get_value_rect_in_cell(cell_rect, "out")
            painter.drawText(val_rect, Qt.AlignVCenter | Qt.AlignLeft, val_text)
            y += row_h

        bottom_info = BOTTOM_INFO.get(ct)
        if bottom_info:
            bottom_y = h - PLOSS_SECTION_HEIGHT
            painter.setPen(QPen(QColor(210, 210, 210), 1))
            painter.drawLine(QPointF(8, bottom_y), QPointF(w - 8, bottom_y))
            blabel, battr = bottom_info
            bval = self._read_param_value(battr)
            btext = f"{blabel}: {bval:.3f}W"
            bfont = QFont("Consolas", 9, QFont.Bold)
            painter.setFont(bfont)
            painter.setPen(QPen(QColor(160, 60, 40)))
            painter.drawText(QRectF(4, bottom_y + 1, w - 8, PLOSS_SECTION_HEIGHT - 2),
                             Qt.AlignCenter, btext)

        if self.isSelected() or self._resizing:
            handle_color = QColor(60, 60, 60)
            painter.setBrush(QBrush(handle_color))
            painter.setPen(QPen(Qt.white, 1))
            for zrect in self._get_resize_zones().values():
                painter.drawRoundedRect(zrect, 2, 2)

        for i in range(self._input_ports):
            p = self.input_port_local(i)
            occupied = False
            scene = self.scene()
            if scene and hasattr(scene, 'is_input_port_occupied'):
                occupied = scene.is_input_port_occupied(self._node_id, i)
            is_hover = (self._hover_input_port == i)
            if is_hover:
                painter.setPen(QPen(QColor(0, 200, 80), 2.5))
                painter.setBrush(QBrush(QColor(0, 200, 80, 80)))
                painter.drawEllipse(p, PORT_RADIUS + 3, PORT_RADIUS + 3)
            painter.setPen(QPen(QColor(40, 40, 40), 1.5))
            grad_p = QLinearGradient(p.x() - PORT_RADIUS, p.y(), p.x() + PORT_RADIUS, p.y())
            if occupied:
                grad_p.setColorAt(0, QColor(160, 160, 160))
                grad_p.setColorAt(1, QColor(120, 120, 120))
            else:
                grad_p.setColorAt(0, QColor(100, 160, 230))
                grad_p.setColorAt(1, QColor(60, 120, 200))
            painter.setBrush(QBrush(grad_p))
            painter.drawEllipse(p, PORT_RADIUS, PORT_RADIUS)
            painter.setPen(QPen(Qt.white, 1))
            port_font = _get_cached_font("port", "Consolas", 6, True)
            painter.setFont(port_font)
            painter.drawText(QRectF(p.x() - PORT_RADIUS, p.y() - PORT_RADIUS, PORT_RADIUS * 2, PORT_RADIUS * 2),
                             Qt.AlignCenter, ">")

        for i in range(self._output_ports):
            p = self.output_port_local(i)
            is_hover = (self._hover_output_port == i)
            if is_hover:
                painter.setPen(QPen(QColor(0, 200, 80), 2.5))
                painter.setBrush(QBrush(QColor(0, 200, 80, 80)))
                painter.drawEllipse(p, PORT_RADIUS + 3, PORT_RADIUS + 3)
            painter.setPen(QPen(QColor(40, 40, 40), 1.5))
            grad_p = QLinearGradient(p.x() - PORT_RADIUS, p.y(), p.x() + PORT_RADIUS, p.y())
            grad_p.setColorAt(0, QColor(230, 100, 80))
            grad_p.setColorAt(1, QColor(200, 60, 40))
            painter.setBrush(QBrush(grad_p))
            painter.drawEllipse(p, PORT_RADIUS, PORT_RADIUS)
            painter.setPen(QPen(Qt.white, 1))
            port_font = _get_cached_font("port", "Consolas", 6, True)
            painter.setFont(port_font)
            painter.drawText(QRectF(p.x() - PORT_RADIUS, p.y() - PORT_RADIUS, PORT_RADIUS * 2, PORT_RADIUS * 2),
                             Qt.AlignCenter, ">")

    def itemChange(self, change, value):
        if change == QGraphicsObject.ItemPositionChange:
            scene = self.scene()
            if scene and hasattr(scene, 'snap_point') and getattr(scene, '_grid_snap', False):
                return scene.snap_point(value)
        if change == QGraphicsObject.ItemPositionHasChanged:
            self.nodeMoved.emit(self._node_id)
        return super().itemChange(change, value)

    def hoverMoveEvent(self, event):
        pos = event.pos()
        zone = self._hit_resize_zone(pos)
        if zone:
            self._hover_resize = zone
            self.setCursor(self._resize_cursors.get(zone, Qt.ArrowCursor))
        else:
            attr, cell_rect = self._hit_param_cell(pos)
            if attr and self._is_editable_attr(attr):
                self.setCursor(Qt.IBeamCursor)
            else:
                self._hover_resize = None
                self.setCursor(Qt.OpenHandCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self._hover_resize = None
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            zone = self._hit_resize_zone(event.pos())
            if zone:
                self._resizing = True
                self._resize_dir = zone
                self._resize_start_pos = event.scenePos()
                self._resize_start_size = (self._width, self._height)
                self._resize_start_corner = event.pos()
                event.accept()
                return
            attr, cell_rect = self._hit_param_cell(event.pos())
            if attr and self._is_editable_attr(attr):
                self._start_inline_edit(attr, cell_rect)
                event.accept()
                return
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing and self._resize_dir:
            delta = event.pos() - self._resize_start_corner
            old_w, old_h = self._resize_start_size
            nw, nh = old_w, old_h
            d = self._resize_dir
            if "L" in d:
                nw = max(MIN_NODE_WIDTH, old_w - delta.x())
            if "R" in d:
                nw = max(MIN_NODE_WIDTH, old_w + delta.x())
            if "T" in d:
                nh = max(MIN_NODE_HEIGHT, old_h - delta.y())
            if "B" in d:
                nh = max(MIN_NODE_HEIGHT, old_h + delta.y())
            gs = NODE_GRID_SIZE
            nw = max(MIN_NODE_WIDTH, ((int(nw) + gs // 2) // gs) * gs)
            nh = max(MIN_NODE_HEIGHT, ((int(nh) + gs // 2) // gs) * gs)
            if nw != self._width or nh != self._height:
                self.prepareGeometryChange()
                dx = self._width - nw if "L" in d else 0
                dy = self._height - nh if "T" in d else 0
                self._width = nw
                self._height = nh
                if dx != 0 or dy != 0:
                    self.setPos(self.pos() + QPointF(dx, dy))
                self.update()
                self.nodeResized.emit(self._node_id)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._resizing:
                self._resizing = False
                self._resize_dir = None
                self.setCursor(Qt.OpenHandCursor)
                event.accept()
                return
            self.setCursor(Qt.OpenHandCursor)
            scene = self.scene()
            if scene and hasattr(scene, 'snap_point') and getattr(scene, '_grid_snap', False):
                self.setPos(scene.snap_point(self.pos()))
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        attr, cell_rect = self._hit_param_cell(event.pos())
        if attr and self._is_editable_attr(attr):
            self._start_inline_edit(attr, cell_rect)
            event.accept()
            return
        self.nodeDoubleClicked.emit(self._node_id)
        super().mouseDoubleClickEvent(event)

    def _is_editable_attr(self, attr: str) -> bool:
        if attr in CALC_ONLY_ATTRS:
            return False
        ct = getattr(self._component, 'calc_type', self._comp_type) if self._component else self._comp_type
        if ct in ("switching", "ldo", "isolated") and attr == "iin":
            return False
        comp_attr = COMP_ATTR_MAP.get(attr)
        if comp_attr is None:
            return False
        if self._component is None:
            return False
        return hasattr(self._component, comp_attr[0])

    def _start_inline_edit(self, attr: str, cell_rect: QRectF):
        if self._edit_proxy is not None:
            self._close_inline_edit()

        self._edit_attr = attr
        self._edit_applied = False

        side = "in"
        for r, a, s in self._get_param_cell_rects():
            if a == attr:
                side = s
                break

        value_rect = self._get_value_rect_in_cell(cell_rect, side)
        current_val = self._read_param_value(attr)
        comp_attr = COMP_ATTR_MAP.get(attr, (attr, "", "{:.2f}"))
        unit = comp_attr[1]

        line_edit = QLineEdit()
        line_edit.setStyleSheet(
            "QLineEdit {"
            "  font-family: Consolas; font-size: 8pt; font-weight: bold;"
            "  color: #000000; background: #ffffff;"
            "  border: 1px solid #4a90d9; border-radius: 2px;"
            "  padding: 0px 2px;"
            "}"
        )
        line_edit.setFixedWidth(int(value_rect.width()))
        if unit == "%":
            line_edit.setText(f"{current_val:.1f}")
        elif unit == "A":
            line_edit.setText(f"{current_val:.4f}")
        else:
            line_edit.setText(f"{current_val:.2f}")
        line_edit.selectAll()

        self._edit_proxy = QGraphicsProxyWidget(self)
        self._edit_proxy.setWidget(line_edit)
        self._edit_proxy.setGeometry(value_rect)

        line_edit.setFocus()
        line_edit.returnPressed.connect(self._confirm_inline_edit)
        line_edit.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is not None and self._edit_proxy is not None and obj is self._edit_proxy.widget():
            if event.type() == event.Type.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self._close_inline_edit()
                    return True
                if event.key() in (Qt.Key_Tab, Qt.Key_Backtab):
                    self._confirm_inline_edit()
                    return True
            if event.type() == event.Type.FocusOut:
                self._confirm_inline_edit()
                return True
        return super().eventFilter(obj, event)

    def _confirm_inline_edit(self):
        if self._edit_proxy is None or self._edit_applied:
            return
        self._edit_applied = True

        line_edit = self._edit_proxy.widget()
        text = line_edit.text().strip()
        try:
            new_val = float(text)
            self._apply_param_edit(self._edit_attr, new_val)
        except ValueError:
            pass
        self._close_inline_edit()

    def _close_inline_edit(self):
        if self._edit_proxy is not None:
            widget = self._edit_proxy.widget()
            if widget is not None:
                widget.removeEventFilter(self)
            self._edit_proxy.deleteLater()
            self._edit_proxy = None
        self._edit_attr = None
        self._edit_applied = False

    def _apply_param_edit(self, attr: str, new_val: float):
        if attr in CALC_ONLY_ATTRS:
            return
        comp_attr = COMP_ATTR_MAP.get(attr)
        if comp_attr is None or self._component is None:
            return
        cname = comp_attr[0]
        if hasattr(self._component, cname):
            setattr(self._component, cname, new_val)
            self._calc_result = None
            self.paramEdited.emit(self._node_id, cname, new_val)
            self.update()

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        scene_pos = event.scenePos()
        menu = QMenu()
        edit_action = menu.addAction("编辑属性")
        menu.addSeparator()
        copy_action = menu.addAction("复制\tCtrl+C")
        paste_action = menu.addAction("粘贴\tCtrl+V")
        menu.addSeparator()
        delete_action = menu.addAction("删除\tDel")
        selected_action = menu.exec(event.screenPos())
        if selected_action == edit_action:
            self.nodeEditRequested.emit(self._node_id)
        elif selected_action == copy_action:
            self.nodeCopyRequested.emit(self._node_id)
        elif selected_action == paste_action:
            self.nodePasteRequested.emit(scene_pos)
        elif selected_action == delete_action:
            self.nodeDeleteRequested.emit(self._node_id)

    def is_near_input_port(self, scene_pos: QPointF) -> bool:
        for i in range(self._input_ports):
            port = self.input_port_pos(i)
            delta = scene_pos - port
            if (delta.x() ** 2 + delta.y() ** 2) < PORT_DETECT_RADIUS ** 2:
                return True
        return False

    def is_near_output_port(self, scene_pos: QPointF) -> bool:
        for i in range(self._output_ports):
            port = self.output_port_pos(i)
            delta = scene_pos - port
            if (delta.x() ** 2 + delta.y() ** 2) < PORT_DETECT_RADIUS ** 2:
                return True
        return False
