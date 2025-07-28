# -*- coding: utf-8 -*-
"""
日志标签页UI初始化
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, 
    QTextEdit, QLabel, QComboBox, QCheckBox, QSpinBox
)

def init_ui(self):
    """初始化UI"""
    # 创建布局
    layout = QVBoxLayout(self)

    # 日志显示区域
    self.logs_text = QTextEdit()
    # 设置样式表，使其与软件整体风格一致
    style = """background-color: #2B2B2B; color: #CCCCCC;
             font-family: Source Code Pro, Consolas, monospace;
             border: 1px solid #444444;"""
    self.logs_text.setStyleSheet(style)
    # 设置字体
    font = self.logs_text.font()
    font.setPointSize(9)
    self.logs_text.setFont(font)

    # 设置日志显示样式表
    self.logs_text.setStyleSheet("""
        QTextEdit {
            font-family: "Consolas", "Courier New", monospace;
            font-size: 10pt;
            background-color: #121212;
            color: #FFFFFF;
        }
    """)

    # 启用富文本显示
    self.logs_text.setAcceptRichText(True)
    layout.addWidget(self.logs_text)

    # 底部工具栏
    bottom_toolbar = QHBoxLayout()
    layout.addLayout(bottom_toolbar)

    # 添加彩色日志切换选项
    self.colored_logs_check = QCheckBox("彩色日志")
    self.colored_logs_check.setChecked(True)  # 默认启用彩色日志
    self.colored_logs_check.stateChanged.connect(self.refresh_logs)
    bottom_toolbar.addWidget(self.colored_logs_check)

    # 添加自动滚动选项
    self.auto_scroll_check = QCheckBox("自动滚动")
    self.auto_scroll_check.setChecked(True)  # 默认启用自动滚动
    self.auto_scroll_check.stateChanged.connect(self.on_auto_scroll_changed)
    bottom_toolbar.addWidget(self.auto_scroll_check)

    # 添加日志显示行数选项
    bottom_toolbar.addWidget(QLabel("显示行数:"))
    self.log_lines_spin = QSpinBox()
    self.log_lines_spin.setRange(10, 10000)  # 设置范围从10行到10000行
    self.log_lines_spin.setValue(1000)       # 默认显示1000行
    self.log_lines_spin.setSingleStep(100)    # 每次调整100行
    self.log_lines_spin.valueChanged.connect(self.refresh_logs)
    bottom_toolbar.addWidget(self.log_lines_spin)

    # 添加日志级别选择下拉框
    bottom_toolbar.addWidget(QLabel("显示级别:"))
    self.log_level_combo = QComboBox()
    self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

    # 从配置读取设置
    self.load_settings_from_config()

    # 连接信号
    self.log_level_combo.currentTextChanged.connect(self.on_log_level_changed)
    bottom_toolbar.addWidget(self.log_level_combo)

    # 清除日志按钮
    self.clear_logs_button = QPushButton("清除日志")
    self.clear_logs_button.clicked.connect(self.clear_logs)
    self.clear_logs_button.setStyleSheet("""
        QPushButton {
            background-color: #e74c3c;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #c0392b;
        }
        QPushButton:pressed {
            background-color: #a93226;
        }
    """)
    bottom_toolbar.addWidget(self.clear_logs_button)

    # 填充空间
    bottom_toolbar.addStretch(1)

    # 初始刷新日志
    self.refresh_logs()
