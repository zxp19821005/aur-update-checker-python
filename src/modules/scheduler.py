# -*- coding: utf-8 -*-
"""
定时检查模块，负责管理定时检查任务
"""
from datetime import datetime, timedelta
from PySide6.QtCore import QObject, QTimer, Signal

class SchedulerModule(QObject):
    """定时检查模块，负责管理定时检查任务"""
    # 信号定义
    aur_check_required = Signal()  # AUR检查信号
    upstream_check_required = Signal()  # 上游检查信号

    def __init__(self, logger, config):
        """初始化定时检查模块

        Args:
            logger: 日志模块
            config: 配置模块
        """
        super().__init__()
        self.logger = logger
        self.config = config

        # 初始化计时器
        self.aur_timer = QTimer(self)
        self.upstream_timer = QTimer(self)

        # 连接计时器信号
        self.aur_timer.timeout.connect(self._on_aur_timer_timeout)
        self.upstream_timer.timeout.connect(self._on_upstream_timer_timeout)

        # 存储上次检查时间
        self.last_aur_check = None
        self.last_upstream_check = None

        # 初始化状态
        self.is_initialized = False

        # 应用配置
        self.apply_config()

        self.logger.info("定时检查模块初始化完成")

    def apply_config(self):
        """应用配置"""
        # 读取配置项
        scheduler_config = self.config.get("scheduler", {})
        self.enabled = scheduler_config.get("enabled", True)
        self.aur_check_interval = scheduler_config.get("aur_check_interval", 24)  # 单位：小时
        self.upstream_check_interval = scheduler_config.get("upstream_check_interval", 48)  # 单位：小时
        self.check_on_startup = scheduler_config.get("check_on_startup", False)  # 默认不在启动时检查
        self.notification_enabled = scheduler_config.get("notification_enabled", True)

        # 将小时转换为毫秒
        aur_interval_ms = self.aur_check_interval * 60 * 60 * 1000
        upstream_interval_ms = self.upstream_check_interval * 60 * 60 * 1000

        self.logger.debug(f"设置AUR检查间隔: {self.aur_check_interval}小时 ({aur_interval_ms}毫秒)")
        self.logger.debug(f"设置上游检查间隔: {self.upstream_check_interval}小时 ({upstream_interval_ms}毫秒)")

        # 配置计时器
        if self.enabled:
            # 停止现有计时器
            self.aur_timer.stop()
            self.upstream_timer.stop()

            # 设置新的间隔
            self.aur_timer.setInterval(aur_interval_ms)
            self.upstream_timer.setInterval(upstream_interval_ms)

            # 启动计时器
            self.aur_timer.start()
            self.upstream_timer.start()

            self.logger.info("已启动定时检查")
        else:
            # 停止计时器
            self.aur_timer.stop()
            self.upstream_timer.stop()
            self.logger.info("定时检查已禁用")

    def start(self):
        """启动定时检查"""
        if not self.enabled:
            self.logger.info("定时检查已禁用，不启动")
            return

        # 检查是否需要在启动时执行检查
        if self.check_on_startup:
            self.logger.info("启动时检查已启用，但默认不会立即执行")
            # 在这里我们不自动执行检查，改为让用户手动触发
            # 或者等待定时器触发

        # 启动计时器
        self.aur_timer.start()
        self.upstream_timer.start()

        self.is_initialized = True
        self.logger.info("定时检查已启动")

    def stop(self):
        """停止定时检查"""
        self.aur_timer.stop()
        self.upstream_timer.stop()
        self.logger.info("定时检查已停止")

    def check_now(self, check_type="all"):
        """立即执行检查

        Args:
            check_type: 检查类型，可选值：all, aur, upstream
        """
        if check_type == "all" or check_type == "aur":
            self.aur_check_required.emit()
            self.last_aur_check = datetime.now()
            self.logger.info("手动触发 AUR 版本检查")

        if check_type == "all" or check_type == "upstream":
            self.upstream_check_required.emit()
            self.last_upstream_check = datetime.now()
            self.logger.info("手动触发上游版本检查")

    def get_next_check_time(self, check_type="all"):
        """获取下次检查时间

        Args:
            check_type: 检查类型，可选值：all, aur, upstream

        Returns:
            dict: 包含下次检查时间的字典
        """
        result = {}

        if check_type == "all" or check_type == "aur":
            if self.last_aur_check:
                next_aur = self.last_aur_check + timedelta(hours=self.aur_check_interval)
                result["aur"] = next_aur
            else:
                result["aur"] = None

        if check_type == "all" or check_type == "upstream":
            if self.last_upstream_check:
                next_upstream = self.last_upstream_check + timedelta(hours=self.upstream_check_interval)
                result["upstream"] = next_upstream
            else:
                result["upstream"] = None

        return result

    def _startup_check(self):
        """启动时执行检查"""
        self.logger.info("执行启动时检查")
        self.check_now()

    def _on_aur_timer_timeout(self):
        """AUR计时器超时处理"""
        self.logger.info(f"AUR检查计时器触发，间隔: {self.aur_check_interval}小时")
        self.aur_check_required.emit()
        self.last_aur_check = datetime.now()

        if self.notification_enabled:
            self._show_check_notification("AUR")

    def _on_upstream_timer_timeout(self):
        """上游计时器超时处理"""
        self.logger.info(f"上游检查计时器触发，间隔: {self.upstream_check_interval}小时")
        self.upstream_check_required.emit()
        self.last_upstream_check = datetime.now()

        if self.notification_enabled:
            self._show_check_notification("上游")

    def _show_check_notification(self, check_type):
        """显示检查通知

        Args:
            check_type: 检查类型
        """
        try:
            # 尝试获取系统托盘实例
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()

            # 寻找主窗口实例
            main_window = None
            for widget in app.topLevelWidgets():
                if hasattr(widget, "tray_icon") and widget.tray_icon:
                    if widget.tray_icon.isVisible():
                        widget.tray_icon.showMessage(
                            f"{check_type}版本检查",
                            f"正在执行定时{check_type}版本检查...",
                            widget.tray_icon.Information,
                            3000
                        )
                        return

            self.logger.debug(f"未找到可见的系统托盘图标，无法显示{check_type}版本检查通知")

        except Exception as e:
            self.logger.error(f"显示通知出错: {str(e)}")
