"""测试格点寻路：GridMap, AStarRouter, 正交路径"""
import sys
sys.path.insert(0, '.')
from PySide6.QtCore import QPointF, QRectF
from utils.astar import GridMap, AStarRouter, build_grid_map_from_scene
from app.edge_item import build_ortho_path, snap_to_edge_grid, EDGE_GRID


class TestGridMap:
    def test_to_grid(self):
        gm = GridMap(20)
        gx, gy = gm.to_grid(QPointF(45, 55))
        assert gx == 2  # 45/20=2.25 → round → 2
        assert gy == 3  # 55/20=2.75 → round → 3

    def test_to_scene(self):
        gm = GridMap(20)
        pt = gm.to_scene(3, 5)
        assert pt.x() == 60
        assert pt.y() == 100

    def test_is_blocked(self):
        gm = GridMap(20)
        gm.add_obstacle(QRectF(40, 40, 60, 60))
        assert gm.is_blocked(2, 2)  # (40,40)
        assert gm.is_blocked(4, 4)  # (80,80) 
        assert not gm.is_blocked(0, 0)

    def test_is_line_free(self):
        gm = GridMap(20)
        gm.add_obstacle(QRectF(40, 40, 60, 60))
        assert not gm.is_line_free(QPointF(0, 60), QPointF(200, 60))
        assert gm.is_line_free(QPointF(0, 0), QPointF(0, 100))


class TestAStarRouter:
    def test_direct_path(self):
        gm = GridMap(20)
        path = AStarRouter.find_path(gm, QPointF(0, 0), QPointF(200, 0))
        assert path is not None
        assert len(path) >= 2
        # 起点和终点应接近
        assert path[0].x() == 0 and path[0].y() == 0
        assert path[-1].x() == 200 and path[-1].y() == 0

    def test_avoid_obstacle(self):
        gm = GridMap(20)
        gm.add_obstacle(QRectF(60, -10, 80, 80))
        path = AStarRouter.find_path(gm, QPointF(0, 0), QPointF(200, 0))
        assert path is not None
        assert len(path) > 2  # 至少需要绕行
        # 所有段都应是正交的
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            assert a.x() == b.x() or a.y() == b.y(), f"段 {i} 不是正交: {a}→{b}"

    def test_orthogonal_all(self):
        """随机测试多条路径，验证全部正交。"""
        gm = GridMap(20)
        gm.add_obstacle(QRectF(100, 80, 80, 100))
        gm.add_obstacle(QRectF(40, 200, 60, 80))
        test_cases = [
            (QPointF(0, 0), QPointF(300, 0)),
            (QPointF(0, 0), QPointF(300, 300)),
            (QPointF(300, 0), QPointF(0, 300)),
            (QPointF(0, 200), QPointF(400, 200)),
        ]
        for start, end in test_cases:
            path = AStarRouter.find_path(gm, start, end)
            assert path is not None, f"未找到路径: {start}→{end}"
            for i in range(len(path) - 1):
                a, b = path[i], path[i + 1]
                assert a.x() == b.x() or a.y() == b.y(), f"正交检查失败"

    def test_grid_aligned(self):
        """验证所有途经点都对齐到20px格点。"""
        gm = GridMap(20)
        gm.add_obstacle(QRectF(60, -10, 80, 80))
        path = AStarRouter.find_path(gm, QPointF(0, 0), QPointF(200, 0))
        for pt in path:
            assert int(pt.x()) % 20 == 0, f"X 未对齐: {pt.x()}"
            assert int(pt.y()) % 20 == 0, f"Y 未对齐: {pt.y()}"


class TestOrthoPaths:
    def test_build_ortho_path(self):
        wp = build_ortho_path(QPointF(100, 100), QPointF(300, 200))
        assert len(wp) >= 3
        # 正交检查
        for i in range(len(wp) - 1):
            a, b = wp[i], wp[i + 1]
            assert a.x() == b.x() or a.y() == b.y()

    def test_snap_to_grid(self):
        pt = snap_to_edge_grid(QPointF(33, 67))
        assert pt.x() == 40
        assert pt.y() == 60

    def test_grid_size_consistency(self):
        assert EDGE_GRID == 20
