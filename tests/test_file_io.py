"""测试工程文件读写"""
import sys
import os
import json
import tempfile
sys.path.insert(0, '.')
from utils.file_io import ProjectIO


class TestProjectIO:
    def setup_method(self):
        self.tmp = tempfile.mktemp(suffix='.json')

    def teardown_method(self):
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def test_save_and_load(self):
        tree = {"roots": [{"id": "abc", "component": {"name": "R", "calc_type": "root"}, "children": []}]}
        positions = {"abc": {"x": 100, "y": 200}}
        ok = ProjectIO.save_project(self.tmp, tree, positions)
        assert ok
        assert os.path.exists(self.tmp)

        loaded = ProjectIO.load_project(self.tmp)
        assert loaded is not None
        assert "tree" in loaded
        assert "positions" in loaded
        assert loaded["tree"]["roots"][0]["component"]["name"] == "R"

    def test_load_nonexistent(self):
        result = ProjectIO.load_project("/nonexistent/path.json")
        assert result is None

    def test_load_invalid_json(self):
        with open(self.tmp, 'w') as f:
            f.write("not json")
        result = ProjectIO.load_project(self.tmp)
        assert result is None

    def test_load_missing_tree_key(self):
        with open(self.tmp, 'w') as f:
            json.dump({"positions": {}}, f)
        result = ProjectIO.load_project(self.tmp)
        assert result is None
