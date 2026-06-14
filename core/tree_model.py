import logging
from PySide6.QtCore import QObject, Signal
from typing import List, Optional
import uuid

from .component import Component

logger = logging.getLogger(__name__)


class TreeNode(QObject):
    componentChanged = Signal(object)

    def __init__(self, component: Component, parent=None):
        super().__init__(parent)
        self._id = str(uuid.uuid4())
        self._component = component
        self._parent_node: Optional["TreeNode"] = None
        self._children: List["TreeNode"] = []

    @property
    def node_id(self) -> str:
        return self._id

    @property
    def component(self) -> Component:
        return self._component

    @component.setter
    def component(self, value: Component):
        self._component = value
        self.componentChanged.emit(self)

    @property
    def parent_node(self) -> Optional["TreeNode"]:
        return self._parent_node

    @parent_node.setter
    def parent_node(self, node: Optional["TreeNode"]):
        self._parent_node = node

    @property
    def children(self) -> List["TreeNode"]:
        return self._children

    def add_child(self, child: "TreeNode"):
        if child not in self._children:
            self._children.append(child)
            child.parent_node = self

    def remove_child(self, child: "TreeNode"):
        if child in self._children:
            self._children.remove(child)
            child.parent_node = None

    def is_root(self) -> bool:
        return self._parent_node is None

    def is_leaf(self) -> bool:
        return len(self._children) == 0

    def find_descendant(self, node_id: str) -> Optional["TreeNode"]:
        if self._id == node_id:
            return self
        for child in self._children:
            result = child.find_descendant(node_id)
            if result:
                return result
        return None

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "component": self._component.to_dict(),
            "children": [child.to_dict() for child in self._children],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TreeNode":
        from .component import Component
        comp = Component.from_dict(d["component"])
        node = cls(comp)
        node._id = d["id"]
        for child_data in d.get("children", []):
            child = TreeNode.from_dict(child_data)
            node.add_child(child)
        return node


class TreeModel(QObject):
    calculationRequested = Signal()
    structureChanged = Signal()

    def __init__(self, library_manager=None, parent=None):
        super().__init__(parent)
        self._root_nodes: List[TreeNode] = []
        self._library = library_manager

    def set_library(self, library_manager):
        self._library = library_manager

    @property
    def library(self):
        return self._library

    def create_tree_node(self, component: Component) -> TreeNode:
        return TreeNode(component)

    @property
    def root_nodes(self) -> List[TreeNode]:
        return self._root_nodes

    def add_root_node(self, node: TreeNode):
        self._root_nodes.append(node)
        self.structureChanged.emit()

    def remove_node(self, node: TreeNode, emit_signal: bool = True):
        parent = node.parent_node
        if parent:
            parent.remove_child(node)
        else:
            if node in self._root_nodes:
                self._root_nodes.remove(node)
        for child in list(node.children):
            self.remove_node(child, emit_signal=False)
        node.deleteLater()
        if emit_signal:
            self.structureChanged.emit()

    def connect_node(self, parent_node: TreeNode, child_node: TreeNode) -> bool:
        if child_node is parent_node:
            return False
        if child_node.parent_node is not None:
            if child_node.parent_node == parent_node:
                return False
        cur = parent_node
        while cur:
            if cur is child_node:
                return False
            cur = cur.parent_node
        if child_node.parent_node is not None:
            child_node.parent_node.remove_child(child_node)
        if child_node in self._root_nodes:
            self._root_nodes.remove(child_node)
        parent_node.add_child(child_node)
        self.structureChanged.emit()
        self.calculationRequested.emit()
        return True

    def disconnect_node(self, node: TreeNode):
        parent = node.parent_node
        if parent:
            parent.remove_child(node)
            self._root_nodes.append(node)
            self.structureChanged.emit()
            self.calculationRequested.emit()

    def find_node_by_id(self, node_id: str) -> Optional[TreeNode]:
        for root in self._root_nodes:
            result = root.find_descendant(node_id)
            if result:
                return result
        return None

    def clear_all(self):
        for node in list(self._root_nodes):
            self.remove_node(node)

    def to_dict(self) -> dict:
        return {
            "roots": [root.to_dict() for root in self._root_nodes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TreeModel":
        model = cls()
        for root_data in d.get("roots", []):
            root = TreeNode.from_dict(root_data)
            model._root_nodes.append(root)
        return model

    @classmethod
    def load_roots(cls, tree_data: dict) -> List[TreeNode]:
        roots = []
        for root_data in tree_data.get("roots", []):
            root = TreeNode.from_dict(root_data)
            roots.append(root)
        logger.info("从字典加载了 %d 个根节点", len(roots))
        return roots
