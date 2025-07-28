# -*- coding: utf-8 -*-
"""
日志操作相关功能
"""
from PySide6.QtCore import QTimer

def refresh_logs(self):
    """刷新日志显示"""
    if not hasattr(self, 'logs_text') or not self.logs_text:
        return

    try:
        # 获取当前选择的日志级别
        selected_level = self.log_level_combo.currentText() if hasattr(self, "log_level_combo") else None

        # 获取当前设置的显示行数
        log_lines = self.log_lines_spin.value() if hasattr(self, "log_lines_spin") else 1000

        # 获取日志，根据选择的日志级别过滤，并使用用户设置的行数限制
        logs = self.logger.get_recent_logs(log_lines, min_level=selected_level)

        # 如果没有日志，显示提示信息
        if not logs:
            # 清除之前的内容
            if hasattr(self, "colored_logs_check") and self.colored_logs_check.isChecked():
                self.logs_text.setHtml('<html><body><span style="color: #777; font-style: italic;">没有符合当前过滤条件的日志记录</span></body></html>')
            else:
                self.logs_text.setPlainText("没有符合当前过滤条件的日志记录")
            return

        # 检查是否启用彩色日志
        use_colored_logs = self.colored_logs_check.isChecked()

        # 使用导入的格式化函数
        from .log_formatter import format_log

        # 构建日志文本
        log_entries = [format_log(log, use_colored_logs) for log in reversed(logs)]

        # 根据是否启用彩色日志，选择HTML或纯文本格式
        if use_colored_logs:
            logs_content = "<html><body>" + "<br>".join(log_entries) + "</body></html>"
        else:
            logs_content = "\n".join(log_entries)

        # 检查是否需要更新（减少不必要的UI操作）
        # 由于HTML格式的差异，我们使用日志条数来决定是否更新
        if hasattr(self, "last_log_count") and self.last_log_count == len(logs):
            return

        # 记录当前日志条数
        self.last_log_count = len(logs)

        # 保存滚动位置
        scrollbar = self.logs_text.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 10

        # 检查是否启用自动滚动
        auto_scroll = hasattr(self, "auto_scroll_check") and self.auto_scroll_check.isChecked()

        # 根据是否启用彩色日志选择合适的文本设置方法
        if use_colored_logs:
            self.logs_text.setHtml(logs_content)
        else:
            self.logs_text.setPlainText(logs_content)

        # 根据设置决定是否自动滚动
        if auto_scroll or at_bottom:
            # 滚动到底部
            QTimer.singleShot(0, lambda: scrollbar.setValue(scrollbar.maximum()))

    except Exception as e:
        import traceback
        traceback.print_exc()

def clear_logs(self):
    """清除日志显示"""
    self.logs_text.clear()

    # 重置日志计数，确保下次刷新时会显示新日志
    self.last_log_count = 0

    # 通知可能的监听者日志已被清除
    self.logs_cleared.emit()

    # 记录日志已清除（不会立即显示在UI中）
    self.logger.info("日志显示已清除")

    # 不再自动刷新日志，让日志面板保持清空状态
    # 直到用户手动刷新或定时器触发下一次刷新
