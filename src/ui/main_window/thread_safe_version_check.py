# -*- coding: utf-8 -*-
"""
线程安全的版本检查混入类，优化UI线程处理和后台任务管理
"""
from typing import Dict, List, Any, Optional, Callable, Union
from PySide6.QtCore import QObject, Signal, Slot, QTimer
import traceback
import time

from ..modules.thread_ui_helper import (
    ThreadSafeUI, 
    ui_thread_safe, 
    get_task_manager,
    TaskPriority,
    run_in_background
)

from ..modules.async_executor import run_async_task
from ..protocols import MainWindowInterface


class ThreadSafeVersionCheckMixin:
    """线程安全的版本检查混入类，优化后台任务处理流程"""

    def __init_thread_safe_check(self):
        """初始化线程安全版本检查功能"""
        # 获取全局任务管理器
        self.task_manager = get_task_manager(logger=self.logger)

        # 连接任务管理器信号
        self.task_manager.task_completed.connect(self._on_background_task_completed)
        self.task_manager.task_failed.connect(self._on_background_task_failed)

        # 创建UI更新的延迟计时器
        self._ui_update_timer = QTimer()
        self._ui_update_timer.setSingleShot(True)
        self._ui_update_timer.setInterval(100)  # 100ms延迟
        self._ui_update_timer.timeout.connect(self._update_ui_from_pending)

        # 待更新包的列表
        self._pending_ui_updates = set()

        # 记录正在进行的检查
        self._active_checks = {}  # package_name -> task_id

    @ui_thread_safe
    def check_package_version(self, name=None, upstream_url=None, checker_type=None, version_extract_key=None):
        """线程安全的检查单个软件包版本

        Args:
            name: 包名
            upstream_url: 上游URL
            checker_type: 检查器类型
            version_extract_key: 版本提取键
        """
        self.logger.info(f"开始检查软件包 {name} 版本")
        self._init_version_services()

        # 防止重复检查同一个包
        if name in self._active_checks:
            self.logger.info(f"软件包 {name} 已在检查队列中，跳过")
            return

        # 准备包信息
        package_info = {
            "name": name,
            "upstream_url": upstream_url
        }

        # 尝试从数据库获取完整的包信息
        try:
            db_package = self.db.get_package_by_name(name)
            if db_package:
                # 合并信息
                if not upstream_url and "upstream_url" in db_package:
                    package_info["upstream_url"] = db_package["upstream_url"]

                # 检查器类型
                if not checker_type and "checker_type" in db_package:
                    checker_type = db_package["checker_type"]
                    package_info["checker_type"] = checker_type
                    self.logger.debug(f"从数据库获取到checker_type: {checker_type}")

                # 版本提取键
                if not version_extract_key and "version_extract_key" in db_package:
                    version_extract_key = db_package["version_extract_key"]
                    package_info["version_extract_key"] = version_extract_key
                    self.logger.debug(f"从数据库获取到version_extract_key: {version_extract_key}")
        except Exception as e:
            self.logger.warning(f"从数据库获取包信息失败: {str(e)}")

        # 添加checker_type(如果存在)
        if checker_type:
            package_info["checker_type"] = checker_type

        # 添加version_extract_key(如果存在)
        if version_extract_key:
            package_info["version_extract_key"] = version_extract_key

        # 在UI中显示检查状态
        self._update_package_check_status(name, "正在检查...")

        # 在后台执行版本检查
        task_id = self.task_manager.schedule_task(
            self._do_check_version,
            package_info,
            task_id=f"check_{name}_{time.time()}",
            priority=TaskPriority.NORMAL
        )

        # 记录活动检查
        self._active_checks[name] = task_id

    def _do_check_version(self, package_info):
        """执行版本检查的后台任务

        这个方法将在工作线程中执行

        Args:
            package_info: 包信息字典

        Returns:
            dict: 版本检查结果
        """
        try:
            # 调用主检查器的检查方法
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(
                    self.main_checker.check_single_upstream_version(package_info)
                )
                return result
            finally:
                loop.close()

        except Exception as e:
            self.logger.error(f"检查版本出错: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return {
                "name": package_info.get("name", "unknown"),
                "success": False,
                "message": str(e)
            }

    @Slot(str, object)
    def _on_background_task_completed(self, task_id, result):
        """后台任务完成时的处理

        Args:
            task_id: 任务ID
            result: 任务结果
        """
        # 查找对应的包名
        package_name = None
        for name, tid in list(self._active_checks.items()):
            if tid == task_id:
                package_name = name
                del self._active_checks[name]
                break

        if not package_name:
            return

        # 处理结果
        if isinstance(result, dict) and "name" in result:
            # 更新数据库
            if result.get("success") and result.get("upstream_version"):
                try:
                    self.db.update_upstream_version(
                        result["name"],
                        result["upstream_version"]
                    )
                    self.logger.info(f"已更新 {result['name']} 的上游版本: {result['upstream_version']}")
                except Exception as e:
                    self.logger.error(f"更新数据库时出错: {str(e)}")

            # 安排UI更新
            self._schedule_ui_update(result["name"])

    @Slot(str, str)
    def _on_background_task_failed(self, task_id, error_msg):
        """后台任务失败时的处理

        Args:
            task_id: 任务ID
            error_msg: 错误消息
        """
        # 查找对应的包名
        package_name = None
        for name, tid in list(self._active_checks.items()):
            if tid == task_id:
                package_name = name
                del self._active_checks[name]
                break

        if not package_name:
            return

        # 显示错误状态
        self._update_package_check_status(package_name, f"失败: {error_msg}")

        # 安排UI更新
        self._schedule_ui_update(package_name)

    def _schedule_ui_update(self, package_name):
        """安排UI更新

        Args:
            package_name: 包名
        """
        # 添加到待更新列表
        self._pending_ui_updates.add(package_name)

        # 如果计时器未运行，启动它
        if not self._ui_update_timer.isActive():
            self._ui_update_timer.start()

    @ui_thread_safe
    def _update_ui_from_pending(self):
        """从待更新列表中更新UI"""
        if not self._pending_ui_updates:
            return

        # 更新所有待更新的包
        for package_name in list(self._pending_ui_updates):
            self.update_package_after_check(package_name)

        # 清空待更新列表
        self._pending_ui_updates.clear()

        # 刷新过滤
        self.filter_packages()

    @ui_thread_safe
    def _update_package_check_status(self, package_name, status):
        """更新包的检查状态

        Args:
            package_name: 包名
            status: 状态文本
        """
        # 查找表格中对应的行
        for row in range(self.packages_table.rowCount()):
            name_item = self.packages_table.item(row, 1)  # 名称列
            if name_item and name_item.text() == package_name:
                # 更新状态列
                status_item = self.packages_table.item(row, 4)
                if status_item:
                    status_item.setText(status)
                break

    @run_in_background
    def check_all_upstream_versions(self, packages=None):
        """在后台线程中检查所有上游版本

        Args:
            packages: 包列表，如果为None则从数据库获取
        """
        self.logger.info("开始批量检查上游版本")
        self._init_version_services()

        # 获取包列表
        if packages is None:
            try:
                packages = self.db.get_all_packages()
            except Exception as e:
                self.logger.error(f"获取包列表失败: {str(e)}")
                return

        # 显示进度
        ThreadSafeUI.run_in_main_thread(self._show_progress_dialog, "检查上游版本", 0, len(packages))

        # 批量检查
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                results = loop.run_until_complete(
                    self.main_checker.check_multiple_upstream_versions(packages)
                )

                # 更新进度
                for i, result in enumerate(results):
                    ThreadSafeUI.run_in_main_thread(self._update_progress_dialog, i + 1, len(packages))

                    # 处理结果
                    if result.get("success") and "name" in result:
                        # 安排UI更新
                        self._schedule_ui_update(result["name"])
            finally:
                loop.close()

            # 完成后隐藏进度对话框
            ThreadSafeUI.run_in_main_thread(self._hide_progress_dialog)

            # 通知检查完成
            ThreadSafeUI.run_in_main_thread(self._notify_batch_check_completed, len(results))

        except Exception as e:
            self.logger.error(f"批量检查出错: {str(e)}")
            self.logger.debug(traceback.format_exc())

            # 隐藏进度对话框并显示错误
            ThreadSafeUI.run_in_main_thread(self._hide_progress_dialog)
            ThreadSafeUI.run_in_main_thread(self._show_error_message, "批量检查错误", str(e))

    # 进度对话框相关方法
    @ui_thread_safe
    def _show_progress_dialog(self, title, current, total):
        """显示进度对话框"""
        from PySide6.QtWidgets import QProgressDialog

        if not hasattr(self, '_progress_dialog') or self._progress_dialog is None:
            self._progress_dialog = QProgressDialog(self)
            self._progress_dialog.setWindowTitle(title)
            self._progress_dialog.setCancelButton(None)
            self._progress_dialog.setMinimumDuration(500)
            self._progress_dialog.setRange(0, total)
            self._progress_dialog.setValue(current)
            self._progress_dialog.show()
        else:
            self._progress_dialog.setWindowTitle(title)
            self._progress_dialog.setRange(0, total)
            self._progress_dialog.setValue(current)
            if not self._progress_dialog.isVisible():
                self._progress_dialog.show()

    @ui_thread_safe
    def _update_progress_dialog(self, current, total):
        """更新进度对话框"""
        if hasattr(self, '_progress_dialog') and self._progress_dialog is not None:
            self._progress_dialog.setRange(0, total)
            self._progress_dialog.setValue(current)

    @ui_thread_safe
    def _hide_progress_dialog(self):
        """隐藏进度对话框"""
        if hasattr(self, '_progress_dialog') and self._progress_dialog is not None:
            self._progress_dialog.hide()

    @ui_thread_safe
    def _show_error_message(self, title, message):
        """显示错误消息"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, title, message)

    @ui_thread_safe
    def _notify_batch_check_completed(self, count):
        """通知批量检查完成"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "批量检查完成", f"成功检查了 {count} 个软件包的上游版本。")


# 导入需要的模块
import asyncio
