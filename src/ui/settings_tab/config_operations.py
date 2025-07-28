# -*- coding: utf-8 -*-
"""
设置保存和重置操作
"""
from PySide6.QtWidgets import QMessageBox, QCheckBox

def save_settings(self):
    """保存设置"""
    # 对齐方式映射
    alignment_mapping = {
        "左对齐": "left",
        "居中对齐": "center",
        "右对齐": "right"
    }

    # 更新API令牌配置
    self.config.set("github.token", self.github_token_edit.text(), auto_save=False)

    # 更新Gitee API配置
    self.config.set("gitee.api_url", self.gitee_api_edit.text(), auto_save=False)
    self.config.set("gitee.token", self.gitee_token_edit.text(), auto_save=False)

    # 更新GitLab API配置
    self.config.set("gitlab.api_url", self.gitlab_api_edit.text(), auto_save=False)
    self.config.set("gitlab.token", self.gitlab_token_edit.text(), auto_save=False)

    # 更新NPM配置
    self.config.set("npm.registry", self.npm_registry_edit.text(), auto_save=False)

    # 更新PyPI配置
    self.config.set("pypi.api_url", self.pypi_api_edit.text(), auto_save=False)

    # 更新路径设置
    self.config.set("database.path", self.db_path_edit.text(), auto_save=False)
    self.config.set("database.backup_count", self.db_backup_count_spin.value(), auto_save=False)
    self.config.set("logging.path", self.log_path_edit.text(), auto_save=False)
    self.config.set("logging.file", self.log_file_edit.text(), auto_save=False)
    self.config.set("logging.level", self.log_level_combo.currentText(), auto_save=False)
    self.config.set("logging.console", self.log_console_check.isChecked(), auto_save=False)
    self.config.set("logging.max_size", self.log_max_size_spin.value() * 1048576, auto_save=False)
    self.config.set("logging.max_files", self.log_max_files_spin.value(), auto_save=False)

    # 更新系统设置
    self.config.set("system.temp_dir", self.temp_dir_edit.text(), auto_save=False)
    self.config.set("system.timeout", self.timeout_spin.value(), auto_save=False)
    self.config.set("system.concurrent_checks", self.concurrent_checks_spin.value(), auto_save=False)
    self.config.set("system.retry_count", self.retry_count_spin.value(), auto_save=False)
    self.config.set("system.show_tray", self.show_tray_check.isChecked(), auto_save=False)
    # 同时设置两个配置路径，保证向前和向后兼容
    close_action_value = self.close_action_combo.currentText()
    self.config.set("system.close_action", close_action_value, auto_save=False)
    self.config.set("ui.close_action", close_action_value, auto_save=False)
    self.config.set("system.package_manager", self.package_manager_combo.currentText(), auto_save=False)

    # 保存UI主题设置
    self.config.set("ui.theme", self.theme_combo.currentText(), auto_save=False)

    # 保存最小化通知设置
    self.config.set("ui.show_minimize_notification", self.show_minimize_notification_check.isChecked(), auto_save=False)

    # 更新工具设置
    self.config.set("tools.curl_path", self.curl_path_edit.text(), auto_save=False)

    # 从表格中读取列设置
    for i, column in enumerate(self.column_settings):
        # 获取对齐方式
        alignment_combo = self.columns_table.cellWidget(i, 2)
        self.config.set(f"ui.text_alignment.{column['config_key']}",
                       alignment_mapping[alignment_combo.currentText()], auto_save=False)

        # 获取是否显示
        show_check_widget = self.columns_table.cellWidget(i, 3)
        show_check = show_check_widget.findChild(QCheckBox)
        self.config.set(f"ui.show_{column['config_key']}", show_check.isChecked(), auto_save=False)

    # 更新字体大小
    self.config.set("ui.font_size", self.font_size_spin.value(), auto_save=False)

    # 更新更新设置
    self.config.set("update.auto_check", self.auto_check_update.isChecked(), auto_save=False)
    self.config.set("update.notify_on_update", self.notify_on_update.isChecked(), auto_save=False)
    self.config.set("update.check_interval", self.check_interval_spin.value() * 86400, auto_save=False)

    # 更新定时检查设置
    if hasattr(self, "enable_scheduler_check"):
        self._update_scheduler_settings()

    # 保存配置
    self.config._save_config()
    self.settings_saved.emit()
    self.logger.info("设置已保存")

def reset_settings(self):
    """重置为默认设置"""
    reply = QMessageBox.question(
        self,
        "重置设置",
        "确定要重置所有设置为默认值吗?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )

    if reply == QMessageBox.StandardButton.Yes:
        self.config.reset_to_defaults()
        self.init_ui()
        self.settings_reset.emit()
