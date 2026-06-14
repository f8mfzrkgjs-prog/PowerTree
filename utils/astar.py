"""
A* 寻路引擎 — 在格点地图上寻找避开障碍物的最短正交路径。

地图为 scene 坐标系的 20px 网格，障碍物来自画布上已有节点的外框矩形。
"""

import heapq
import math
from typing import List, Tuple, Set, Optional, Dict
from PySide6.QtCore import QPointF, QRectF


class PathCache:
    """路径缓存，避免重复计算相同起终点的路径。"""
    
    _instance = None
    _cache: Dict[Tuple, List[QPointF]] = {}
    _max_size = 100
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_key(self, start: QPointF, end: QPointF, obstacle_hash: int) -> Tuple:
        return (
            int(start.x()), int(start.y()),
            int(end.x()), int(end.y()),
            obstacle_hash
        )
    
    def get(self, key: Tuple) -> Optional[List[QPointF]]:
        return self._cache.get(key)
    
    def set(self, key: Tuple, path: List[QPointF]):
        if len(self._cache) >= self._max_size:
            keys = list(self._cache.keys())
            for k in keys[:20]:
                del self._cache[k]
        self._cache[key] = path
    
    def clear(self):
        self._cache.clear()


class GridMap:
    """将场景矩形区域映射为离散格点地图。"""

    def __init__(self, grid_size: int = 20):
        self._grid = grid_size
        self._obstacles: List[QRectF] = []
        self._margin = 8  # 障碍物外扩边距

    @property
    def grid_size(self) -> int:
        return self._grid

    def clear_obstacles(self):
        self._obstacles.clear()

    def add_obstacle(self, rect: QRectF):
        self._obstacles.append(rect.adjusted(-self._margin, -self._margin,
                                             self._margin, self._margin))

    def to_grid(self, point: QPointF) -> Tuple[int, int]:
        return (int(point.x() / self._grid + 0.5), int(point.y() / self._grid + 0.5))

    def to_scene(self, gx: int, gy: int) -> QPointF:
        return QPointF(gx * self._grid, gy * self._grid)

    def is_blocked(self, gx: int, gy: int) -> bool:
        x = gx * self._grid
        y = gy * self._grid
        pt = QPointF(x, y)
        for ob in self._obstacles:
            if ob.contains(pt):
                return True
        return False

    def is_line_free(self, a: QPointF, b: QPointF) -> bool:
        """检查从 a 到 b 的直线（水平或垂直）是否穿过障碍物。"""
        gx1, gy1 = self.to_grid(a)
        gx2, gy2 = self.to_grid(b)
        if gx1 == gx2:
            step = 1 if gy2 > gy1 else -1
            for gy in range(gy1, gy2 + step, step):
                if self.is_blocked(gx1, gy):
                    return False
        elif gy1 == gy2:
            step = 1 if gx2 > gx1 else -1
            for gx in range(gx1, gx2 + step, step):
                if self.is_blocked(gx, gy1):
                    return False
        else:
            return False
        return True


class AStarRouter:
    """A* 寻路器 — 在 GridMap 上找到从起点到终点的最短正交路径。"""

    _cache = PathCache.get_instance()

    @staticmethod
    def find_path(grid_map: GridMap, start: QPointF, end: QPointF,
                  debug: bool = False) -> Optional[List[QPointF]]:
        """
        返回从 start 到 end 的正交路径点列表（格点对齐）。
        如果无法到达，返回 None。
        """
        obstacle_hash = hash(tuple(
            (int(r.x()), int(r.y()), int(r.width()), int(r.height()))
            for r in grid_map._obstacles
        ))
        cache_key = AStarRouter._cache.get_key(start, end, obstacle_hash)
        cached = AStarRouter._cache.get(cache_key)
        if cached is not None:
            return cached

        sx, sy = grid_map.to_grid(start)
        ex, ey = grid_map.to_grid(end)
        gs = grid_map.grid_size

        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        open_set = []
        heapq.heappush(open_set, (0, 0, sx, sy))
        came_from: dict = {}
        g_score: dict = { (sx, sy): 0 }

        min_x = min(sx, ex) - 30
        max_x = max(sx, ex) + 30
        min_y = min(sy, ey) - 30
        max_y = max(sy, ey) + 30

        while open_set:
            f, _, cx, cy = heapq.heappop(open_set)
            if (cx, cy) == (ex, ey):
                path = AStarRouter._reconstruct(came_from, (sx, sy), (ex, ey), gs)
                AStarRouter._cache.set(cache_key, path)
                return path

            for dx, dy in dirs:
                nx, ny = cx + dx, cy + dy
                if not (min_x <= nx <= max_x and min_y <= ny <= max_y):
                    continue
                if grid_map.is_blocked(nx, ny):
                    continue

                seg_start = grid_map.to_scene(cx, cy)
                seg_end = grid_map.to_scene(nx, ny)
                if not grid_map.is_line_free(seg_start, seg_end):
                    continue

                new_g = g_score[(cx, cy)] + 1
                if new_g < g_score.get((nx, ny), math.inf):
                    came_from[(nx, ny)] = (cx, cy)
                    g_score[(nx, ny)] = new_g
                    h = abs(nx - ex) + abs(ny - ey)
                    heapq.heappush(open_set, (new_g + h, len(open_set), nx, ny))

        return None

    @staticmethod
    def _reconstruct(came_from: dict, start: tuple, end: tuple, gs: int) -> List[QPointF]:
        """从 came_from 字典重建路径，并简化为关键拐点（压缩共线点）。"""
        raw = []
        cur = end
        while cur != start:
            raw.append(cur)
            cur = came_from[cur]
        raw.append(start)
        raw.reverse()

        if len(raw) <= 2:
            return [QPointF(x * gs, y * gs) for x, y in raw]

        # 压缩：保留拐弯处的点，去掉中间共线点
        compressed = [QPointF(raw[0][0] * gs, raw[0][1] * gs)]
        for i in range(1, len(raw) - 1):
            px, py = raw[i - 1]
            cx, cy = raw[i]
            nx, ny = raw[i + 1]
            if (px != nx and py != ny) or (px == nx and cx != nx) or (py == ny and cy != ny):
                pass
            if (cx - px) != (nx - cx) or (cy - py) != (ny - cy):
                compressed.append(QPointF(cx * gs, cy * gs))
        compressed.append(QPointF(raw[-1][0] * gs, raw[-1][1] * gs))
        return compressed


def build_grid_map_from_scene(node_items: dict, grid_size: int = 20,
                               exclude_ids: list = None) -> GridMap:
    """从场景中的节点构建格点地图（用于寻路）。"""
    exclude_ids = exclude_ids or []
    gm = GridMap(grid_size)
    for node_id, node_item in node_items.items():
        if node_id in exclude_ids:
            continue
        rect = node_item.sceneBoundingRect()
        gm.add_obstacle(rect)
    return gm
