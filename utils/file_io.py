import json
import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class ProjectIO:
    @staticmethod
    def save_project(filepath: str, tree_data: dict, node_positions: dict) -> bool:
        project = {
            "tree": tree_data,
            "positions": node_positions,
        }
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(project, f, indent=2, ensure_ascii=False)
            logger.info("工程已保存: %s", filepath)
            return True
        except PermissionError:
            logger.error("保存失败 - 无写入权限: %s", filepath)
            return False
        except OSError as e:
            logger.error("保存失败 - 系统错误: %s", e)
            return False
        except Exception as e:
            logger.error("保存失败: %s", e)
            return False

    @staticmethod
    def load_project(filepath: str) -> dict | None:
        if not os.path.exists(filepath):
            logger.error("文件不存在: %s", filepath)
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "tree" not in data:
                logger.error("无效的工程文件格式: %s", filepath)
                return None
            logger.info("工程已加载: %s", filepath)
            return data
        except json.JSONDecodeError as e:
            logger.error("JSON解析失败 (%s): %s", filepath, e)
            return None
        except PermissionError:
            logger.error("读取失败 - 无权限: %s", filepath)
            return None
        except Exception as e:
            logger.error("加载失败: %s", e)
            return None
