import sys
import logging
import os
from PySide6.QtWidgets import QApplication
from core.library_manager import LibraryManager
from core.tree_model import TreeModel
from app.main_window import MainWindow


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger("powertree")
    logger.info("PowerTree Designer 启动")

    app = QApplication(sys.argv)
    app.setApplicationName("PowerTree Designer")

    library = LibraryManager()
    tree_model = TreeModel()

    window = MainWindow(tree_model, library)
    window.show()

    rc = app.exec()
    logger.info("PowerTree Designer 退出 (rc=%d)", rc)
    sys.exit(rc)


if __name__ == "__main__":
    main()
