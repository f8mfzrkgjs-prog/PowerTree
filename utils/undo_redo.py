import logging
from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QPointF

from core.tree_model import TreeNode

logger = logging.getLogger(__name__)


class AddNodeCommand(QUndoCommand):
    def __init__(self, scene, tree_model, node, pos: QPointF):
        super().__init__("添加节点")
        self._scene = scene
        self._tree_model = tree_model
        self._node = node
        self._pos = pos
        self._added_to_scene = False

    def undo(self):
        if self._node.node_id in self._scene._node_items:
            self._scene.remove_node_item(self._node.node_id)
        if self._node in self._tree_model.root_nodes:
            self._tree_model._root_nodes.remove(self._node)

    def redo(self):
        if self._node not in self._tree_model.root_nodes:
            self._tree_model.add_root_node(self._node)
        if self._node.node_id not in self._scene._node_items:
            from app.node_item import NodeItem
            comp = self._node.component
            item = NodeItem(self._node.node_id, comp.comp_type, comp.name)
            item.set_component(comp)
            item.setPos(self._pos)
            self._scene.addItem(item)
            self._scene._node_items[self._node.node_id] = item
            self._scene._connect_node_signals(item)


class DeleteNodeCommand(QUndoCommand):
    def __init__(self, scene, tree_model, node_id: str):
        super().__init__("删除节点")
        self._scene = scene
        self._tree_model = tree_model
        self._node_id = node_id
        self._saved_data = None
        self._descendant_ids = []
        self._all_ids = []
        node = tree_model.find_node_by_id(node_id)
        if node:
            self._saved_data = node.to_dict()
            self._descendant_ids = [d.node_id for d in _collect_all_descendants(node)]
            self._all_ids = [node_id] + self._descendant_ids
        self._visual_data = {}
        for nid in self._all_ids:
            item = scene.find_node_item_by_id(nid)
            if item:
                self._visual_data[nid] = {
                    "pos": item.pos(),
                    "width": item.node_width,
                    "height": item.node_height,
                    "color": item._color.name(),
                    "input_ports": item.input_ports,
                    "output_ports": item.output_ports,
                }
        self._edge_data = []
        seen = set()
        for edge in list(scene._edge_items):
            if edge.parent_id in self._all_ids or edge.child_id in self._all_ids:
                key = (edge.parent_id, edge.child_id)
                if key not in seen:
                    seen.add(key)
                    self._edge_data.append(key)

    def undo(self):
        if self._saved_data is None:
            return
        from app.node_item import NodeItem
        from PySide6.QtGui import QColor
        root = TreeNode.from_dict(self._saved_data)
        self._tree_model.add_root_node(root)

        def restore_node(node):
            vd = self._visual_data.get(node.node_id, {})
            nc = QColor(vd.get("color", "#C8C8C8"))
            item = NodeItem(node.node_id, node.component.comp_type, node.component.name,
                            node_width=vd.get("width"), node_height=vd.get("height"),
                            node_color=nc,
                            input_ports=vd.get("input_ports", 1),
                            output_ports=vd.get("output_ports", 1))
            item.set_component(node.component)
            item.setPos(vd.get("pos", QPointF(50, 50)))
            self._scene.addItem(item)
            self._scene._node_items[node.node_id] = item
            self._scene._connect_node_signals(item)
            for child in node.children:
                restore_node(child)

        restore_node(root)

        for pid, cid in self._edge_data:
            if pid in self._scene._node_items and cid in self._scene._node_items:
                self._scene._create_edge(pid, cid)
        self._scene.update_all_edges()

    def redo(self):
        for nid in reversed(self._all_ids):
            self._scene._remove_edges_for_node(nid)
        for nid in self._descendant_ids:
            self._scene.remove_node_item(nid)
        node = self._tree_model.find_node_by_id(self._node_id)
        if node:
            self._tree_model.remove_node(node)
        self._scene.remove_node_item(self._node_id)


class ConnectNodeCommand(QUndoCommand):
    def __init__(self, scene, tree_model, parent_id: str, child_id: str, waypoints: list = None,
                 parent_port: int = 0, child_port: int = 0, is_manual: bool = False):
        super().__init__("连接节点")
        self._scene = scene
        self._tree_model = tree_model
        self._parent_id = parent_id
        self._child_id = child_id
        self._waypoints = waypoints
        self._parent_port = parent_port
        self._child_port = child_port
        self._is_manual = is_manual

    def undo(self):
        child = self._tree_model.find_node_by_id(self._child_id)
        if child:
            self._tree_model.disconnect_node(child)
        self._scene.delete_edge_by_nodes(self._parent_id, self._child_id)

    def redo(self):
        parent = self._tree_model.find_node_by_id(self._parent_id)
        child = self._tree_model.find_node_by_id(self._child_id)
        if parent and child:
            if self._tree_model.connect_node(parent, child):
                self._scene._create_routed_edge(self._parent_id, self._child_id, self._waypoints,
                                                self._parent_port, self._child_port, self._is_manual)


class DisconnectNodeCommand(QUndoCommand):
    def __init__(self, scene, tree_model, parent_id: str, child_id: str):
        super().__init__("断开连线")
        self._scene = scene
        self._tree_model = tree_model
        self._parent_id = parent_id
        self._child_id = child_id
        self._saved_waypoints = None
        self._parent_port = 0
        self._child_port = 0
        self._is_manual = False
        for edge in scene._edge_items:
            if edge.parent_id == parent_id and edge.child_id == child_id:
                self._saved_waypoints = list(edge.waypoints) if edge.waypoints else None
                self._parent_port = edge.parent_port
                self._child_port = edge.child_port
                self._is_manual = edge.is_manual_route
                break

    def undo(self):
        parent = self._tree_model.find_node_by_id(self._parent_id)
        child = self._tree_model.find_node_by_id(self._child_id)
        if parent and child:
            if self._tree_model.connect_node(parent, child):
                self._scene._create_routed_edge(self._parent_id, self._child_id, self._saved_waypoints,
                                                self._parent_port, self._child_port, self._is_manual)

    def redo(self):
        child = self._tree_model.find_node_by_id(self._child_id)
        if child:
            self._tree_model.disconnect_node(child)
        self._scene.delete_edge_by_nodes(self._parent_id, self._child_id)


def _collect_all_descendants(node) -> list:
    result = []
    for child in node.children:
        result.append(child)
        result.extend(_collect_all_descendants(child))
    return result
