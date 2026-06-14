"""
导出功能模块 - 支持PDF、PNG等格式导出
"""
import logging
from PySide6.QtCore import Qt, QPointF, QRectF, QMarginsF
from PySide6.QtGui import QPixmap, QPainter, QPdfWriter, QPageSize, QPageLayout
from PySide6.QtWidgets import QFileDialog, QMessageBox, QGraphicsScene

from config import ExportConfig

logger = logging.getLogger(__name__)


class Exporter:
    """场景导出器"""
    
    def __init__(self, scene: QGraphicsScene, parent=None):
        self._scene = scene
        self._parent = parent
        
    def export_to_pdf(self, file_path: str = None) -> bool:
        """
        导出场景为PDF文件
        
        Args:
            file_path: 保存路径，如果为None则弹出文件对话框
            
        Returns:
            是否导出成功
        """
        if file_path is None:
            file_path, _ = QFileDialog.getSaveFileName(
                self._parent, "导出PDF", "", "PDF文件 (*.pdf)"
            )
        if not file_path:
            return False
        if not file_path.lower().endswith('.pdf'):
            file_path += '.pdf'

        scene_rect = self._scene.itemsBoundingRect()
        if scene_rect.isEmpty():
            if self._parent:
                QMessageBox.warning(self._parent, "导出失败", "画布为空")
            return False

        try:
            margin = ExportConfig.PNG_MARGIN
            export_rect = scene_rect.adjusted(-margin, -margin, margin, margin)
            
            scale_factor = ExportConfig.EXPORT_SCALE
            pixmap = QPixmap(
                int(export_rect.width() * scale_factor),
                int(export_rect.height() * scale_factor)
            )
            pixmap.fill(Qt.white)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.scale(scale_factor, scale_factor)
            painter.translate(-export_rect.topLeft())
            self._scene.render(painter, export_rect, export_rect)
            painter.end()

            printer = QPdfWriter(file_path)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageMargins(QMarginsF(ExportConfig.PDF_MARGIN, ExportConfig.PDF_MARGIN, 
                                             ExportConfig.PDF_MARGIN, ExportConfig.PDF_MARGIN), 
                                   QPageLayout.Unit.Millimeter)
            printer.setResolution(ExportConfig.PDF_RESOLUTION)

            painter = QPainter(printer)
            if not painter.isActive():
                if self._parent:
                    QMessageBox.warning(self._parent, "导出失败", "无法创建PDF文件")
                return False

            page_rect = printer.pageLayout().paintRectPixels(printer.resolution())

            img_scale_x = page_rect.width() / pixmap.width()
            img_scale_y = page_rect.height() / pixmap.height()
            img_scale = min(img_scale_x, img_scale_y)

            offset_x = (page_rect.width() - pixmap.width() * img_scale) / 2
            offset_y = (page_rect.height() - pixmap.height() * img_scale) / 2

            painter.translate(offset_x, offset_y)
            painter.scale(img_scale, img_scale)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()

            logger.info(f"导出PDF成功: {file_path}")
            return True

        except Exception as e:
            logger.error(f"导出PDF失败: {e}")
            if self._parent:
                QMessageBox.warning(self._parent, "导出失败", f"导出过程中发生错误: {e}")
            return False

    def export_to_png(self, file_path: str = None, scale: float = 1.0) -> bool:
        """
        导出场景为PNG图片
        
        Args:
            file_path: 保存路径，如果为None则弹出文件对话框
            scale: 缩放比例，默认1.0
            
        Returns:
            是否导出成功
        """
        if file_path is None:
            file_path, _ = QFileDialog.getSaveFileName(
                self._parent, "导出PNG", "", "PNG图片 (*.png)"
            )
        if not file_path:
            return False
        if not file_path.lower().endswith('.png'):
            file_path += '.png'

        scene_rect = self._scene.itemsBoundingRect()
        if scene_rect.isEmpty():
            if self._parent:
                QMessageBox.warning(self._parent, "导出失败", "画布为空")
            return False

        try:
            margin = ExportConfig.PNG_MARGIN
            export_rect = scene_rect.adjusted(-margin, -margin, margin, margin)

            pixmap = QPixmap(
                int(export_rect.width() * scale),
                int(export_rect.height() * scale)
            )
            pixmap.fill(Qt.white)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.scale(scale, scale)
            painter.translate(-export_rect.topLeft())
            self._scene.render(painter, export_rect, export_rect)
            painter.end()

            if pixmap.save(file_path):
                logger.info(f"导出PNG成功: {file_path}")
                return True
            else:
                if self._parent:
                    QMessageBox.warning(self._parent, "导出失败", "无法保存PNG文件")
                return False

        except Exception as e:
            logger.error(f"导出PNG失败: {e}")
            if self._parent:
                QMessageBox.warning(self._parent, "导出失败", f"导出过程中发生错误: {e}")
            return False

    def export_to_svg(self, file_path: str = None) -> bool:
        """
        导出场景为SVG矢量图
        
        Args:
            file_path: 保存路径，如果为None则弹出文件对话框
            
        Returns:
            是否导出成功
        """
        if file_path is None:
            file_path, _ = QFileDialog.getSaveFileName(
                self._parent, "导出SVG", "", "SVG矢量图 (*.svg)"
            )
        if not file_path:
            return False
        if not file_path.lower().endswith('.svg'):
            file_path += '.svg'

        scene_rect = self._scene.itemsBoundingRect()
        if scene_rect.isEmpty():
            if self._parent:
                QMessageBox.warning(self._parent, "导出失败", "画布为空")
            return False

        try:
            from PySide6.QtSvg import QSvgGenerator
            
            generator = QSvgGenerator()
            generator.setFileName(file_path)
            generator.setSize(scene_rect.size().toSize())
            generator.setViewBox(scene_rect)

            painter = QPainter(generator)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._scene.render(painter, scene_rect, scene_rect)
            painter.end()

            logger.info(f"导出SVG成功: {file_path}")
            return True

        except ImportError:
            if self._parent:
                QMessageBox.warning(self._parent, "导出失败", "QtSvg模块不可用")
            return False
        except Exception as e:
            logger.error(f"导出SVG失败: {e}")
            if self._parent:
                QMessageBox.warning(self._parent, "导出失败", f"导出过程中发生错误: {e}")
            return False
