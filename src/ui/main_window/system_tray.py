# -*- coding: utf-8 -*-
"""
系统托盘相关功能模块
"""
import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QAction

class SystemTrayMixin:
    """系统托盘相关的方法混入类"""

    def init_tray(self):
        """初始化系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)

        # 加载托盘图标
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "assets", "icon.png")
        self.tray_icon.setIcon(QIcon(icon_path if os.path.exists(icon_path) else ""))

        # 创建托盘菜单
        tray_menu = QMenu()

        # 添加菜单项
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.showNormal)

        # 添加版本检查菜单项
        check_aur_action = QAction("检查 AUR 版本更新", self)
        check_aur_action.triggered.connect(self._tray_check_aur)
        
        check_upstream_action = QAction("检查上游版本更新", self)
        check_upstream_action.triggered.connect(self._tray_check_upstream)
        
        check_both_action = QAction("检查 AUR 和上游版本更新", self)
        check_both_action.triggered.connect(self._tray_check_both)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close_application)

        # 添加菜单项到菜单
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(check_aur_action)
        tray_menu.addAction(check_upstream_action)
        tray_menu.addAction(check_both_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)

        # 设置托盘菜单
        self.tray_icon.setContextMenu(tray_menu)

        # 点击托盘图标的行为
        self.tray_icon.activated.connect(self.tray_icon_activated)

        # 显示托盘图标
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        """托盘图标被激活时的处理

        Args:
            reason: 激活原因
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # 单击托盘图标时，显示主窗口
            self.showNormal()
            self.activateWindow()

    def close_application(self):
        """关闭应用"""
        QApplication.quit()
        
    def _tray_check_aur(self):
        """从托盘菜单触发：检查 AUR 版本更新"""
        try:
            self.logger.info("从托盘菜单触发 AUR 版本检查")
            # 显示窗口
            self.showNormal()
            self.activateWindow()
            # 获取所有软件包并执行批量检查
            packages = self.db.get_all_packages()
            if not packages:
                self.logger.warning("没有找到任何软件包，无法执行检查")
                return
            # 初始化服务
            self._init_version_services()
            # 准备包名列表
            package_names = [p["name"] for p in packages if "name" in p]
            if package_names:
                from src.modules.async_executor import run_async_task
                run_async_task(
                    self.aur_checker.check_multiple_aur_versions(package_names),
                    self._on_batch_check_completed,
                    self._on_batch_check_error
                )
                self.logger.info(f"已提交 {len(package_names)} 个软件包的 AUR 版本检查任务")
            else:
                self.logger.warning("没有有效的软件包名称，无法执行检查")
        except Exception as e:
            self.logger.error(f"从托盘菜单触发 AUR 版本检查时出错: {str(e)}")
            
    def _tray_check_upstream(self):
        """从托盘菜单触发：检查上游版本更新"""
        try:
            self.logger.info("从托盘菜单触发上游版本检查")
            # 显示窗口
            self.showNormal()
            self.activateWindow()
            # 获取所有软件包并执行批量检查
            packages = self.db.get_all_packages()
            if not packages:
                self.logger.warning("没有找到任何软件包，无法执行检查")
                return
            # 初始化服务
            self._init_version_services()
            # 执行批量上游版本检查
            from src.modules.async_executor import run_async_task
            run_async_task(
                self.main_checker.check_multiple_upstream_versions(packages),
                self._on_batch_check_completed,
                self._on_batch_check_error
            )
            self.logger.info(f"已提交 {len(packages)} 个软件包的上游版本检查任务")
        except Exception as e:
            self.logger.error(f"从托盘菜单触发上游版本检查时出错: {str(e)}")
            
    def _tray_check_both(self):
        """从托盘菜单触发：检查 AUR 和上游版本更新"""
        try:
            self.logger.info("从托盘菜单触发 AUR 和上游版本检查")
            # 显示窗口
            self.showNormal()
            self.activateWindow()

            # 默认检查所有软件包
            try:
                # 获取所有软件包并选择它们
                self.select_all_packages()
                self.logger.info("已自动选择所有软件包")

                # 调用检查方法
                if hasattr(self, "check_selected_all_versions"):
                    # 检查所有版本（AUR和上游）
                    self.check_selected_all_versions()
                else:
                    self.logger.warning("没有找到 check_selected_all_versions 方法，无法执行检查")
            except Exception as inner_e:
                self.logger.error(f"自动选择所有软件包或检查版本时出错: {str(inner_e)}")
        except Exception as e:
            self.logger.error(f"从托盘菜单触发 AUR 和上游版本检查时出错: {str(e)}")
            
    def _delayed_upstream_check(self):
        """延迟执行的上游版本检查"""
        try:
            # 获取所有软件包
            packages = self.db.get_all_packages()
            if not packages:
                self.logger.warning("没有找到任何软件包，无法执行上游版本检查")
                return
            # 执行批量上游版本检查
            from src.modules.async_executor import run_async_task
            run_async_task(
                self.main_checker.check_multiple_upstream_versions(packages),
                self._on_batch_check_completed,
                self._on_batch_check_error
            )
            self.logger.info(f"已提交 {len(packages)} 个软件包的上游版本检查任务")
        except Exception as e:
            self.logger.error(f"延迟执行上游版本检查时出错: {str(e)}")

    def handle_close_event(self, event):
        """处理窗口关闭事件

        Args:
            event: 关闭事件
        """
        # 读取关闭行为配置，可能是"exit"或"minimize"
        close_action = self.config.get('ui.close_action', "minimize")
        # 兼容处理可能存在的旧配置值
        if close_action == "直接退出":
            close_action = "exit"
        elif close_action == "最小化到托盘":
            close_action = "minimize"
        self.logger.info(f"关闭行为配置: {close_action}")
        
        if close_action == "exit":
            # 配置为退出程序
            self.logger.info("配置为退出程序，执行退出")
            event.accept()
            QApplication.quit()
        else:
            # 配置为最小化到托盘
            if self.tray_icon.isVisible():
                self.logger.info("配置为最小化到托盘，执行隐藏")
                self.hide()
                event.ignore()
            else:
                # 托盘不可见时，无法最小化，只能退出
                self.logger.info("托盘不可见，执行退出")
                event.accept()
                QApplication.quit()

