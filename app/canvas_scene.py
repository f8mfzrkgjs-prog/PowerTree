from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QTimer
from PySide6.QtWidgets import QGraphicsScene, QMenu, QMessageBox, QDialog
from PySide6.QtGui import QCursor, QColor, QPen, QBrush, QPolygonF
from PySide6.QtGui import QUndoStack

from config import GridConfig, PortConfig, SceneConfig, Colors
from .node_item import NodeItem, PORT_RADIUS, DEFAULT_NODE_WIDTH, DEFAULT_NODE_HEIGHT
from .edge_item import EdgeItem, TempLineItem, snap_to_edge_grid, EDGE_GRID
from utils.astar import build_grid_map_from_scene, AStarRouter


class CanvasScene(QGraphicsScene):
    paramEdited = Signal()

    GRID_SIZE = GridConfig.GRID_SIZE
    GRID_MAJOR = GridConfig.GRID_MAJOR

    def __init__(self, tree_model, parent=None):
        super().__init__(parent)
        self._tree_model = tree_model
        self._undo_stack: QUndoStack | None = None
        self._node_items: dict[str, NodeItem] = {}
        self._edge_items: list[EdgeItem] = []
        self._connecting = False
        self._connect_source_node: NodeItem | None = None
        self._temp_line: TempLineItem | None = None
        self._routing = False
        self._route_source_node: NodeItem | None = None
        self._routing_reversed = False
        self._next_pos = QPointF(SceneConfig.INITIAL_POSITION_X, SceneConfig.INITIAL_POSITION_Y)
        self._clipboard: list[dict] = []
        self._grid_visible = True
        self._grid_snap = True
        self._grid_size = self.GRID_SIZE
        self._edge_update_timer = QTimer()
        self._edge_update_timer.setSingleShot(True)
        self._edge_update_timer.setInterval(30)
        self._edge_update_timer.timeout.connect(self._do_update_all_edges)
        self._branch_source_edge: EdgeItem | None = None
        self._branch_source_point: QPointF | None = None

        tree_model.structureChanged.connect(self._on_structure_changed)

    def set_undo_stack(self, stack: QUndoStack):
        self._undo_stack = stack

    @property
    def tree_model(self):
        return self._tree_model

    @property
    def next_pos(self):
        pos = self._next_pos
        self._next_pos += QPointF(SceneConfig.POSITION_OFFSET_X, SceneConfig.POSITION_OFFSET_Y)
        if self._next_pos.x() > SceneConfig.POSITION_MAX_X:
            self._next_pos.setX(SceneConfig.INITIAL_POSITION_X)
            self._next_pos.setY(self._next_pos.y() + 200)
        return pos

    def _get_template_visual(self, template_index: int):
        library = self._tree_model.library
        if library and 0 <= template_index < len(library.templates):
            tmpl = library.templates[template_index]
            return (
                tmpl.get("width", DEFAULT_NODE_WIDTH),
                tmpl.get("height", DEFAULT_NODE_HEIGHT),
                QColor(tmpl.get("color", "#C8C8C8")),
                tmpl.get("input_ports", 1),
                tmpl.get("output_ports", 1),
            )
        return (DEFAULT_NODE_WIDTH, DEFAULT_NODE_HEIGHT, QColor("#C8C8C8"), 1, 1)

    def create_node(self, template_index: int, name: str, comp_type: str, pos: QPointF = None,
                    node_width: int = None, node_height: int = None,
                    node_color: QColor = None,
                    input_ports: int = None, output_ports: int = None):
        component = self._tree_model.library.create_component_from_template(template_index, name)
        if component is None:
            return None
        node = self._tree_model.create_tree_node(component)
        self._tree_model.add_root_node(node)

        if node_width is None or node_height is None or node_color is None:
            w, h, c, inp, outp = self._get_template_visual(template_index)
            node_width = node_width or w
            node_height = node_height or h
            node_color = node_color or c
            input_ports = input_ports if input_ports is not None else inp
            output_ports = output_ports if output_ports is not None else outp

        node_item = NodeItem(node.node_id, component.comp_type, component.name,
                             node_width=node_width, node_height=node_height,
                             node_color=node_color,
                             input_ports=input_ports if input_ports is not None else 1,
                             output_ports=output_ports if output_ports is not None else 1)
        node_item.set_component(component)
        if pos is None:
            pos = self.next_pos
        pos = self.snap_point(pos)
        node_item.setPos(pos)
        self.addItem(node_item)
        self._node_items[node.node_id] = node_item
        self._connect_node_signals(node_item)
        if self._undo_stack is not None:
            from utils.undo_redo import AddNodeCommand
            cmd = AddNodeCommand(self, self._tree_model, node, pos)
            self._undo_stack.push(cmd)
        return node_item

    def create_node_from_template(self, template_index: int, pos: QPointF = None):
        library = self._tree_model.library
        if template_index < 0 or template_index >= len(library.templates):
            return None
        tmpl = library.templates[template_index]
        return self.create_node(template_index, tmpl["name"], tmpl.get("calc_type", "switching"), pos)

    def remove_node_item(self, node_id: str):
        node_item = self._node_items.pop(node_id, None)
        if node_item:
            self._remove_edges_for_node(node_id)
            try:
                node_item.nodeMoved.disconnect()
                node_item.nodeDoubleClicked.disconnect()
                node_item.nodeEditRequested.disconnect()
                node_item.nodeDeleteRequested.disconnect()
                node_item.nodeCopyRequested.disconnect()
                node_item.nodePasteRequested.disconnect()
                node_item.paramEdited.disconnect()
                node_item.nodeResized.disconnect()
            except RuntimeError:
                pass
            self.removeItem(node_item)
            node_item.deleteLater()

    def _remove_edges_for_node(self, node_id: str):
        for edge in list(self._edge_items):
            if edge.parent_id == node_id or edge.child_id == node_id:
                self._remove_edge_item(edge)

    def _remove_edge_item(self, edge: EdgeItem):
        if edge in self._edge_items:
            self._edge_items.remove(edge)
        self.removeItem(edge)
        edge.deleteLater()

    def find_node_item_by_id(self, node_id: str) -> NodeItem | None:
        return self._node_items.get(node_id)

    def is_input_port_occupied(self, node_id: str, port_index: int = 0) -> bool:
        """检查指定节点的输入端口是否已被连接。"""
        for edge in self._edge_items:
            if edge.child_id == node_id and edge.child_port == port_index:
                return True
        return False

    def get_edge_to_input_port(self, node_id: str, port_index: int = 0) -> EdgeItem | None:
        """获取连接到指定输入端口的连线。"""
        for edge in self._edge_items:
            if edge.child_id == node_id and edge.child_port == port_index:
                return edge
        return None

    def update_all_edges(self):
        for edge in self._edge_items:
            parent_item = self._node_items.get(edge.parent_id)
            child_item = self._node_items.get(edge.child_id)
            if parent_item and child_item:
                if edge.is_manual_route and len(edge.waypoints) >= 2:
                    waypoints = list(edge.waypoints)
                    new_start = parent_item.output_port_pos(edge.parent_port)
                    new_end = child_item.input_port_pos(edge.child_port)
                    waypoints[0] = new_start
                    waypoints[-1] = new_end
                    if len(waypoints) >= 3:
                        second = waypoints[1]
                        if abs(second.y() - new_start.y()) < abs(second.x() - new_start.x()):
                            waypoints[1] = QPointF(second.x(), new_start.y())
                        else:
                            waypoints[1] = QPointF(new_start.x(), second.y())
                    if len(waypoints) >= 4:
                        second_last = waypoints[-2]
                        if abs(second_last.y() - new_end.y()) < abs(second_last.x() - new_end.x()):
                            waypoints[-2] = QPointF(second_last.x(), new_end.y())
                        else:
                            waypoints[-2] = QPointF(new_end.x(), second_last.y())
                    edge.set_waypoints(waypoints)
                else:
                    edge.update_path(
                        parent_item.output_port_pos(edge.parent_port),
                        child_item.input_port_pos(edge.child_port)
                    )

    def find_node_at_scene_pos(self, scene_pos: QPointF) -> NodeItem | None:
        items = self.items(scene_pos, Qt.IntersectsItemShape, Qt.DescendingOrder)
        for item in items:
            if isinstance(item, NodeItem):
                return item
        return None

    def contextMenuEvent(self, event):
        scene_pos = event.scenePos()
        items = self.items(scene_pos)
        for item in items:
            if isinstance(item, NodeItem):
                super().contextMenuEvent(event)
                return
        menu = QMenu()
        paste_action = menu.addAction("粘贴\tCtrl+V")
        selected = menu.exec(event.screenPos())
        if selected == paste_action:
            self.paste_node(scene_pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            scene_pos = event.scenePos()
            node = self.find_node_at_scene_pos(scene_pos)
            modifiers = event.modifiers()

            if self._routing:
                if modifiers & Qt.ControlModifier:
                    self._cancel_routing()
                    event.accept()
                    return
                target_node, port_type, port_index = self._find_nearest_valid_port(scene_pos, node)
                if target_node and target_node is not self._route_source_node:
                    self._finish_routing(target_node, port_type, port_index)
                else:
                    self._temp_line.add_waypoint(scene_pos)
                event.accept()
                return

            if node:
                if node.is_near_output_port(scene_pos):
                    self._start_routing(node, scene_pos, reversed=False)
                    event.accept()
                    return
                if node.is_near_input_port(scene_pos) and node.input_ports > 0:
                    self._start_routing(node, scene_pos, reversed=True)
                    event.accept()
                    return

            # Ctrl+click on edge → branch routing
            if modifiers & Qt.ControlModifier:
                edge = self._find_edge_at_pos(scene_pos)
                if edge:
                    branch_point = edge.get_point_on_edge(scene_pos)
                    if branch_point:
                        self._start_branch_routing(edge, branch_point)
                    event.accept()
                    return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scene_pos = event.scenePos()
        self._update_port_hover(scene_pos)
        if self._routing and self._temp_line:
            self._temp_line.update_end(scene_pos)
            node = self.find_node_at_scene_pos(scene_pos)
            target, pt, pi = self._find_nearest_valid_port(scene_pos, node)
            self._temp_line.set_port_near(target is not None)
        super().mouseMoveEvent(event)

    def _update_port_hover(self, scene_pos: QPointF):
        """更新所有节点的端口悬停高亮状态。"""
        PORT_HOVER_DIST = PortConfig.PORT_HOVER_DISTANCE
        for node_item in self._node_items.values():
            hover_in = -1
            hover_out = -1
            for i in range(node_item.input_ports):
                port_pos = node_item.input_port_pos(i)
                d = (scene_pos - port_pos).manhattanLength()
                if d < PORT_HOVER_DIST:
                    hover_in = i
                    break
            for i in range(node_item.output_ports):
                port_pos = node_item.output_port_pos(i)
                d = (scene_pos - port_pos).manhattanLength()
                if d < PORT_HOVER_DIST:
                    hover_out = i
                    break
            if hover_in >= 0:
                node_item.set_hover_port('in', hover_in)
            elif hover_out >= 0:
                node_item.set_hover_port('out', hover_out)
            else:
                node_item.set_hover_port(None)

    def mouseReleaseEvent(self, event):
        if self._routing:
            scene_pos = event.scenePos()
            node = self.find_node_at_scene_pos(scene_pos)
            target, pt, pi = self._find_nearest_valid_port(scene_pos, node)
            if target and target is not self._route_source_node:
                self._finish_routing(target, pt, pi)
            else:
                self._cancel_routing()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _find_nearest_valid_port(self, scene_pos: QPointF, node) -> tuple:
        """查找范围内最近的合法端口，返回 (node, port_type, port_index)。
        已被占用的输入端口会被跳过。
        """
        PORT_SNAP = PortConfig.PORT_SNAP_DISTANCE
        best_dist = PORT_SNAP
        best_node = None
        best_type = None
        best_index = 0
        if node and node is not self._route_source_node:
            if not self._routing_reversed and node.is_near_input_port(scene_pos):
                for i in range(node.input_ports):
                    if self.is_input_port_occupied(node.node_id, i):
                        continue
                    d = (scene_pos - node.input_port_pos(i)).manhattanLength()
                    if d < best_dist:
                        best_dist = d
                        best_node = node
                        best_type = "in"
                        best_index = i
            if self._routing_reversed and node.is_near_output_port(scene_pos):
                for i in range(node.output_ports):
                    d = (scene_pos - node.output_port_pos(i)).manhattanLength()
                    if d < best_dist:
                        best_dist = d
                        best_node = node
                        best_type = "out"
                        best_index = i
        return best_node, best_type, best_index

    def _find_edge_at_pos(self, scene_pos: QPointF):
        for edge in self._edge_items:
            if edge.contains(scene_pos):
                return edge
        return None

    def copy_selected_nodes(self):
        selected: list[tuple[QPointF, NodeItem, object]] = []
        for node_item in self._node_items.values():
            if node_item.isSelected():
                node = self._tree_model.find_node_by_id(node_item.node_id)
                if node:
                    selected.append((node_item.pos(), node_item, node))
        if not selected:
            return
        self._clipboard.clear()
        ref_pos = selected[0][0]
        selected_ids = {item[2].node_id for item in selected}
        id_to_idx = {item[2].node_id: i for i, item in enumerate(selected)}

        clipboard_nodes = []
        clipboard_edges = []
        for pos, node_item, node in selected:
            clipboard_nodes.append({
                "component_dict": node.component.to_dict(),
                "width": node_item.node_width,
                "height": node_item.node_height,
                "color": node_item._color.name(),
                "input_ports": node_item.input_ports,
                "output_ports": node_item.output_ports,
                "offset_x": pos.x() - ref_pos.x(),
                "offset_y": pos.y() - ref_pos.y(),
            })
            for child in node.children:
                if child.node_id in selected_ids:
                    clipboard_edges.append({
                        "from_idx": id_to_idx[node.node_id],
                        "to_idx": id_to_idx[child.node_id],
                    })
        self._clipboard = {"nodes": clipboard_nodes, "edges": clipboard_edges}

    def paste_node(self, scene_pos: QPointF = None):
        if not self._clipboard or not self._clipboard.get("nodes"):
            return
        if scene_pos is None:
            views = self.views()
            if views:
                vp = views[0].viewport().mapFromGlobal(QCursor.pos())
                scene_pos = views[0].mapToScene(vp)
            else:
                scene_pos = QPointF(200, 150)
        scene_pos = self.snap_point(scene_pos)
        new_ids = []
        for data in self._clipboard["nodes"]:
            cd = data["component_dict"]
            comp_type = cd.get("comp_type", "load")
            comp_name = cd.get("name", "") + "_副本"
            from core.component import PowerModule, Load
            if comp_type == "load":
                component = Load.from_dict(cd)
            else:
                component = PowerModule.from_dict(cd)
            component.name = comp_name
            node = self._tree_model.create_tree_node(component)
            self._tree_model.add_root_node(node)
            node_color = QColor(data.get("color", "#C8C8C8"))
            node_item = NodeItem(node.node_id, comp_type, comp_name,
                                 node_width=data.get("width", DEFAULT_NODE_WIDTH),
                                 node_height=data.get("height", DEFAULT_NODE_HEIGHT),
                                 node_color=node_color,
                                 input_ports=data.get("input_ports", 1),
                                 output_ports=data.get("output_ports", 1))
            node_item.set_component(component)
            rx = scene_pos.x() + data.get("offset_x", 0)
            ry = scene_pos.y() + data.get("offset_y", 0)
            pos = self.snap_point(QPointF(rx, ry))
            node_item.setPos(pos)
            self.addItem(node_item)
            self._node_items[node.node_id] = node_item
            self._connect_node_signals(node_item)
            new_ids.append(node.node_id)
        for edge_data in self._clipboard.get("edges", []):
            pid = new_ids[edge_data["from_idx"]]
            cid = new_ids[edge_data["to_idx"]]
            parent_node = self._tree_model.find_node_by_id(pid)
            child_node = self._tree_model.find_node_by_id(cid)
            if parent_node and child_node:
                self._tree_model.connect_node(parent_node, child_node)
                self._create_edge(pid, cid)

    def keyPressEvent(self, event):
        if self._routing:
            if event.key() == Qt.Key_Escape:
                self._cancel_routing()
                event.accept()
                return
            if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                if self._temp_line:
                    self._temp_line.remove_last_waypoint()
                event.accept()
                return
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self._cancel_routing()
                event.accept()
                return
            super().keyPressEvent(event)
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for edge in list(self._edge_items):
                if edge.isSelected():
                    self.delete_edge_item(edge)
            for node_id, node_item in list(self._node_items.items()):
                if node_item.isSelected():
                    self._on_node_delete_requested(node_id)
            event.accept()
            return
        super().keyPressEvent(event)

    def _try_connect(self, parent_item: NodeItem, child_item: NodeItem, waypoints: list = None,
                     parent_port: int = 0, child_port: int = 0, is_manual: bool = False):
        parent_node = self._tree_model.find_node_by_id(parent_item.node_id)
        child_node = self._tree_model.find_node_by_id(child_item.node_id)
        if parent_node and child_node:
            if self._undo_stack is not None:
                from utils.undo_redo import ConnectNodeCommand
                cmd = ConnectNodeCommand(self, self._tree_model, parent_item.node_id, child_item.node_id, waypoints, parent_port, child_port, is_manual)
                self._undo_stack.push(cmd)
            else:
                if self._tree_model.connect_node(parent_node, child_node):
                    self._create_routed_edge(parent_item.node_id, child_item.node_id, waypoints, parent_port, child_port, is_manual)

    def _create_edge(self, parent_id: str, child_id: str, parent_port: int = 0, child_port: int = 0):
        self._create_routed_edge(parent_id, child_id, None, parent_port, child_port)

    def _create_routed_edge(self, parent_id: str, child_id: str, waypoints: list = None,
                            parent_port: int = 0, child_port: int = 0, is_manual: bool = False):
        for edge in self._edge_items:
            if edge.parent_id == parent_id and edge.child_id == child_id:
                return
        parent_item = self._node_items.get(parent_id)
        child_item = self._node_items.get(child_id)
        if not parent_item or not child_item:
            return
        edge = EdgeItem(parent_id, child_id, parent_port=parent_port, child_port=child_port)
        edge.set_manual_route(is_manual)
        if waypoints:
            edge.set_waypoints(waypoints)
        else:
            edge.update_path(parent_item.output_port_pos(parent_port), child_item.input_port_pos(child_port))
        self.addItem(edge)
        self._edge_items.append(edge)

    def _start_routing(self, source_node, scene_pos: QPointF, reversed: bool = False):
        self._routing = True
        self._routing_reversed = reversed
        self._route_source_node = source_node
        if reversed:
            start = source_node.input_port_pos()
        else:
            start = source_node.output_port_pos()
        end = snap_to_edge_grid(QPointF(scene_pos.x(), start.y()))
        self._temp_line = TempLineItem([start, end])
        self.addItem(self._temp_line)

    def _finish_routing(self, target_node, port_type: str = None, port_index: int = 0):
        self._routing = False
        waypoints = []
        has_manual_waypoints = False
        if self._temp_line:
            waypoints = list(self._temp_line.waypoints)
            has_manual_waypoints = self._temp_line.has_manual_waypoints
            self.removeItem(self._temp_line)
            self._temp_line = None

        if not self._route_source_node or target_node is self._route_source_node:
            self._route_source_node = None
            self._routing_reversed = False
            self._branch_source_edge = None
            self._branch_source_point = None
            return

        if self._routing_reversed:
            parent_node = target_node
            child_node = self._route_source_node
            parent_port = port_index
            child_port = 0
        else:
            parent_node = self._route_source_node
            child_node = target_node
            parent_port = 0
            child_port = port_index

        if not parent_node or not child_node:
            self._route_source_node = None
            self._routing_reversed = False
            self._branch_source_edge = None
            self._branch_source_point = None
            return

        is_branch = self._branch_source_point is not None

        if is_branch:
            start_pt = parent_node.output_port_pos(parent_port)
            end_pt = child_node.input_port_pos(child_port)
            gm = build_grid_map_from_scene(self._node_items, EDGE_GRID,
                                           exclude_ids=[parent_node.node_id, child_node.node_id])
            astar_path = AStarRouter.find_path(gm, start_pt, end_pt)
            if astar_path:
                waypoints = astar_path
            else:
                waypoints = build_ortho_path(
                    snap_to_edge_grid(start_pt),
                    snap_to_edge_grid(end_pt))
            self._try_connect(parent_node, child_node, waypoints, parent_port, child_port, False)
        elif has_manual_waypoints:
            waypoints[-1] = child_node.input_port_pos(child_port) if not self._routing_reversed else parent_node.output_port_pos(parent_port)
            self._try_connect(parent_node, child_node, waypoints, parent_port, child_port, True)
        else:
            if len(waypoints) >= 2:
                start_pt = waypoints[0]
                end_pt = child_node.input_port_pos(child_port) if not self._routing_reversed else parent_node.output_port_pos(parent_port)
                gm = build_grid_map_from_scene(self._node_items, EDGE_GRID,
                                               exclude_ids=[parent_node.node_id, child_node.node_id])
                astar_path = AStarRouter.find_path(gm, start_pt, end_pt)
                if astar_path:
                    waypoints = astar_path
                else:
                    waypoints[-1] = end_pt
            self._try_connect(parent_node, child_node, waypoints, parent_port, child_port, False)

        self._route_source_node = None
        self._routing_reversed = False
        self._branch_source_edge = None
        self._branch_source_point = None

    def _cancel_routing(self):
        self._routing = False
        self._routing_reversed = False
        if self._temp_line:
            self.removeItem(self._temp_line)
            self._temp_line = None
        self._route_source_node = None

    def _start_branch_routing(self, edge: EdgeItem, branch_point: QPointF):
        """从连线上的某点开始分支连线。"""
        self._routing = True
        self._routing_reversed = False
        self._branch_source_edge = edge
        self._branch_source_point = branch_point
        parent_item = self._node_items.get(edge.parent_id)
        if parent_item:
            self._route_source_node = parent_item
        else:
            self._cancel_routing()
            return
        self._temp_line = TempLineItem([branch_point, branch_point])
        self.addItem(self._temp_line)

    def delete_edge_item(self, edge: EdgeItem):
        if self._undo_stack is not None:
            from utils.undo_redo import DisconnectNodeCommand
            cmd = DisconnectNodeCommand(self, self._tree_model, edge.parent_id, edge.child_id)
            self._undo_stack.push(cmd)
        else:
            child_node = self._tree_model.find_node_by_id(edge.child_id)
            if child_node:
                self._tree_model.disconnect_node(child_node)
            self._remove_edge_item(edge)

    def delete_edge_by_nodes(self, parent_id: str, child_id: str):
        for edge in list(self._edge_items):
            if edge.parent_id == parent_id and edge.child_id == child_id:
                self._remove_edge_item(edge)

    def _connect_node_signals(self, node_item: NodeItem):
        node_item.nodeMoved.connect(self._on_node_moved)
        node_item.nodeDoubleClicked.connect(self._on_node_double_clicked)
        node_item.nodeEditRequested.connect(self._on_node_edit_requested)
        node_item.nodeDeleteRequested.connect(self._on_node_delete_requested)
        node_item.nodeCopyRequested.connect(self._on_node_copy_requested)
        node_item.nodePasteRequested.connect(self._on_node_paste_requested)
        node_item.paramEdited.connect(self._on_param_edited)
        node_item.nodeResized.connect(self._on_node_resized)

    def _on_node_moved(self, node_id: str):
        self._edge_update_timer.start()

    def _do_update_all_edges(self):
        self.update_all_edges()

    def _on_node_double_clicked(self, node_id: str):
        node = self._tree_model.find_node_by_id(node_id)
        node_item = self._node_items.get(node_id)
        if node and node_item:
            from .property_dialog import PropertyDialog
            dlg = PropertyDialog(node.component, self.views()[0] if self.views() else None)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                node.component = dlg.component
                node_item.node_name = node.component.name
                node_item.comp_type = node.component.comp_type
                node_item.set_component(dlg.component)
                node_item.set_calc_result(None)
                node_item.update()

    def _on_node_edit_requested(self, node_id: str):
        self._on_node_double_clicked(node_id)

    def _on_node_copy_requested(self, node_id: str):
        node_item = self._node_items.get(node_id)
        if node_item:
            node_item.setSelected(True)
        self.copy_selected_nodes()

    def _on_node_paste_requested(self, scene_pos: QPointF):
        self.paste_node(scene_pos)

    def _on_node_delete_requested(self, node_id: str):
        node = self._tree_model.find_node_by_id(node_id)
        if node and not node.is_leaf():
            reply = QMessageBox.question(
                None, "确认删除",
                f"节点「{node.component.name}」包含 {len(node.children)} 个子节点，\n"
                f"确定要删除整棵子树吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        if self._undo_stack is not None:
            from utils.undo_redo import DeleteNodeCommand
            cmd = DeleteNodeCommand(self, self._tree_model, node_id)
            self._undo_stack.push(cmd)
        else:
            self._remove_edges_for_node(node_id)
            if node:
                self._tree_model.remove_node(node)
            self.remove_node_item(node_id)

    def _on_param_edited(self, node_id: str, attr_name: str, new_value):
        self.paramEdited.emit()
        self.update_all_edges()

    def _on_node_resized(self, node_id: str):
        self.update_all_edges()

    def _on_structure_changed(self):
        pass

    def get_node_positions(self) -> dict:
        positions = {}
        for node_id, item in self._node_items.items():
            positions[node_id] = {
                "x": item.pos().x(),
                "y": item.pos().y(),
                "width": item.node_width,
                "height": item.node_height,
                "color": item._color.name(),
                "input_ports": item._input_ports,
                "output_ports": item._output_ports,
            }
        return positions

    def restore_node_positions(self, positions: dict):
        for node_id, pos in positions.items():
            item = self._node_items.get(node_id)
            if item:
                item.setPos(QPointF(pos["x"], pos["y"]))

    def clear_scene(self):
        for edge in list(self._edge_items):
            self._remove_edge_item(edge)
        for node_id in list(self._node_items.keys()):
            self.remove_node_item(node_id)
        self._node_items.clear()
        self._edge_items.clear()
        self._next_pos = QPointF(50, 50)

    @property
    def grid_visible(self) -> bool:
        return self._grid_visible

    @property
    def grid_snap(self) -> bool:
        return self._grid_snap

    @property
    def grid_size(self) -> int:
        return self._grid_size

    def set_grid_visible(self, visible: bool):
        self._grid_visible = visible
        self.update()

    def set_grid_snap(self, snap: bool):
        self._grid_snap = snap

    def set_grid_size(self, size: int):
        self._grid_size = max(5, min(200, size))
        self.update()

    def snap_point(self, point: QPointF) -> QPointF:
        if not self._grid_snap:
            return point
        gs = self._grid_size
        return QPointF(round(point.x() / gs) * gs, round(point.y() / gs) * gs)

    def drawBackground(self, painter, rect: QRectF):
        super().drawBackground(painter, rect)
        if not self._grid_visible:
            return

        gs = self._grid_size
        gm = self.GRID_MAJOR

        left = int(rect.left() // gs * gs) - gs
        top = int(rect.top() // gs * gs) - gs
        right = int(rect.right()) + gs
        bottom = int(rect.bottom()) + gs

        major_color = QColor(160, 160, 160)
        minor_color = QColor(200, 200, 200)

        for x in range(left, right + gs, gs):
            for y in range(top, bottom + gs, gs):
                is_major = (x // gs) % gm == 0 and (y // gs) % gm == 0
                if is_major:
                    painter.setPen(QPen(major_color, 1))
                    painter.drawPoint(QPointF(x, y))
                    painter.drawPoint(QPointF(x - 1, y))
                    painter.drawPoint(QPointF(x + 1, y))
                    painter.drawPoint(QPointF(x, y - 1))
                    painter.drawPoint(QPointF(x, y + 1))
                else:
                    painter.setPen(QPen(minor_color, 1))
                    painter.drawPoint(QPointF(x, y))
