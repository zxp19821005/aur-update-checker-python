# -*- coding: utf-8 -*-
"""
主窗口模块，整合其他所有模块
"""
import os
from PySide6.QtWidgets import QMainWindow, QMessageBox, QWidget, QVBoxLayout, QTabWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

# 导入模块
from ...modules.aur_checker import AurCheckerModule
from ...modules.scheduler import SchedulerModule
from .ui_buttons import UIButtons

# 导入子模块
from .ui_init import UIInitMixin
from .package_operations import PackageOperationsMixin
from .version_check import VersionCheckMixin
from .update_ui import UpdateUIMixin
from .system_tray import SystemTrayMixin
from .package_filtering import PackageFiltering
from .table_operations import TableOperations
from .table_sort import TableSortMixin

# 导入自定义标签页
from ..settings_tab import SettingsTab
from ..logs_tab import LogsTab


class MainWindowWrapper(QMainWindow, PackageOperationsMixin, UpdateUIMixin, SystemTrayMixin, VersionCheckMixin, TableSortMixin):

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
        self.load_packages()

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
        self.load_packages()

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

    """
    主窗口类，整合所有功能模块
    """

    def __init__(self, config, db, logger):
        """初始化主窗口

        Args:
            config: 配置对象
            db: 数据库对象
            logger: 日志对象
        """
        super().__init__()

        # 存储依赖对象
        self.config = config
        self.db = db
        self.logger = logger

        # 初始化UI之前的预处理
        self.logger.debug("开始初始化主窗口UI")

        # 设置初始状态
        self.packages = []
        self.filtered_packages = []

        # 初始化检查器模块
        self.aur_checker = AurCheckerModule(logger, db)

        # 初始化定时检查模块
        self.scheduler = SchedulerModule(logger, config)

        # 设置主窗口基本属性
        self.setWindowTitle("AUR 更新检查器")
        self.resize(1200, 800)

        # 初始化UI组件
        self.init_ui()
        self.init_packages_tab()
        self.init_signals()
        self.init_tray()

        # 初始化按钮样式（在初始化UI组件之后）
        UIButtons.init_colored_buttons(self)

        # 从配置读取窗口大小和状态
        self.restore_window_state()

        # 连接定时检查信号
        self._connect_scheduler_signals()

    def init_ui(self):
        """初始化主界面布局"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 创建并添加软件包标签页
        self.packages_tab = QWidget()
        self.tab_widget.addTab(self.packages_tab, "软件包")

        # 添加日志标签页
        self.logs_tab = LogsTab(self.logger, config=self.config, parent=self)
        self.tab_widget.addTab(self.logs_tab, "日志")

        # 添加设置标签页
        self.settings_tab = SettingsTab(self.config, self.logger)
        self.tab_widget.addTab(self.settings_tab, "设置")

    def init_packages_tab(self):
        """初始化软件包标签页，使用UIInitMixin中的方法"""
        UIInitMixin.init_packages_tab(self)

    def init_signals(self):
        """初始化信号连接"""
        if hasattr(self, "search_edit"):
            self.search_edit.textChanged.connect(self.on_search_text_changed)

        if hasattr(self, "show_outdated_check"):
            self.show_outdated_check.stateChanged.connect(self.on_outdated_filter_changed)

        if hasattr(self, "refresh_button"):
            self.refresh_button.clicked.connect(self.load_packages)

    def on_search_text_changed(self, text):
        """处理搜索框文本变化

        为避免多次触发过滤，使用计时器延迟执行过滤
        """
        # 忽略空字符串，避免在清空搜索框时触发
        self._setup_delayed_filter("_search_timer", 500, True)

    def on_outdated_filter_changed(self, state):
        """处理'仅显示过时'复选框状态变化

        为避免多次触发过滤，使用计时器延迟执行过滤
        """
        is_checked = bool(state)
        self.logger.debug(f"过滤条件改变: 仅显示过时 = {is_checked}")
        self._setup_delayed_filter("_filter_timer", 500, True)

    def _setup_delayed_filter(self, timer_name, delay_ms, has_filter):
        """设置延时过滤器，减少代码重复和多次触发

        只保留一个活动的过滤计时器，所有过滤请求合并到这个计时器
        """
        # 如果已有全局过滤计时器，先停止它
        for timer_attr in ["_search_timer", "_filter_timer", "_global_filter_timer"]:
            if hasattr(self, timer_attr):
                try:
                    getattr(self, timer_attr).stop()
                    self.logger.debug(f"停止了计时器 {timer_attr}")
                except Exception:
                    pass

        # 创建新的全局过滤计时器
        global_timer = QTimer()
        global_timer.setSingleShot(True)
        setattr(self, "_global_filter_timer", global_timer)

        # 设置唯一的过滤函数
        def do_filter():
            self.logger.debug("执行计时器触发的过滤")
            # 禁用所有信号，避免重复触发
            if hasattr(self, "search_edit"):
                self.search_edit.blockSignals(True)
            if hasattr(self, "show_outdated_check"):  
                self.show_outdated_check.blockSignals(True)

            try:
                # 执行一次过滤
                self.filter_packages(update_table=True)
            finally:
                # 恢复信号
                if hasattr(self, "search_edit"):
                    self.search_edit.blockSignals(False)
                if hasattr(self, "show_outdated_check"):
                    self.show_outdated_check.blockSignals(False)

        # 连接函数并启动计时器
        global_timer.timeout.connect(do_filter)
        global_timer.start(delay_ms)
        self.logger.debug(f"设置了新的过滤计时器，延迟 {delay_ms}ms")

    def _apply_column_visibility(self):
        """应用列可见性设置"""
        ui_config = self.config.get("ui", {})
        columns = [
            (1, "show_name", True),               # 名称列
            (2, "show_aur_version", True),        # AUR版本列
            (3, "show_upstream_version", True),   # 上游版本列
            (4, "show_status", False),            # 状态列
            (5, "show_aur_check_time", True),     # AUR检查时间列
            (6, "show_upstream_check_time", True),# 上游检查时间列
            (7, "show_checker_type", True),       # 检查器类型列
            (8, "show_upstream_url", False),      # 上游URL列
            (9, "show_notes", False)              # 备注列
        ]

        # 应用所有列的可见性设置
        for idx, key, default in columns:
            self.packages_table.setColumnHidden(idx, not bool(ui_config.get(key, default)))

    def load_packages(self):
        """异步加载软件包列表"""
        self.logger.info("开始异步加载软件包列表")

        # 显示加载状态
        if hasattr(self, "loading_progress"):
            self.loading_progress.setVisible(True)
            self.loading_progress.setValue(0)
            self.status_label.setText("正在加载数据...")

        # 使用QTimer.singleShot模拟异步加载
        from PySide6.QtCore import QTimer

        def async_load():
            try:
                # 从数据库获取软件包数据
                self.packages = self.db.get_all_packages()

                if not self.packages:
                    self.logger.error("数据库返回的包列表为空！")
                    return

                self.logger.info(f"从数据库加载了 {len(self.packages)} 个包")

                # 更新加载进度
                if hasattr(self, "loading_progress"):
                    self.loading_progress.setValue(50)

                # 检查版本信息，确保每个包都有版本字段
                for pkg in self.packages:
                    if not pkg.get("aur_version") and not pkg.get("version"):
                        # 如果没有版本信息但有上游版本，使用上游版本作为本地版本
                        if pkg.get("upstream_version"):
                            pkg["version"] = pkg["upstream_version"]

                # 设置过滤后的包列表
                self.filtered_packages = self.packages.copy()

                # 更新加载进度
                if hasattr(self, "loading_progress"):
                    self.loading_progress.setValue(80)

                # 更新表格
                self.update_packages_table()

                # 完成加载
                if hasattr(self, "loading_progress"):
                    self.loading_progress.setValue(100)
                    QTimer.singleShot(500, lambda: self.loading_progress.setVisible(False))
                    self.status_label.setText("就绪")

            except Exception as e:
                self.logger.error(f"加载数据时出错: {str(e)}")
                if hasattr(self, "loading_progress"):
                    self.loading_progress.setVisible(False)
                self.status_label.setText(f"加载失败: {str(e)}")

        # 启动异步加载
        QTimer.singleShot(10, async_load)

    def filter_packages(self, update_table=True):
        """根据过滤条件筛选软件包"""
        # 获取搜索框文本和过滤条件
        search_text = self.search_edit.text().lower() if hasattr(self, "search_edit") else ""
        show_outdated = self.show_outdated_check.isChecked() if hasattr(self, "show_outdated_check") else False

        # 记录过滤条件
        self.logger.info(f"应用过滤: 搜索文本='{search_text}', 仅显示过时={show_outdated}")

        # 确保packages列表存在
        if not hasattr(self, "packages") or not self.packages:
            self.logger.warning("没有可用的软件包列表")
            return

        # 应用过滤逻辑
        self.filtered_packages = []
        for pkg in self.packages:
            name = pkg.get("name", "").lower()

            # 搜索名称过滤
            if search_text and search_text not in name:
                continue

            # 过时包过滤
            if show_outdated:
                aur_version = pkg.get("aur_version")
                upstream_version = pkg.get("upstream_version")

                # 跳过没有两个版本或版本相同的包
                if not (aur_version and upstream_version and aur_version != upstream_version):
                    continue

            # 通过所有过滤条件，添加到结果列表
            self.filtered_packages.append(pkg)

        # 如果过滤后列表为空但原始列表有数据，给出提示
        if not self.filtered_packages and self.packages:
            self.logger.warning(f"过滤后没有匹配的软件包 (过滤条件: '{search_text}', 仅过时={show_outdated})")

        # 更新表格显示
        if update_table:
            self.update_packages_table()

    def update_packages_table(self):
        """更新软件包表格的内容"""
        # 记录数据情况
        self.logger.debug(f"更新表格: 原始包:{len(self.packages)}, 过滤后:{len(self.filtered_packages)}")

        # 如果过滤后的列表为空但原始列表有数据，重置过滤
        if self.packages and not self.filtered_packages:
            self.logger.warning("过滤列表为空但原始列表有数据，重置过滤")
            self.filtered_packages = self.packages.copy()

        # 清空表格并重设行数
        self.packages_table.setRowCount(0)
        self.packages_table.setRowCount(len(self.filtered_packages))

        # 应用列可见性设置
        self._apply_column_visibility()

        # 填充表格数据
        for row, pkg in enumerate(self.filtered_packages):
            self._create_table_row(row, pkg)

    def update_package_status(self, row):
        """更新特定行的包状态信息"""
        TableOperations.update_single_package_status(self, row)

    def update_package_after_check(self, package_name):
        """版本检查完成后更新包信息

        Args:
            package_name: 包名称
        """
        # 从数据库重新获取最新数据
        updated_pkg = self.db.get_package_by_name(package_name)
        if not updated_pkg:
            self.logger.warning(f"无法获取包 {package_name} 的最新数据")
            return

        # 更新内存中的包数据
        for i, pkg in enumerate(self.packages):
            if pkg.get("name") == package_name:
                self.packages[i] = updated_pkg
                break

        # 更新过滤后的包列表
        for i, pkg in enumerate(self.filtered_packages):
            if pkg.get("name") == package_name:
                self.filtered_packages[i] = updated_pkg
                break

        # 更新UI表格
        for row in range(self.packages_table.rowCount()):
            name_item = self.packages_table.item(row, 1)
            if name_item and name_item.text() == package_name:
                self._create_table_row(row, updated_pkg)
                break

    def check_all_packages(self, check_type="aur"):
        """检查所有软件包"""
        if check_type == "aur":
            self.check_all_aur_versions()
        elif check_type == "upstream":
            self.check_all_upstream_versions()
        else:
            self.check_all_versions()

    def reload_packages(self):
        """重新加载软件包列表，同时保持当前的过滤条件"""
        self.logger.info("准备重新加载包数据以更新UI，并保持当前过滤条件")

        # 保存当前的搜索文本和过滤条件
        search_text = ""
        show_outdated = False

        if hasattr(self, "search_edit") and self.search_edit:
            search_text = self.search_edit.text()

        if hasattr(self, "show_outdated_check") and self.show_outdated_check:
            show_outdated = self.show_outdated_check.isChecked()

        self.logger.debug(f"保存当前过滤条件: 搜索文本='{search_text}', 仅显示过时={show_outdated}")

        # 断开所有过滤相关的信号，以避免重复触发
        had_search_connection = False
        had_outdated_connection = False

        if hasattr(self, "search_edit") and self.search_edit:
            # 临时断开文本变化信号
            try:
                # 检查信号是否已连接的方法
                receivers = self.search_edit.receivers(self.search_edit.textChanged)
                if receivers > 0:
                    self.search_edit.textChanged.disconnect(self.on_search_text_changed)
                    had_search_connection = True
                    self.logger.debug("已断开搜索框信号")
                else:
                    self.logger.debug("搜索框信号未连接，无需断开")
            except Exception as e:
                self.logger.debug(f"搜索框信号断开时出错: {str(e)}")

        if hasattr(self, "show_outdated_check") and self.show_outdated_check:
            # 临时断开复选框状态变化信号
            try:
                # 检查信号是否已连接的方法
                receivers = self.show_outdated_check.receivers(self.show_outdated_check.stateChanged)
                if receivers > 0:
                    self.show_outdated_check.stateChanged.disconnect(self.on_outdated_filter_changed)
                    had_outdated_connection = True
                    self.logger.debug("已断开过滤复选框信号")
                else:
                    self.logger.debug("过滤复选框信号未连接，无需断开")
            except Exception as e:
                self.logger.debug(f"过滤复选框信号断开时出错: {str(e)}")

        # 清空搜索框和复选框
        if hasattr(self, "search_edit") and search_text:
            self.search_edit.setText("")

        if hasattr(self, "show_outdated_check") and show_outdated:
            self.show_outdated_check.setChecked(False)

        # 重新加载所有包
        self.load_packages()

        # 使用延时器确保UI更新完成后再应用过滤
        from PySide6.QtCore import QTimer

        def apply_filters():
            self.logger.info(f"开始应用保存的过滤条件: 搜索文本='{search_text}', 仅显示过时={show_outdated}")

            try:
                # 先手动应用过滤
                if search_text or show_outdated:
                    # 直接修改搜索框和复选框，此时信号已断开，不会触发过滤
                    if hasattr(self, "search_edit") and search_text:
                        self.search_edit.setText(search_text)
                        self.logger.debug(f"已设置搜索框文本: {search_text}")

                    if hasattr(self, "show_outdated_check") and show_outdated:
                        self.show_outdated_check.setChecked(show_outdated)
                        self.logger.debug(f"已设置'仅显示过时': {show_outdated}")

                    # 手动触发一次过滤
                    self.logger.debug("手动执行过滤操作")
                    # 直接调用过滤方法，不经过延时处理
                    self.filter_packages(update_table=True)

                # 重新连接信号
                if hasattr(self, "search_edit") and had_search_connection:
                    self.search_edit.textChanged.connect(self.on_search_text_changed)
                    self.logger.debug("已重新连接搜索框信号")

                if hasattr(self, "show_outdated_check") and had_outdated_connection:
                    self.show_outdated_check.stateChanged.connect(self.on_outdated_filter_changed)
                    self.logger.debug("已重新连接过滤复选框信号")

            except Exception as e:
                self.logger.error(f"恢复过滤条件时出错: {str(e)}")
                # 确保信号被重新连接
                if hasattr(self, "search_edit") and had_search_connection:
                    try:
                        self.search_edit.textChanged.connect(self.on_search_text_changed)
                    except Exception:
                        pass

                if hasattr(self, "show_outdated_check") and had_outdated_connection:
                    try:
                        self.show_outdated_check.stateChanged.connect(self.on_outdated_filter_changed)
                    except Exception:
                        pass

        # 延时300毫秒应用过滤条件，确保UI已完全更新
        QTimer.singleShot(300, apply_filters)

    def restore_window_state(self):
        """从配置文件恢复窗口状态"""
        window_config = self.config.get("window", {})
        self.resize(
            window_config.get("width", 1200),
            window_config.get("height", 800)
        )

        x = window_config.get("x")
        y = window_config.get("y")
        if x is not None and y is not None:
            self.move(x, y)

    def save_window_state(self):
        """保存窗口状态到配置文件"""
        size = self.size()
        pos = self.pos()

        window_config = {
            "width": size.width(),
            "height": size.height(),
            "x": pos.x(),
            "y": pos.y()
        }

        try:
            if self.config:
                self.config["window"] = window_config
                self.logger.debug("窗口配置已保存")
            else:
                self.logger.warning("配置模块未初始化，窗口配置未保存")
        except Exception as e:
            self.logger.error(f"保存窗口配置时出错: {str(e)}")

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 保存窗口状态
        self.save_window_state()

        # 获取关闭行为设置
        close_action = self.config.get("ui", {}).get("close_action", "minimize")
        
        # 如果设置为最小化并且有系统托盘，则最小化到托盘
        if close_action == "minimize" and hasattr(self, "tray_icon") and self.tray_icon is not None:
            # 显示通知（如果启用）
            if self.config.get("ui", {}).get("show_minimize_notification", True):
                self.tray_icon.showMessage(
                    "AUR Update Checker", 
                    "应用已最小化到系统托盘，点击托盘图标可恢复。",
                    self.tray_icon.icon(), 
                    2000
                )
            
            # 隐藏主窗口而不是关闭
            self.hide()
            event.ignore()
            return
            
        # 如果不是最小化或没有系统托盘，则正常处理关闭
        
        # 检查是否有活跃任务
        if hasattr(self, "active_tasks") and self.active_tasks:
            reply = QMessageBox.question(
                self, "确认退出", "有正在进行的检查任务，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return

        # 停止定时检查任务
        if hasattr(self, "scheduler"):
            try:
                self.logger.info("正在停止定时检查任务...")
                self.scheduler.stop()
            except Exception as e:
                self.logger.error(f"停止定时检查任务时出错: {str(e)}")

        # 默认行为
        event.accept()
