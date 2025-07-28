# -*- coding: utf-8 -*-
"""定时检查方法模块"""

def _connect_scheduler_signals(self):
    """连接定时检查模块的信号"""
    try:
        # 连接AUR检查信号
        self.scheduler.aur_check_required.connect(self._handle_aur_scheduled_check)

        # 连接上游检查信号
        self.scheduler.upstream_check_required.connect(self._handle_upstream_scheduled_check)

        # 启动定时检查
        self.scheduler.start()

        self.logger.info("已连接定时检查信号")
    except Exception as e:
        self.logger.error(f"连接定时检查信号时出错: {str(e)}")

def _handle_aur_scheduled_check(self):
    """处理定时AUR检查"""
    self.logger.info("执行定时AUR版本检查")
    try:
        # 获取所有包信息
        packages = self.db.get_all_packages()

        if not packages:
            self.logger.warning("数据库中没有包信息，无法执行AUR检查")
            return

        # 初始化版本检查服务
        self._init_version_services()

        # 使用批量方法一次性检查所有AUR版本
        from src.modules.async_executor import run_async_task
        run_async_task(
            self.aur_checker.check_multiple_aur_versions([p["name"] for p in packages]),
            self._on_scheduled_aur_check_completed,
            self._on_scheduled_aur_check_error
        )

        if hasattr(self, "status_label"):
            self.status_label.setText("正在执行定时AUR版本检查...")

    except Exception as e:
        self.logger.error(f"执行定时AUR检查时出错: {str(e)}")

def _handle_upstream_scheduled_check(self):
    """处理定时上游检查"""
    self.logger.info("执行定时上游版本检查")
    try:
        # 获取所有包信息
        packages = self.db.get_all_packages()

        if not packages:
            self.logger.warning("数据库中没有包信息，无法执行上游检查")
            return

        # 初始化版本检查服务
        self._init_version_services()

        # 执行批量上游版本检查
        from src.modules.async_executor import run_async_task
        run_async_task(
            self.main_checker.check_multiple_upstream_versions(packages),
            self._on_scheduled_upstream_check_completed,
            self._on_scheduled_upstream_check_error
        )

        if hasattr(self, "status_label"):
            self.status_label.setText("正在执行定时上游版本检查...")

    except Exception as e:
        self.logger.error(f"执行定时上游检查时出错: {str(e)}")

def _on_scheduled_aur_check_completed(self, results):
    """定时AUR版本检查完成的回调"""
    if not results:
        self.logger.warning("AUR版本检查返回了空结果")
        return

    self.logger.info(f"定时AUR版本检查完成: {len(results)}个结果")

    # 更新UI
    self.refresh_package_list()

    # 更新状态栏
    if hasattr(self, "statusBar"):
        self.statusBar().showMessage(f"AUR版本检查完成: {len(results)}个软件包", 5000)

    # 更新标签
    if hasattr(self, "status_label"):
        self.status_label.setText("就绪")

def _on_scheduled_aur_check_error(self, error):
    """定时AUR版本检查错误的回调"""
    self.logger.error(f"定时AUR版本检查出错: {str(error)}")

    # 更新状态栏
    if hasattr(self, "statusBar"):
        self.statusBar().showMessage(f"AUR版本检查出错: {str(error)}", 5000)

    # 更新标签
    if hasattr(self, "status_label"):
        self.status_label.setText("就绪")

def _on_scheduled_upstream_check_completed(self, results):
    """定时上游版本检查完成的回调"""
    if not results:
        self.logger.warning("上游版本检查返回了空结果")
        return

    self.logger.info(f"定时上游版本检查完成: {len(results)}个结果")

    # 更新UI
    self.refresh_package_list()

    # 更新状态栏
    if hasattr(self, "statusBar"):
        self.statusBar().showMessage(f"上游版本检查完成: {len(results)}个软件包", 5000)

    # 更新标签
    if hasattr(self, "status_label"):
        self.status_label.setText("就绪")

def _on_scheduled_upstream_check_error(self, error):
    """定时上游版本检查错误的回调"""
    self.logger.error(f"定时上游版本检查出错: {str(error)}")

    # 更新状态栏
    if hasattr(self, "statusBar"):
        self.statusBar().showMessage(f"上游版本检查出错: {str(error)}", 5000)

    # 更新标签
    if hasattr(self, "status_label"):
        self.status_label.setText("就绪")
