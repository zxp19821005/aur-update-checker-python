# -*- coding: utf-8 -*-
"""
显示设置相关功能
"""
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QTableWidget, QHeaderView,
    QTableWidgetItem, QComboBox, QCheckBox, QWidget, QHBoxLayout,
    QFormLayout, QSpinBox  # 添加 QSpinBox
)
from PySide6.QtCore import Qt

def setup_display_tab(self, display_tab):
    """设置显示标签页

    Args:
        display_tab: 显示标签页小部件
    """
    display_layout = QVBoxLayout(display_tab)

    # 列显示设置组
    columns_group = QGroupBox("表格列显示设置")
    columns_layout = QVBoxLayout()
    columns_group.setLayout(columns_layout)
    display_layout.addWidget(columns_group)

    # 创建表格来显示列设置
    self.columns_table = QTableWidget()
    self.columns_table.setColumnCount(4)
    self.columns_table.setHorizontalHeaderLabels(["序号", "表格列名", "对齐方式", "是否显示"])
    self.columns_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    self.columns_table.verticalHeader().setVisible(False)
    columns_layout.addWidget(self.columns_table)

    # 定义列信息
    self.column_settings = [
        {"name": "软件名", "config_key": "name"},
        {"name": "AUR版本", "config_key": "aur_version"},
        {"name": "上游版本", "config_key": "upstream_version"},
        {"name": "状态", "config_key": "status"},
        {"name": "AUR检查时间", "config_key": "aur_check_time"},
        {"name": "上游检查时间", "config_key": "upstream_check_time"},
        {"name": "检查器类型", "config_key": "checker_type"},
        {"name": "上游URL", "config_key": "upstream_url"},
        {"name": "备注", "config_key": "notes"}
    ]

    # 填充表格数据
    self.columns_table.setRowCount(len(self.column_settings))
    for i, column in enumerate(self.column_settings):
        # 序号
        index_item = QTableWidgetItem(str(i + 1))
        index_item.setFlags(Qt.ItemIsEnabled)
        self.columns_table.setItem(i, 0, index_item)

        # 列名
        name_item = QTableWidgetItem(column["name"])
        name_item.setFlags(Qt.ItemIsEnabled)
        self.columns_table.setItem(i, 1, name_item)

        # 对齐方式
        alignment_combo = QComboBox()
        alignment_combo.addItems(["左对齐", "居中对齐", "右对齐"])
        current_alignment = self.config.get(f"ui.text_alignment.{column['config_key']}", "left")
        alignment_combo.setCurrentText({
            "left": "左对齐",
            "center": "居中对齐",
            "right": "右对齐"
        }[current_alignment])
        self.columns_table.setCellWidget(i, 2, alignment_combo)

        # 是否显示
        show_check = QCheckBox()
        show_check.setChecked(self.config.get(f"ui.show_{column['config_key']}", True))
        show_check_widget = QWidget()
        show_check_layout = QHBoxLayout(show_check_widget)
        show_check_layout.addWidget(show_check)
        show_check_layout.setAlignment(Qt.AlignCenter)
        show_check_layout.setContentsMargins(0, 0, 0, 0)
        self.columns_table.setCellWidget(i, 3, show_check_widget)

    # UI 设置组
    ui_group = QGroupBox("界面设置")
    ui_layout = QVBoxLayout()
    ui_group.setLayout(ui_layout)
    display_layout.addWidget(ui_group)

    # UI 设置表单
    ui_form = QFormLayout()
    ui_layout.addLayout(ui_form)

    # 字体大小设置
    self.font_size_spin = self._create_form_control(
    ui_form, "字体大小:", QSpinBox, "ui.font_size", 11,
    minimum=8, maximum=16, singleStep=1
)
