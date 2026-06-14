import math
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainterPath, QPainter, QPen, QColor, QBrush, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsPathItem, QMenu, QGraphicsSceneContextMenuEvent,
    QStyleOptionGraphicsItem, QWidget
)

from config import GridConfig, EdgeConfig, Colors

from .node_item import PORT_RADIUS

EDGE_GRID = GridConfig.EDGE_GRID


def _point_segment_distance(p: QPointF, a: QPointF, b: QPointF) -> float:
    """计算点到线段的最短距离（欧几里得距离）。"""
    ab = b - a
    ap = p - a
    ab_len_sq = ab.x() ** 2 + ab.y() ** 2
    if ab_len_sq < 1e-9:
        return math.sqrt(ap.x() ** 2 + ap.y() ** 2)
    t = max(0, min(1, (ap.x() * ab.x() + ap.y() * ab.y()) / ab_len_sq))
    closest = QPointF(a.x() + t * ab.x(), a.y() + t * ab.y())
    dx = p.x() - closest.x()
    dy = p.y() - closest.y()
    return math.sqrt(dx * dx + dy * dy)


def snap_to_edge_grid(point: QPointF) -> QPointF:
    gs = EDGE_GRID
    return QPointF(int(point.x() / gs + 0.5) * gs, int(point.y() / gs + 0.5) * gs)


def build_ortho_path(source: QPointF, dest: QPointF) -> list:
    """Compute orthogonal waypoints from source to dest."""
    pts = [source]
    sx, sy = source.x(), source.y()
    dx, dy = dest.x(), dest.y()

    if abs(dx - sx) < 5:
        # Nearly vertical
        pts.append(QPointF(sx + 20, sy))
        pts.append(QPointF(sx + 20, dy))
    else:
        mid_x = (sx + dx) / 2
        mid_x = int(mid_x / EDGE_GRID + 0.5) * EDGE_GRID
        pts.append(QPointF(mid_x, sy))
        pts.append(QPointF(mid_x, dy))

    pts.append(dest)
    return pts


class EdgeItem(QGraphicsPathItem):
    def __init__(self, parent_id: str, child_id: str, parent=None, waypoints: list = None,
                 parent_port: int = 0, child_port: int = 0):
        super().__init__(parent)
        self._parent_id = parent_id
        self._child_id = child_id
        self._parent_port = parent_port
        self._child_port = child_port
        self._source_point = QPointF()
        self._dest_point = QPointF()
        self._waypoints = waypoints or []
        self._is_manual_route = False
        self.setFlag(QGraphicsPathItem.ItemIsSelectable)
        self.setFlag(QGraphicsPathItem.ItemSendsGeometryChanges)
        self._color = QColor(60, 60, 60)
        self.setPen(QPen(self._color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setBrush(QBrush(Qt.NoBrush))
        self.setZValue(-1)
        self.setAcceptHoverEvents(True)
        self._dragging_waypoint = -1
        self._drag_start_pos = QPointF()

    @property
    def parent_id(self) -> str:
        return self._parent_id

    @property
    def child_id(self) -> str:
        return self._child_id

    @property
    def parent_port(self) -> int:
        return self._parent_port

    @property
    def child_port(self) -> int:
        return self._child_port

    @property
    def waypoints(self) -> list:
        return self._waypoints

    @property
    def is_manual_route(self) -> bool:
        return self._is_manual_route

    def set_manual_route(self, manual: bool):
        self._is_manual_route = manual

    def contains(self, point: QPointF) -> bool:
        if len(self._waypoints) < 2:
            return False
        for i in range(len(self._waypoints) - 1):
            a = self._waypoints[i]
            b = self._waypoints[i + 1]
            dist = _point_segment_distance(point, a, b)
            if dist < EdgeConfig.EDGE_MARGIN:
                return True
        return False

    def update_path(self, source_scene: QPointF, dest_scene: QPointF):
        self._source_point = source_scene
        self._dest_point = dest_scene
        self._waypoints = build_ortho_path(
            snap_to_edge_grid(source_scene),
            snap_to_edge_grid(dest_scene))
        self._build_path()

    def set_waypoints(self, waypoints: list):
        self._waypoints = [snap_to_edge_grid(p) for p in waypoints]
        if self._waypoints:
            self._source_point = self._waypoints[0]
            self._dest_point = self._waypoints[-1]
        self._build_path()

    def _build_path(self):
        path = QPainterPath()
        if len(self._waypoints) < 2:
            return
        path.moveTo(self._waypoints[0])
        for pt in self._waypoints[1:]:
            path.lineTo(pt)
        self.setPath(path)

    def boundingRect(self):
        r = self.path().boundingRect()
        if r.isEmpty():
            return r
        return r.adjusted(-12, -12, 12, 12)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        if self.isSelected():
            painter.setPen(QPen(QColor(0, 120, 215), 3))
        else:
            painter.setPen(QPen(self._color, 2))
        painter.setBrush(QBrush(Qt.NoBrush))
        painter.drawPath(self.path())
        if self.isSelected() and len(self._waypoints) >= 3:
            painter.setPen(QPen(QColor(0, 120, 215, 120), 1))
            painter.setBrush(QBrush(QColor(0, 120, 215)))
            for pt in self._waypoints[1:-1]:
                painter.drawEllipse(pt, EdgeConfig.WAYPOINT_RADIUS, EdgeConfig.WAYPOINT_RADIUS)
        self._draw_arrow(painter)

    def _draw_arrow(self, painter: QPainter):
        """在连线终点附近绘制方向箭头。"""
        if len(self._waypoints) < 2:
            return
        arrow_size = EdgeConfig.ARROW_SIZE
        end_pt = self._waypoints[-1]
        prev_pt = self._waypoints[-2]
        dx = end_pt.x() - prev_pt.x()
        dy = end_pt.y() - prev_pt.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-6:
            return
        dx /= length
        dy /= length
        arrow_base = QPointF(end_pt.x() - dx * arrow_size, end_pt.y() - dy * arrow_size)
        perp_x = -dy * arrow_size * 0.5
        perp_y = dx * arrow_size * 0.5
        p1 = QPointF(arrow_base.x() + perp_x, arrow_base.y() + perp_y)
        p2 = QPointF(arrow_base.x() - perp_x, arrow_base.y() - perp_y)
        arrow_color = QColor(0, 120, 215) if self.isSelected() else self._color
        painter.setPen(QPen(arrow_color, 1))
        painter.setBrush(QBrush(arrow_color))
        triangle = QPolygonF([end_pt, p1, p2])
        painter.drawPolygon(triangle)

    def _hit_waypoint(self, pos: QPointF) -> int:
        """检测点击位置是否在途经点上，返回途经点索引或-1。"""
        if len(self._waypoints) < 3:
            return -1
        for i, pt in enumerate(self._waypoints[1:-1], 1):
            if (pos - pt).manhattanLength() < EdgeConfig.WAYPOINT_HIT_DISTANCE:
                return i
        return -1

    def get_point_on_edge(self, scene_pos: QPointF) -> QPointF | None:
        """获取连线上的最近格点位置（用于分支连线）。"""
        if len(self._waypoints) < 2:
            return None
        best_point = None
        best_dist = float('inf')
        for i in range(len(self._waypoints) - 1):
            a = self._waypoints[i]
            b = self._waypoints[i + 1]
            projected = self._project_point_on_segment(scene_pos, a, b)
            dist = (scene_pos - projected).manhattanLength()
            if dist < best_dist:
                best_dist = dist
                best_point = snap_to_edge_grid(projected)
        if best_dist < EdgeConfig.ENDPOINT_HIT_DISTANCE + 5:
            return best_point
        return None

    def _project_point_on_segment(self, p: QPointF, a: QPointF, b: QPointF) -> QPointF:
        """将点投影到线段上。"""
        ab = b - a
        ap = p - a
        ab_len_sq = ab.x() ** 2 + ab.y() ** 2
        if ab_len_sq < 1e-9:
            return a
        t = max(0, min(1, (ap.x() * ab.x() + ap.y() * ab.y()) / ab_len_sq))
        return QPointF(a.x() + t * ab.x(), a.y() + t * ab.y())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSelected():
            wp_idx = self._hit_waypoint(event.pos())
            if wp_idx >= 0:
                self._dragging_waypoint = wp_idx
                self._drag_start_pos = event.pos()
                self.set_manual_route(True)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging_waypoint >= 0:
            new_pos = snap_to_edge_grid(event.pos())
            self._waypoints[self._dragging_waypoint] = new_pos
            self._build_path()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging_waypoint >= 0:
            self._dragging_waypoint = -1
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        menu = QMenu()
        delete_action = menu.addAction("删除连线")
        selected_action = menu.exec(event.screenPos())
        if selected_action == delete_action:
            scene = self.scene()
            if scene and hasattr(scene, 'delete_edge_item'):
                scene.delete_edge_item(self)


class TempLineItem(QGraphicsPathItem):
    def __init__(self, waypoints: list, parent=None):
        super().__init__(parent)
        self._start = waypoints[0]
        self._fixed: list = []  # 用户点击锁定的途经点
        self._cursor = waypoints[-1]
        self._port_near = False
        self.setPen(QPen(QColor(0, 120, 215, 180), 2, Qt.DashLine))
        self.setBrush(QBrush(Qt.NoBrush))
        self.setZValue(100)
        self._rebuild()

    @property
    def waypoints(self) -> list:
        pts = [self._start] + self._fixed
        if self._cursor:
            last = self._fixed[-1] if self._fixed else self._start
            seg = build_ortho_path(last, self._cursor)
            pts.extend(seg[1:])
        return pts

    @property
    def has_manual_waypoints(self) -> bool:
        """用户是否主动添加了途经点。"""
        return len(self._fixed) > 0

    def set_port_near(self, near: bool):
        if near != self._port_near:
            self._port_near = near
            if near:
                self.setPen(QPen(QColor(0, 200, 80, 220), 2.5, Qt.DashLine))
            else:
                self.setPen(QPen(QColor(0, 120, 215, 180), 2, Qt.DashLine))

    def update_end(self, cursor_pos: QPointF):
        self._cursor = cursor_pos
        self._rebuild()

    def add_waypoint(self, pt: QPointF):
        last = self._fixed[-1] if self._fixed else self._start
        seg = build_ortho_path(last, pt)
        for p in seg[1:]:
            self._fixed.append(snap_to_edge_grid(p))
        self._cursor = pt
        self._rebuild()

    def remove_last_waypoint(self):
        if len(self._fixed) >= 1:
            self._fixed.pop()
            self._rebuild()
            return True
        return False

    def _rebuild(self):
        pts = self.waypoints
        path = QPainterPath()
        if len(pts) >= 2:
            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
        self.setPath(path)
