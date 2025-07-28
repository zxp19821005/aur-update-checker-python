# -*- coding: utf-8 -*-
"""
日志设置相关功能
"""

def on_log_level_changed(self, level):
    """处理日志级别变化

    Args:
        level: 新的日志级别
    """
    # 设置日志显示级别
    self.logger.set_log_level(level)

    # 保存到配置
    try:
        if self.config:
            # 保存配置并立即刷新日志显示
            self.config.set("logging.level", level, auto_save=True)
            self.logger.info(f"日志显示级别已设置为: {level}")

        # 立即刷新日志显示
        self.refresh_logs()
    except Exception as e:
        print(f"保存日志级别设置时出错: {e}")
        # 捕获错误但继续刷新
        self.refresh_logs()

def on_log_lines_changed(self, value):
    """处理日志显示行数变化

    Args:
        value: 新的显示行数
    """
    try:
        if self.config:
            self.config.set("logging.display_lines", value, auto_save=True)
            self.logger.debug(f"日志显示行数已设置为: {value}")

        # 立即刷新日志显示
        self.refresh_logs()
    except Exception as e:
        print(f"保存日志行数设置时出错: {e}")

def on_colored_logs_changed(self, state):
    """处理彩色日志开关变化

    Args:
        state: 开关状态
    """
    is_checked = bool(state)
    try:
        if self.config:
            self.config.set("logging.colored", is_checked, auto_save=True)
            self.logger.debug(f"彩色日志已{'启用' if is_checked else '禁用'}")
        # 立即刷新日志显示
        self.refresh_logs()
    except Exception as e:
        print(f"保存彩色日志设置时出错: {e}")

def on_auto_scroll_changed(self, state):
    """处理自动滚动开关变化

    Args:
        state: 开关状态
    """
    is_checked = bool(state)
    try:
        if self.config:
            self.config.set("logging.auto_scroll", is_checked, auto_save=True)
            self.logger.debug(f"日志自动滚动已{'启用' if is_checked else '禁用'}")
    except Exception as e:
        print(f"保存自动滚动设置时出错: {e}")

def load_settings_from_config(self):
    """从配置加载设置"""
    if self.config:
        # 读取日志级别
        config_level = self.config.get("logging.level", "INFO")
        index = self.log_level_combo.findText(config_level)
        if index >= 0:
            self.log_level_combo.setCurrentIndex(index)

        # 读取日志显示行数
        log_lines = self.config.get("logging.display_lines", 1000)
        self.log_lines_spin.setValue(int(log_lines))

        # 读取是否启用彩色日志
        colored_logs = self.config.get("logging.colored", True)
        self.colored_logs_check.setChecked(bool(colored_logs))

        # 读取是否启用自动滚动
        auto_scroll = self.config.get("logging.auto_scroll", True)
        self.auto_scroll_check.setChecked(bool(auto_scroll))
    else:
        # 设置默认值
        config_level = "INFO"  # 默认值
        # 设置当前选择的日志级别
        index = self.log_level_combo.findText(config_level)
        if index >= 0:
            self.log_level_combo.setCurrentIndex(index)
