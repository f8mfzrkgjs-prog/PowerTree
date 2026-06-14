# PowerTree Designer

电源树图形化设计工具 - 用于设计和分析电源系统架构

> **声明：本项目完全由AI生成（opencode + GLM-4），用于学习和研究目的。**

## 功能特点

- **图形化设计**: 拖拽式电源树设计界面
- **器件库**: 支持BUCK、BOOST、LDO、EFUSE等多种电源器件
- **自动计算**: 功率、效率、损耗自动计算
- **连线功能**: 
  - 正交路径自动寻路
  - 分支连线支持
  - 手动途经点编辑
- **导出功能**: 支持PDF、PNG格式导出

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 项目结构

```
PowerTree/
├── app/                 # UI层
│   ├── main_window.py   # 主窗口
│   ├── canvas_scene.py  # 画布场景
│   ├── node_item.py     # 节点图形项
│   ├── edge_item.py     # 连线图形项
│   └── exporter.py      # 导出模块
├── core/                # 核心业务逻辑
│   ├── component.py     # 元器件数据模型
│   ├── tree_model.py    # 电源树模型
│   ├── calculator.py    # 功率计算
│   └── library_manager.py
├── utils/               # 工具类
│   ├── astar.py         # A*寻路算法
│   ├── undo_redo.py     # 撤销重做
│   └── file_io.py       # 文件IO
├── resources/           # 资源文件
│   └── presets/         # 器件库预设
├── tests/               # 测试
├── config.py            # 配置常量
└── main.py              # 入口
```

## 技术栈

- Python 3.10+
- PySide6 (Qt for Python)
- A* 寻路算法

## 许可证

MIT License
