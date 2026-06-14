"""测试器件库管理"""
import sys
import os
import json
import tempfile
sys.path.insert(0, '.')
from core.library_manager import LibraryManager


class TestLibraryManager:
    def setup_method(self):
        self.tmp = tempfile.mktemp(suffix='.json')
        self.lm = LibraryManager(self.tmp)

    def teardown_method(self):
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def test_add_template(self):
        ok = self.lm.add_template("BUCK_5V", "switching", 220, 110, "#2864B4", 1, 1)
        assert ok
        assert len(self.lm.templates) == 1
        assert self.lm.templates[0]["name"] == "BUCK_5V"

    def test_duplicate_name(self):
        self.lm.add_template("BUCK", "switching")
        ok = self.lm.add_template("BUCK", "switching")
        assert not ok
        assert len(self.lm.templates) == 1

    def test_remove_template(self):
        self.lm.add_template("A", "switching")
        self.lm.add_template("B", "ldo")
        assert len(self.lm.templates) == 2
        self.lm.remove_template(0)
        assert len(self.lm.templates) == 1
        assert self.lm.templates[0]["name"] == "B"

    def test_update_template(self):
        self.lm.add_template("OLD", "switching")
        ok = self.lm.update_template(0, "NEW", "ldo", 200, 100, "#FF0000", 2, 2)
        assert ok
        assert self.lm.templates[0]["name"] == "NEW"
        assert self.lm.templates[0]["calc_type"] == "ldo"

    def test_create_component(self):
        self.lm.add_template("BUCK", "switching")
        comp = self.lm.create_component_from_template(0)
        assert comp is not None
        assert comp.calc_type == "switching"

    def test_create_load_component(self):
        self.lm.add_template("LOAD", "load", input_ports=1, output_ports=0)
        comp = self.lm.create_component_from_template(0)
        assert comp is not None
        assert comp.calc_type == "load"

    def test_persistence(self):
        self.lm.add_template("SAVED", "switching")
        # 重新加载
        lm2 = LibraryManager(self.tmp)
        assert len(lm2.templates) == 1
        assert lm2.templates[0]["name"] == "SAVED"
