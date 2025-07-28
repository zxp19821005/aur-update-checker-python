# -*- coding: utf-8 -*-
"""
设置表单控件创建模块
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QLineEdit, QCheckBox, QSpinBox, QComboBox
)

def create_form_control(self, parent, label, control_type, config_key, default_value=None, **kwargs):
    """创建表单控件

    Args:
        parent: 父布局
        label: 标签文本
        control_type: 控件类型(QLineEdit, QCheckBox等)
        config_key: 配置键
        default_value: 默认值
        kwargs: 控件的额外参数
    """
    row_layout = QHBoxLayout()

    if control_type == QLineEdit:
        control = QLineEdit(**kwargs)
        control.setText(str(self.config.get(config_key, default_value)))
    elif control_type == QCheckBox:
        control = QCheckBox(**kwargs)
        control.setChecked(bool(self.config.get(config_key, default_value)))
    elif control_type == QSpinBox:
        control = QSpinBox(**kwargs)
        control.setValue(int(self.config.get(config_key, default_value)))
    elif control_type == QComboBox:
        # 从kwargs中提取items参数
        items = kwargs.pop('items', [])
        control = QComboBox(**kwargs)

        # 添加项目到下拉框
        if items:
            control.addItems(items)

        # 设置当前值
        current_value = self.config.get(config_key, default_value)
        if current_value in items:
            control.setCurrentText(current_value)

    row_layout.addWidget(control)
    parent.addRow(label, row_layout)
    return control
