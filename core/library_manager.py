import json
import os
import sys
import logging
from typing import List, Dict, Optional

from .component import Component, PowerModule, Load

logger = logging.getLogger(__name__)

CALC_TYPES = ["root", "switching", "ldo", "isolated", "load"]


def _get_resource_path(relative_path: str) -> str:
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)

DEFAULT_TEMPLATE = {
    "name": "", "calc_type": "switching",
    "width": 140, "height": 60, "color": "#64A0E6",
    "input_ports": 1, "output_ports": 1,
}


class LibraryManager:
    def __init__(self, preset_path: str = None):
        if preset_path is None:
            preset_path = _get_resource_path(os.path.join("..", "resources", "presets", "modules.json"))
        self._preset_path = preset_path
        self._templates: List[Dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self._preset_path):
            try:
                with open(self._preset_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if not isinstance(raw, list):
                    logger.warning("器件库文件格式异常，使用空列表")
                    raw = []
                self._templates = []
                for item in raw:
                    if isinstance(item, dict):
                        if "type" in item and "calc_type" not in item:
                            item["calc_type"] = item.pop("type")
                        self._templates.append(item)
            except (json.JSONDecodeError, OSError) as e:
                logger.error("加载器件库失败: %s", e)
                self._templates = []
        else:
            self._templates = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self._preset_path)), exist_ok=True)
            with open(self._preset_path, "w", encoding="utf-8") as f:
                json.dump(self._templates, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error("保存器件库失败: %s", e)

    @property
    def templates(self) -> List[Dict]:
        return self._templates

    def _is_name_duplicate(self, name: str, exclude_index: int = -1) -> bool:
        for i, t in enumerate(self._templates):
            if i != exclude_index and t.get("name", "") == name:
                return True
        return False

    def add_template(self, name: str, calc_type: str = "switching",
                     width: int = 140, height: int = 60, color: str = "#64A0E6",
                     input_ports: int = 1, output_ports: int = 1) -> bool:
        if self._is_name_duplicate(name):
            return False
        self._templates.append({
            "name": name, "calc_type": calc_type,
            "width": width, "height": height, "color": color,
            "input_ports": input_ports, "output_ports": output_ports,
        })
        self._save()
        return True

    def remove_template(self, index: int):
        if 0 <= index < len(self._templates):
            self._templates.pop(index)
            self._save()

    def update_template(self, index: int, name: str, calc_type: str = "switching",
                        width: int = 140, height: int = 60, color: str = "#64A0E6",
                        input_ports: int = 1, output_ports: int = 1) -> bool:
        if 0 <= index < len(self._templates):
            if self._is_name_duplicate(name, exclude_index=index):
                return False
            self._templates[index] = {
                "name": name, "calc_type": calc_type,
                "width": width, "height": height, "color": color,
                "input_ports": input_ports, "output_ports": output_ports,
            }
            self._save()
            return True
        return False

    def create_component_from_template(self, index: int, name: str = None) -> Optional[Component]:
        if not (0 <= index < len(self._templates)):
            return None
        tmpl = self._templates[index]
        comp_name = name or tmpl["name"]
        calc_type = tmpl.get("calc_type", "switching")
        if calc_type == "load":
            return Load(name=comp_name, comp_type=calc_type, calc_type="load")
        return PowerModule(name=comp_name, comp_type=calc_type, calc_type=calc_type)
