# -*- coding: utf-8 -*-
"""
定时检查设置模块
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QPushButton, QCheckBox, QSpinBox, QGroupBox
)

def setup_scheduler_tab(self, tab):
    """设置定时检查标签页

    Args:
        self: SettingsTab实例
        tab: 标签页Widget
    """
    layout = QVBoxLayout(tab)

    # 创建定时检查分组
    scheduler_group = QGroupBox("定时检查设置")
    scheduler_layout = QFormLayout()

    # 启用定时检查
    self.enable_scheduler_check = QCheckBox()
    scheduler_layout.addRow("启用定时检查:", self.enable_scheduler_check)

    # AUR检查间隔
    self.aur_interval_spin = QSpinBox()
    self.aur_interval_spin.setRange(1, 168)  # 1小时到1周
    self.aur_interval_spin.setSuffix(" 小时")
    self.aur_interval_spin.setToolTip("设置自动检查AUR版本的间隔，单位为小时")
    scheduler_layout.addRow("AUR版本检查间隔:", self.aur_interval_spin)

    # 上游检查间隔
    self.upstream_interval_spin = QSpinBox()
    self.upstream_interval_spin.setRange(1, 168)  # 1小时到1周
    self.upstream_interval_spin.setSuffix(" 小时")
    self.upstream_interval_spin.setToolTip("设置自动检查上游版本的间隔，单位为小时")
    scheduler_layout.addRow("上游版本检查间隔:", self.upstream_interval_spin)

    # 启动时检查
    self.check_on_startup_check = QCheckBox()
    scheduler_layout.addRow("启动时执行检查:", self.check_on_startup_check)

    # 启用通知
    self.enable_notification_check = QCheckBox()
    scheduler_layout.addRow("启用定时检查通知:", self.enable_notification_check)

    # 将布局设置到分组
    scheduler_group.setLayout(scheduler_layout)

    # 添加到主布局
    layout.addWidget(scheduler_group)

    # 创建按钮区域
    button_layout = QHBoxLayout()

    # 添加立即检查按钮
    check_now_button = QPushButton("立即执行检查")
    check_now_button.clicked.connect(self._check_now)
    button_layout.addWidget(check_now_button)

    layout.addLayout(button_layout)

    # 添加一个弹性空间
    layout.addStretch(1)

    # 加载定时检查设置
    self._load_scheduler_settings()

def _load_scheduler_settings(self):
    """加载定时检查设置"""
    try:
        scheduler_config = self.config.get("scheduler", {})

        # 加载设置
        self.enable_scheduler_check.setChecked(scheduler_config.get("enabled", True))
        self.aur_interval_spin.setValue(scheduler_config.get("aur_check_interval", 24))
        self.upstream_interval_spin.setValue(scheduler_config.get("upstream_check_interval", 48))
        self.check_on_startup_check.setChecked(scheduler_config.get("check_on_startup", True))
        self.enable_notification_check.setChecked(scheduler_config.get("notification_enabled", True))

        self.logger.debug("已加载定时检查设置")
    except Exception as e:
        self.logger.error(f"加载定时检查设置时出错: {str(e)}")

def _update_scheduler_settings(self):
    """更新定时检查设置到配置"""
    try:
        # 更新配置
        self.config.set("scheduler.enabled", self.enable_scheduler_check.isChecked())
        self.config.set("scheduler.aur_check_interval", self.aur_interval_spin.value())
        self.config.set("scheduler.upstream_check_interval", self.upstream_interval_spin.value())
        self.config.set("scheduler.check_on_startup", self.check_on_startup_check.isChecked())
        self.config.set("scheduler.notification_enabled", self.enable_notification_check.isChecked())

        self.logger.debug("已更新定时检查设置到配置")
    except Exception as e:
        self.logger.error(f"更新定时检查设置时出错: {str(e)}")

def _check_now(self):
    """立即执行版本检查"""
    try:
        # 查找主窗口实例
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()

        # 寻找主窗口实例
        for widget in app.topLevelWidgets():
            if hasattr(widget, "scheduler"):
                # 执行立即检查
                widget.scheduler.check_now()
                self.logger.info("已触发立即检查")
                return

        self.logger.warning("未找到主窗口实例，无法执行立即检查")

    except Exception as e:
        self.logger.error(f"执行立即检查时出错: {str(e)}")
