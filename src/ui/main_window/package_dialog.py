# -*- coding: utf-8 -*-
"""
软件包对话框模块
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QDialogButtonBox,
    QCheckBox
)
from PySide6.QtCore import Qt

class PackageDialog(QDialog):
    """软件包添加/编辑对话框"""

    def __init__(self, parent=None, package=None):
        """初始化对话框

        Args:
            parent: 父窗口
            package: 要编辑的软件包，None表示添加新软件包
        """
        super().__init__(parent)
        self.package = package

        # 设置对话框属性
        self.setWindowTitle("添加软件包" if package is None else "编辑软件包")
        self.setMinimumWidth(400)

        # 创建表单布局
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        layout.addLayout(form_layout)

        # 软件包名称
        self.name_edit = QLineEdit()
        if package:
            self.name_edit.setText(package.get("name", ""))
            self.name_edit.setReadOnly(True)  # 编辑模式下不允许修改名称
        form_layout.addRow("软件包名称:", self.name_edit)

        # 上游URL
        self.url_edit = QLineEdit()
        if package:
            self.url_edit.setText(package.get("upstream_url", ""))
        form_layout.addRow("上游URL:", self.url_edit)

        # 导入QComboBox
        from PySide6.QtWidgets import QComboBox

        # 检查器类型
        self.checker_type_edit = QComboBox()
        # 添加可用的检查器类型
        checker_types = ["github", "gitlab", "pypi", "common", "gitee", "json", "redirect", "curl", "playwright", "npm"]
        for checker_type in checker_types:
            self.checker_type_edit.addItem(checker_type)

        # 如果是编辑模式，设置当前选中的检查器类型
        if package and package.get("checker_type"):
            index = self.checker_type_edit.findText(package.get("checker_type"))
            if index >= 0:
                self.checker_type_edit.setCurrentIndex(index)
        form_layout.addRow("检查器类型:", self.checker_type_edit)

        # 版本提取关键字
        self.version_extract_key_edit = QLineEdit()
        if package:
            self.version_extract_key_edit.setText(package.get("version_extract_key", ""))
        form_layout.addRow("版本提取关键字:", self.version_extract_key_edit)

        # 是否检查测试版本
        self.check_test_versions = QCheckBox("检查测试版本（alpha、beta、rc等）")
        if package:
            self.check_test_versions.setChecked(package.get("check_test_versions", False))
        form_layout.addRow("", self.check_test_versions)

        # 备注
        self.notes_edit = QTextEdit()
        if package:
            self.notes_edit.setPlainText(package.get("notes", ""))
        self.notes_edit.setMaximumHeight(100)
        form_layout.addRow("备注:", self.notes_edit)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_package_data(self):
        """获取对话框中的软件包数据

        Returns:
            dict: 软件包数据字典
        """
        package_data = {
            "name": self.name_edit.text().strip(),
            "upstream_url": self.url_edit.text().strip(),
            "checker_type": self.checker_type_edit.currentText(),
            "version_extract_key": self.version_extract_key_edit.text().strip(),
            # 已删除 click_selector 和 download_selector
            "check_test_versions": self.check_test_versions.isChecked(),
            "notes": self.notes_edit.toPlainText().strip()
        }

        return package_data