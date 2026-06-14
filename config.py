"""
PowerTree 配置常量
"""

class GridConfig:
    """格点配置"""
    GRID_SIZE = 20
    EDGE_GRID = 20
    NODE_GRID_SIZE = 20
    GRID_MAJOR = 5


class NodeConfig:
    """节点配置"""
    DEFAULT_WIDTH = 220
    DEFAULT_HEIGHT = 110
    MIN_WIDTH = 160
    MIN_HEIGHT = 60
    HEADER_HEIGHT = 22
    PARAM_ROW_HEIGHT = 18
    PARAM_TOP_MARGIN = HEADER_HEIGHT + 14
    BODY_BOTTOM_PADDING = 2
    PLOSS_SECTION_HEIGHT = 20


class PortConfig:
    """端口配置"""
    PORT_RADIUS = 7
    PORT_DETECT_RADIUS = 14
    PORT_SPACING = 18
    PORT_SNAP_DISTANCE = 8
    PORT_HOVER_DISTANCE = 14


class ResizeConfig:
    """缩放配置"""
    RESIZE_HANDLE_SIZE = 7


class EdgeConfig:
    """连线配置"""
    EDGE_MARGIN = 8
    WAYPOINT_HIT_DISTANCE = 8
    ENDPOINT_HIT_DISTANCE = 10
    ARROW_SIZE = 8
    WAYPOINT_RADIUS = 3


class SceneConfig:
    """场景配置"""
    SCENE_MARGIN = 2000
    INITIAL_POSITION_X = 50
    INITIAL_POSITION_Y = 50
    POSITION_OFFSET_X = 80
    POSITION_OFFSET_Y = 80
    POSITION_MAX_X = 800


class Colors:
    """颜色配置"""
    DEFAULT_NODE_COLOR = "#C8C8C8"
    
    TYPE_COLORS = {
        "root": "#3C8C3C",
        "buck": "#2864B4",
        "ldo": "#A07828",
        "boost": "#B43C28",
        "isolated": "#6450A0",
        "load": "#646464",
    }
    
    HEADER_COLORS = {
        "root": "#286E28",
        "buck": "#194B91",
        "ldo": "#825F14",
        "boost": "#912819",
        "isolated": "#4B3782",
        "load": "#464646",
    }
    
    EDGE_COLOR = "#3C3C3C"
    EDGE_SELECTED_COLOR = "#0078D7"
    PORT_INPUT_COLOR = "#64A0E6"
    PORT_OUTPUT_COLOR = "#E66450"
    PORT_OCCUPIED_COLOR = "#A0A0A0"
    PORT_HOVER_COLOR = "#00C850"


class ExportConfig:
    """导出配置"""
    PDF_MARGIN = 15
    PNG_MARGIN = 50
    EXPORT_SCALE = 2.0
    PDF_RESOLUTION = 300


class CalculatorConfig:
    """计算配置"""
    VOLTAGE_TOLERANCE = 0.05
    LOW_EFFICIENCY_THRESHOLD = 70
