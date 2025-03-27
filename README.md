# 模型查找器（精简版）

一个轻量级工具，用于检测缺失模型并生成下载链接。

## 功能特点

- 界面简洁，操作直观
- 工作流JSON分析
- Bing搜索生成下载链接
- HTML结果视图

## 使用方法

1. 选择工作流JSON文件并分析
2. 使用生成的CSV文件搜索下载链接
3. 查看HTML结果获取下载链接

## 运行环境

- Python 3.9+
- 依赖包: pandas, DrissionPage

## 安装依赖

```bash
pip install pandas DrissionPage
```

## 运行程序

```bash
python model_finder_精简版.py
```

## 项目结构

```
comfyui-model-finder/
├── src/                      # 源代码
│   ├── model_finder/         # 主要模块
│   │   ├── core/             # 核心功能
│   │   │   ├── model_finder.py    # 模型查找功能
│   │   │   └── link_generator.py  # 链接生成功能
│   │   ├── ui/               # 用户界面
│   │   │   └── main_window.py     # 主窗口UI
│   │   ├── utils/            # 工具函数
│   │   │   └── helpers.py         # 辅助功能
│   │   └── __init__.py       # 包初始化
│   └── main.py               # 入口点
├── requirements.txt          # 项目依赖
├── build_exe.bat             # 构建可执行文件脚本
└── README.md                 # 项目说明
```

## 打包为可执行文件

使用提供的批处理文件可以轻松打包为独立的exe文件：

```bash
./build_exe.bat
```

打包后的文件将在`dist`文件夹中找到。

## 联系方式

- **微信**：wangdefa4567
- **邮箱**：littlegrass@outlook.com
- **微信二维码**：请见项目根目录下的`wechat_qrcode.jpg`

## 许可证

MIT License 