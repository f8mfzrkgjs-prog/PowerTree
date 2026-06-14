from PySide6.QtCore import Qt, Signal, QMimeData, QByteArray
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtGui import QDrag


class _DragListWidget(QListWidget):
    dragStarted = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragOnly)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item:
            return
        template_index = item.data(Qt.UserRole)
        mime_data = QMimeData()
        mime_data.setData("application/x-powertree-template", QByteArray(str(template_index).encode()))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.CopyAction)


class LibraryPanel(QWidget):
    def __init__(self, library_manager, parent=None):
        super().__init__(parent)
        self._library = library_manager
        self._setup_ui()
        self._load_templates()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        title = QLabel("器件库")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 6px;")
        layout.addWidget(title)

        self._list_widget = _DragListWidget()
        self._list_widget.setMaximumWidth(220)
        layout.addWidget(self._list_widget)

    def _load_templates(self):
        self._list_widget.clear()
        for i, tmpl in enumerate(self._library.templates):
            ct = tmpl.get("calc_type", "switching")
            item = QListWidgetItem(f"{tmpl['name']}  [{ct}]")
            item.setData(Qt.UserRole, i)
            item.setFlags(item.flags() | Qt.ItemIsDragEnabled)
            self._list_widget.addItem(item)
