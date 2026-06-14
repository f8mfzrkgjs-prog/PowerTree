from PySide6.QtCore import Qt, QPointF
from PySide6.QtWidgets import QGraphicsView
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QKeyEvent, QCursor


class CanvasView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setAcceptDrops(True)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self._canvas_scene = scene
        self.viewport().setMouseTracking(True)
        scene.setSceneRect(-2000, -2000, 4000, 4000)

    def showEvent(self, event):
        super().showEvent(event)
        self.centerOn(QPointF(200, 150))
        self.setFocus()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat("application/x-powertree-template"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-powertree-template"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasFormat("application/x-powertree-template"):
            data = event.mimeData().data("application/x-powertree-template")
            template_index = int(data.data())
            scene_pos = self.mapToScene(event.position().toPoint())
            self._canvas_scene.create_node_from_template(template_index, scene_pos)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        modifiers = event.modifiers()
        if event.key() == Qt.Key_C and modifiers == Qt.ControlModifier:
            self._canvas_scene.copy_selected_nodes()
            event.accept()
            return
        if event.key() == Qt.Key_V and modifiers == Qt.ControlModifier:
            vp = self.viewport().mapFromGlobal(QCursor.pos())
            scene_pos = self.mapToScene(vp)
            self._canvas_scene.paste_node(scene_pos)
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        current = self.transform().m11()
        if event.angleDelta().y() > 0:
            new_scale = current * 1.15
            if new_scale > 10.0:
                factor = 10.0 / current
            else:
                factor = 1.15
        else:
            new_scale = current / 1.15
            if new_scale < 0.1:
                factor = 0.1 / current
            else:
                factor = 1.0 / 1.15
        self.scale(factor, factor)
