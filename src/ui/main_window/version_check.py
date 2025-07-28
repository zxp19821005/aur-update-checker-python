# -*- coding: utf-8 -*-
"""
版本检查相关功能模块, UI交互部分
"""
from typing import TypeVar, cast
from PySide6.QtWidgets import QTableWidgetItem, QMessageBox, QProgressBar
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from ...modules.async_executor import run_async_task
from ...modules.main_checker import MainCheckerModule
from ...modules.aur_checker import AurCheckerModule
from ..protocols import MainWindowInterface

# 类型变量，表示实现了MainWindowInterface的任何类
T = TypeVar('T', bound=MainWindowInterface)

class VersionCheckMixin:
    """版本检查相关的方法混入类，需要实现MainWindowInterface接口"""

    def _init_version_services(self):
        """初始化版本检查相关服务"""
        if not hasattr(self, "main_checker") or self.main_checker is None:
            self.main_checker = MainCheckerModule(
                self.logger,
                self.db,
                self.config
            )
            self.logger.debug("版本检查模块已初始化")

        if not hasattr(self, "aur_checker") or self.aur_checker is None:
            self.aur_checker = AurCheckerModule(
                self.logger,
                self.db
            )
            self.logger.debug("AUR检查模块已初始化")

    def check_package_version(self, name=None, upstream_url=None, checker_type=None, version_extract_key=None):
        """检查单个软件包版本"""
        self.logger.info(f"开始检查软件包 {name} 版本")
        self._init_version_services()

        # 准备包信息
        package_info = {
            "name": name,
            "upstream_url": upstream_url
        }

        # 尝试从数据库获取完整的包信息
        try:
            db_package = self.db.get_package_by_name(name)
            if db_package:
                # 如果未提供checker_type，尝试从数据库获取
                if not checker_type and "checker_type" in db_package:
                    checker_type = db_package["checker_type"]
                    self.logger.debug(f"从数据库获取到checker_type: {checker_type}")

                # 如果未提供version_extract_key，尝试从数据库获取
                if not version_extract_key and "version_extract_key" in db_package:
                    version_extract_key = db_package["version_extract_key"]
                    self.logger.debug(f"从数据库获取到version_extract_key: {version_extract_key}")
        except Exception as e:
            self.logger.warning(f"从数据库获取包信息失败: {str(e)}")

        # 添加checker_type(如果存在)
        if checker_type:
            package_info["checker_type"] = checker_type
            self.logger.debug(f"设置checker_type为: {checker_type}")

        # 添加version_extract_key(如果存在)
        if version_extract_key:
            package_info["version_extract_key"] = version_extract_key
            self.logger.debug(f"设置version_extract_key为: {version_extract_key}")

        # 输出最终使用的包信息，帮助调试
        self.logger.debug(f"最终检查包信息: checker_type={package_info.get('checker_type')}, version_extract_key={package_info.get('version_extract_key')}")

        # 异步运行版本检查
        run_async_task(
            self.main_checker.check_single_upstream_version(package_info),
            self._on_version_check_completed,
            self._on_version_check_error
        )

    def batch_check_versions(self, packages=None):
        """批量检查版本"""
        self.logger.info("开始批量检查版本")
        self._init_version_services()

        # 如果没有指定包, 则获取所有包
        if packages is None:
            try:
                packages = self.db.get_all_packages()
            except Exception as e:
                self.logger.error(f"获取包列表失败: {str(e)}")
                return

        if not packages:
            self.logger.warning("没有要检查的包")
            return

        # 异步运行批量检查
        run_async_task(
            self.main_checker.check_multiple_upstream_versions(packages),
            self._on_batch_check_completed,
            self._on_batch_check_error
        )

    def check_aur_version(self, package_name):
        """检查AUR版本"""
        self.logger.info(f"开始检查AUR软件包 {package_name} 版本")
        self._init_version_services()

        # 异步运行AUR版本检查
        run_async_task(
            self.aur_checker.check_aur_version(package_name),
            self._on_aur_check_completed,
            self._on_aur_check_error
        )

    # 回调方法
    def _on_version_check_completed(self, result):
        if not result:
            return
        package_name = result.get("name")
        if package_name:
            self.update_package_after_check(package_name)
        self.logger.info(f"版本检查完成: {result}")

        # 更新数据库中的检查时间
        try:
            package_name = result.get("name")
            if package_name and result.get("success"):
                # 获取当前时间
                from datetime import datetime
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 更新上游版本检查时间
                # 由于没有单独的更新检查日期方法，我们保持当前版本不变，只更新日期
                package = self.db.get_package_by_name(package_name)
                if package and "upstream_version" in package:
                    self.db.update_upstream_version(package_name, package["upstream_version"])
                self.logger.debug(f"已更新 {package_name} 的检查时间: {current_time}")

                # 立即更新UI - 尝试多种方法以确保界面刷新
                # 先尝试使用reload_packages方法
                if hasattr(self, "reload_packages") and callable(self.reload_packages):
                    self.logger.debug("使用reload_packages更新上游版本检查后的UI")
                    self.reload_packages()
                # 如果没有reload_packages方法，则尝试使用update_package_after_check更新单个包
                elif hasattr(self, "update_package_after_check") and callable(self.update_package_after_check):
                    self.logger.debug(f"使用update_package_after_check更新{package_name}的UI")
                    self.update_package_after_check(package_name)
                # 最后尝试使用refresh_package_list
                elif hasattr(self, "refresh_package_list") and callable(self.refresh_package_list):
                    self.logger.debug("使用refresh_package_list更新UI")
                    self.refresh_package_list()
        except Exception as e:
            self.logger.error(f"更新检查时间失败: {str(e)}")

    def _on_version_check_error(self, error):
        self.logger.error(f"版本检查出错: {str(error)}")

    def _on_batch_check_completed(self, results):
        if not results:
            return
        self.logger.info(f"批量版本检查完成: {len(results)}个结果")
        
        # 使用批量更新功能更新数据库
        try:
            # 准备批量更新数据
            aur_updates = []
            upstream_updates = []
            
            for result in results:
                if result.get("success") and result.get("name"):
                    # AUR 更新
                    if "version" in result and "found" in result and result["found"]:
                        aur_updates.append({
                            "name": result["name"],
                            "version": result["version"]
                        })
                    
                    # 上游更新
                    if "upstream_version" in result:
                        upstream_updates.append({
                            "name": result["name"],
                            "version": result["upstream_version"]
                        })
            
            # 批量更新AUR版本
            if aur_updates:
                aur_updated = self.db.update_multiple_aur_versions(aur_updates)
                self.logger.info(f"批量更新了 {aur_updated} 个软件包的AUR版本")
                
            # 批量更新上游版本
            if upstream_updates:
                upstream_updated = self.db.update_multiple_upstream_versions(upstream_updates)
                self.logger.info(f"批量更新了 {upstream_updated} 个软件包的上游版本")
                
            # 如果表格已加载，则更新UI
            if hasattr(self, "refresh_package_list") and callable(self.refresh_package_list):
                self.refresh_package_list()
                
        except Exception as e:
            self.logger.error(f"批量更新数据库失败: {str(e)}")
            
        # 通知用户检查完成
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(f"批量检查完成: {len(results)}个软件包", 5000)

    def _on_batch_check_error(self, error):
        self.logger.error(f"批量版本检查出错: {str(error)}")

    def _on_aur_check_completed(self, result):
        if not result:
            return
        self.logger.info(f"AUR版本检查完成: {result}")

        # 更新数据库中的 AUR 检查时间
        try:
            package_name = result.get("name")
            if package_name and result.get("success"):
                # 获取当前时间
                from datetime import datetime
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 更新 AUR 版本检查时间
                # 使用新的批量更新方法
                if "version" in result:
                    updated_count = self.db.update_multiple_aur_versions([{
                        "name": package_name,
                        "version": result["version"]
                    }])
                    
                    if updated_count > 0:
                        self.logger.debug(f"已更新 {package_name} 的 AUR 检查时间: {current_time}")

                # 立即更新UI - 尝试多种方法以确保界面刷新
                # 先尝试使用reload_packages方法
                if hasattr(self, "reload_packages") and callable(self.reload_packages):
                    self.logger.debug("使用reload_packages更新UI")
                    self.reload_packages()
                # 如果没有reload_packages方法，则尝试使用update_package_after_check更新单个包
                elif hasattr(self, "update_package_after_check") and callable(self.update_package_after_check):
                    self.logger.debug(f"使用update_package_after_check更新{package_name}的UI")
                    self.update_package_after_check(package_name)
                # 最后尝试使用refresh_package_list
                elif hasattr(self, "refresh_package_list") and callable(self.refresh_package_list):
                    self.logger.debug("使用refresh_package_list更新UI")
                    self.refresh_package_list()
        except Exception as e:
            self.logger.error(f"更新 AUR 检查时间失败: {str(e)}")

    def _on_aur_check_error(self, error):
        self.logger.error(f"AUR版本检查出错: {str(error)}")

    def check_package_all_versions(self, package):
        """检查软件包的所有版本（AUR和上游）

        Args:
            package: 软件包信息字典
        """
        if not package:
            self.logger.warning("软件包信息为空")
            return

        name = package.get("name")
        if not name:
            self.logger.warning("软件包名为空")
            return

        # 初始化服务
        self._init_version_services()

        # 检查AUR版本
        self.logger.info(f"开始检查软件包 {name} 的所有版本")
        self.check_aur_version(name)

        # 检查上游版本
        upstream_url = package.get("upstream_url")
        checker_type = package.get("checker_type")
        version_extract_key = package.get("version_extract_key")

        if upstream_url:
            self.check_package_version(
                name=name,
                upstream_url=upstream_url,
                checker_type=checker_type,
                version_extract_key=version_extract_key
            )
        else:
            self.logger.warning(f"软件包 {name} 没有上游URL，跳过上游版本检查")


    def check_selected_aur(self):
        """检查所有通过复选框或鼠标选择的软件包的AUR版本"""
        # 获取选中的软件包
        selected_packages = self.get_selected_packages()
        if not selected_packages:
            self.logger.warning("没有选中的软件包")
            QMessageBox.information(self, "提示", "请先选择要检查的软件包")
            return

        self.logger.info(f"开始批量检查 {len(selected_packages)} 个选中的软件包的AUR版本")

        # 创建进度条
        progress_bar = None
        if hasattr(self, "status_bar"):
            progress_bar = QProgressBar()
            progress_bar.setMaximum(len(selected_packages))
            progress_bar.setValue(0)
            self.status_bar.addWidget(progress_bar)

        # 初始化AUR检查器
        self._init_version_services()

        # 准备包名列表用于批量查询
        package_names = []
        for package in selected_packages:
            name = package.get("name")
            if name:
                package_names.append(name)

        if not package_names:
            self.logger.warning("没有有效的包名用于检查")
            if progress_bar:
                self.status_bar.removeWidget(progress_bar)
            return

        # 使用批量API进行异步检查
        from src.modules.async_executor import run_async_task

        def on_batch_check_completed(results):
            # 完成检查，更新UI
            self.logger.info(f"批量AUR检查完成，结果数: {len(results)}")

            # 移除进度条
            if progress_bar and hasattr(self, "status_bar"):
                self.status_bar.removeWidget(progress_bar)
                self.status_bar.showMessage(f"已完成 {len(results)} 个软件包的AUR版本检查", 3000)

            # 更新表格数据
            if hasattr(self, "update_packages_table"):
                self.update_packages_table()

        def on_batch_check_error(error):
            self.logger.error(f"批量检查AUR版本时发生错误: {str(error)}")
            if progress_bar and hasattr(self, "status_bar"):
                self.status_bar.removeWidget(progress_bar)
                self.status_bar.showMessage(f"检查过程中发生错误", 3000)

        # 更新进度条状态为"正在检查"
        if hasattr(self, "status_bar"):
            self.status_bar.showMessage(f"正在批量检查 {len(package_names)} 个软件包的AUR版本...")

        # 异步执行批量检查
        run_async_task(
            self.aur_checker.check_multiple_aur_versions(package_names),
            on_batch_check_completed,
            on_batch_check_error
        )

    def check_selected_upstream(self):
        """检查所有通过复选框或鼠标选择的软件包的上游版本"""
        # 获取选中的软件包
        selected_packages = self.get_selected_packages()
        if not selected_packages:
            self.logger.warning("没有选中的软件包")
            QMessageBox.information(self, "提示", "请先选择要检查的软件包")
            return

        self.logger.info(f"开始检查 {len(selected_packages)} 个选中的软件包的上游版本")

        # 创建进度条
        progress_bar = None
        if hasattr(self, "status_bar"):
            progress_bar = QProgressBar()
            progress_bar.setMaximum(len(selected_packages))
            progress_bar.setValue(0)
            self.status_bar.addWidget(progress_bar)

        # 批量检查
        for i, package in enumerate(selected_packages):
            name = package.get("name")
            if not name:
                continue

            upstream_url = package.get("upstream_url")
            checker_type = package.get("checker_type")
            version_extract_key = package.get("version_extract_key")

            self.logger.debug(f"正在检查 [{i+1}/{len(selected_packages)}] {name} 的上游版本")
            if upstream_url:
                self.check_package_version(
                    name=name,
                    upstream_url=upstream_url,
                    checker_type=checker_type,
                    version_extract_key=version_extract_key
                )
            else:
                self.logger.warning(f"软件包 {name} 没有设置上游URL，跳过检查")

            # 更新进度条
            if progress_bar:
                progress_bar.setValue(i + 1)
                self.status_bar.showMessage(f"检查中... {i+1}/{len(selected_packages)}")

        # 完成检查，移除进度条
        if progress_bar:
            self.status_bar.removeWidget(progress_bar)
            self.status_bar.showMessage(f"已完成 {len(selected_packages)} 个软件包的上游版本检查", 3000)

        self.logger.info(f"完成 {len(selected_packages)} 个软件包的上游版本检查")

    def check_selected_all_versions(self):
        """检查所有通过复选框或鼠标选择的软件包的所有版本（AUR和上游）"""
        # 获取选中的软件包
        selected_packages = self.get_selected_packages()
        if not selected_packages:
            self.logger.warning("没有选中的软件包")
            QMessageBox.information(self, "提示", "请先选择要检查的软件包")
            return

        self.logger.info(f"开始检查 {len(selected_packages)} 个选中的软件包的所有版本")

        # 创建进度条
        progress_bar = None
        if hasattr(self, "status_bar"):
            progress_bar = QProgressBar()
            progress_bar.setMaximum(len(selected_packages))
            progress_bar.setValue(0)
            self.status_bar.addWidget(progress_bar)

        # 初始化服务
        self._init_version_services()

        # 1. 准备包名列表用于批量AUR查询
        package_names = []
        for package in selected_packages:
            name = package.get("name")
            if name:
                package_names.append(name)

        if package_names:
            # 2. 使用批量API进行AUR异步检查
            self.logger.info(f"开始批量检查 {len(package_names)} 个软件包的AUR版本")

            from src.modules.async_executor import run_async_task

            # 批量AUR查询完成后再进行上游版本检查
            def on_aur_batch_completed(results):
                self.logger.info(f"批量AUR检查完成，结果数: {len(results)}")

                # 现在开始逐个检查上游版本
                self._check_upstream_for_selected(selected_packages, progress_bar)

            def on_aur_batch_error(error):
                self.logger.error(f"批量检查AUR版本时发生错误: {str(error)}")
                # 即使AUR批量检查失败，也继续进行上游版本检查
                self._check_upstream_for_selected(selected_packages, progress_bar)

            # 更新状态条
            if hasattr(self, "status_bar"):
                self.status_bar.showMessage(f"正在批量检查 {len(package_names)} 个软件包的AUR版本...")

            # 执行批量AUR检查，完成后会自动检查上游版本
            run_async_task(
                self.aur_checker.check_multiple_aur_versions(package_names),
                on_aur_batch_completed,
                on_aur_batch_error
            )
        else:
            # 如果没有有效的包名，直接进行上游版本检查
            self._check_upstream_for_selected(selected_packages, progress_bar)

    def _check_upstream_for_selected(self, selected_packages, progress_bar=None):
        """检查所选包的上游版本（AUR检查之后的第二阶段）"""
        self.logger.info(f"开始检查 {len(selected_packages)} 个包的上游版本")

        # 逐个检查上游版本
        for i, package in enumerate(selected_packages):
            name = package.get("name")
            if not name:
                continue

            # 只检查上游版本
            upstream_url = package.get("upstream_url")
            checker_type = package.get("checker_type")
            version_extract_key = package.get("version_extract_key")

            if upstream_url:
                self.logger.debug(f"正在检查 [{i+1}/{len(selected_packages)}] {name} 的上游版本")
                self.check_package_version(
                    name=name,
                    upstream_url=upstream_url,
                    checker_type=checker_type,
                    version_extract_key=version_extract_key
                )
            else:
                self.logger.debug(f"软件包 {name} 没有设置上游URL，跳过上游版本检查")

            # 更新进度条
            if progress_bar:
                progress_bar.setValue(i + 1)
                self.status_bar.showMessage(f"检查上游版本... {i+1}/{len(selected_packages)}")

        # 完成检查，移除进度条
        if progress_bar and hasattr(self, "status_bar"):
            self.status_bar.removeWidget(progress_bar)
            self.status_bar.showMessage(f"已完成 {len(selected_packages)} 个软件包的所有版本检查", 3000)

        self.logger.info(f"完成 {len(selected_packages)} 个软件包的所有版本检查")
