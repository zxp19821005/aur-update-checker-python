# -*- coding: utf-8 -*-
"""
软件包操作相关功能模块
"""
from PySide6.QtWidgets import QTableWidgetItem, QMessageBox, QMenu, QApplication
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from .package_dialog import PackageDialog

class PackageOperationsMixin:
    """软件包操作相关的方法混入类"""
    
    def copy_cell_content(self, row, column):
        """复制单元格内容到剪贴板
        
        Args:
            row: 行索引
            column: 列索引
        """
        if row < 0 or column < 0:
            return
            
        # 获取单元格内容
        item = self.packages_table.item(row, column)
        if not item:
            return
            
        content = item.text()
        if not content:
            return
            
        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(content)
        
        # 在状态栏显示提示
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(f"已复制: {content}", 3000)  # 显示3秒
        
        self.logger.debug(f"已复制单元格内容: {content}")

    def get_selected_packages(self):
        """获取表格中选中的软件包（通过复选框或鼠标选中的行）

        Returns:
            list: 选中的软件包列表
        """
        self.logger.debug("==== 开始获取选中的软件包 ====")
        selected_packages = []
        selected_rows = set()

        # 记录表格基本信息
        table_rows = self.packages_table.rowCount()
        table_cols = self.packages_table.columnCount()
        self.logger.debug(f"表格大小: {table_rows} 行 x {table_cols} 列")

        # 检查选择模式
        selection_mode = self.packages_table.selectionMode()
        selection_behavior = self.packages_table.selectionBehavior()
        self.logger.debug(f"表格选择模式: mode={selection_mode}, behavior={selection_behavior}")

        # 1. 首先获取通过鼠标选中的行
        # 方法一: 通过selectedIndexes()
        selected_indexes = self.packages_table.selectedIndexes()

        # 记录鼠标选择的详细情况
        if selected_indexes:
            self.logger.debug(f"鼠标选中了 {len(selected_indexes)} 个单元格")
            index_rows = []
            for index in selected_indexes:
                row = index.row()
                col = index.column()
                selected_rows.add(row)
                index_rows.append(f"({row},{col})")
            self.logger.debug(f"选中的单元格位置: {', '.join(index_rows)}")

        # 方法二: 通过selectedItems()（更直接的方法）
        selected_items = self.packages_table.selectedItems()
        if selected_items:
            self.logger.debug(f"通过selectedItems()检测到 {len(selected_items)} 个选中项目")
            item_details = []
            for item in selected_items:
                row = item.row()
                col = item.column()
                text = item.text() if hasattr(item, 'text') else "无文本"
                selected_rows.add(row)
                item_details.append(f"({row},{col})={text}")
            self.logger.debug(f"选中项目详情: {', '.join(item_details[:5])}{'...' if len(item_details) > 5 else ''}")

        # 方法三: 通过selectedRanges()
        selected_ranges = self.packages_table.selectedRanges()
        if selected_ranges:
            self.logger.debug(f"检测到 {len(selected_ranges)} 个选中范围")
            for i, range_item in enumerate(selected_ranges):
                top = range_item.topRow()
                bottom = range_item.bottomRow()
                left = range_item.leftColumn()
                right = range_item.rightColumn()
                self.logger.debug(f"范围 {i+1}: 从 ({top},{left}) 到 ({bottom},{right}), 共 {bottom-top+1} 行")
                for row in range(top, bottom + 1):
                    selected_rows.add(row)

        if selected_rows:
            self.logger.debug(f"鼠标选择的行（所有方法合并）: {sorted(list(selected_rows))}")
        else:
            self.logger.warning("通过所有方法都未检测到鼠标选中的行")

        # 2. 然后获取通过复选框选中的行
        checkbox_selected = 0
        for row in range(self.packages_table.rowCount()):
            checkbox_item = self.packages_table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                selected_rows.add(row)
                checkbox_selected += 1

        if checkbox_selected:
            self.logger.debug(f"通过复选框选中了 {checkbox_selected} 行")

        # 记录总选中行数
        self.logger.debug(f"总共选中了 {len(selected_rows)} 行")

        # 检查filtered_packages是否可用
        if hasattr(self, 'filtered_packages'):
            self.logger.debug(f"filtered_packages可用，包含 {len(self.filtered_packages)} 个包")
            # 输出前几个包的名称以验证数据
            if self.filtered_packages:
                sample_names = [p.get('name', 'unknown') for p in self.filtered_packages[:3]]
                self.logger.debug(f"filtered_packages样本: {sample_names}...")
        else:
            self.logger.warning("filtered_packages不可用！")

        # 3. 处理所有选中的行
        self.logger.debug(f"开始处理 {len(selected_rows)} 个选中的行...")
        row_processed = 0

        for row in selected_rows:
            row_processed += 1
            # 获取软件包名称
            name_item = self.packages_table.item(row, 1)

            if name_item:
                package_name = name_item.text()
                self.logger.debug(f"处理行 {row} (第{row_processed}/{len(selected_rows)}行): 包名={package_name}")

                # 从当前显示的软件包列表中查找完整信息
                package_found = False

                # 检查filtered_packages是否为列表且有元素
                if hasattr(self, 'filtered_packages') and isinstance(self.filtered_packages, list) and self.filtered_packages:
                    self.logger.debug(f"开始在 {len(self.filtered_packages)} 个filtered_packages中查找 {package_name}")

                    for package in self.filtered_packages:
                        if isinstance(package, dict) and package.get("name") == package_name:
                            selected_packages.append(package)
                            package_found = True
                            self.logger.debug(f"在filtered_packages中找到 {package_name}, 包含键: {list(package.keys())}")
                            break

                    if not package_found:
                        self.logger.warning(f"在filtered_packages中找不到名为 {package_name} 的软件包")
                else:
                    self.logger.warning(f"filtered_packages不可用或为空，无法查找 {package_name}")
            else:
                self.logger.warning(f"行 {row} 的名称单元格为空")

        self.logger.debug(f"完成处理，最终找到 {len(selected_packages)} 个软件包信息")

        # 如果没有找到包，记录一个明确的警告
        if not selected_packages and selected_rows:
            self.logger.warning(f"虽然选中了 {len(selected_rows)} 行，但未能获取任何软件包信息！")

        # 如果没有选中的包但有选中的行，可能是表格选择问题
        if len(selected_packages) == 0 and len(selected_rows) > 0:
            self.logger.warning("有选中的行但未找到对应的软件包信息，尝试直接使用表格数据")

            # 直接从表格获取数据
            for row in selected_rows:
                name_item = self.packages_table.item(row, 1)
                if name_item:
                    package_name = name_item.text()
                    self.logger.info(f"正在处理选中行的包名: {package_name}")

                    # 尝试直接从所有包中查找
                    package_found = False

                    # 如果self.packages可用
                    if hasattr(self, 'packages'):
                        for package in self.packages:
                            if package["name"] == package_name:
                                selected_packages.append(package)
                                package_found = True
                                self.logger.info(f"在完整包列表中找到了: {package_name}")
                                break
                    else:
                        self.logger.warning("self.packages不可用，跳过完整包列表搜索")

                    # 无论如何，确保从表格创建一个可用的包对象
                    # 不依赖于在包列表中找到
                    # 创建包对象

                    # 创建一个基本的包信息
                    basic_package = {"name": package_name}

                    # 尝试获取AUR版本
                    aur_item = self.packages_table.item(row, 2)
                    if aur_item and aur_item.text():
                        basic_package["aur_version"] = aur_item.text()
                        self.logger.debug(f"添加AUR版本: {aur_item.text()}")

                    # 尝试获取上游版本
                    upstream_item = self.packages_table.item(row, 3)
                    if upstream_item and upstream_item.text():
                        basic_package["upstream_version"] = upstream_item.text()
                        self.logger.debug(f"添加上游版本: {upstream_item.text()}")

                    # 尝试获取状态
                    status_item = self.packages_table.item(row, 4)
                    if status_item and status_item.text():
                        basic_package["status"] = status_item.text()

                    # 尝试获取上游URL
                    try:
                        upstream_url_item = self.packages_table.item(row, 8)
                        if upstream_url_item and upstream_url_item.text():
                            basic_package["upstream_url"] = upstream_url_item.text()
                            self.logger.debug(f"添加上游URL: {upstream_url_item.text()}")
                    except Exception as e:
                        self.logger.warning(f"获取上游URL时出错: {e}")

                    # 添加到选中包列表
                    selected_packages.append(basic_package)
                    self.logger.info(f"直接从表格添加了软件包: {package_name}, 包含字段: {list(basic_package.keys())}")

        return selected_packages

    def show_package_context_menu(self, position):
        """显示软件包的上下文菜单

        Args:
            position: 菜单位置
        """
        menu = QMenu()

        # 获取当前选中的行
        row = self.packages_table.rowAt(position.y())
        if row < 0:
            return

        # 获取软件包名称
        package_name = self.packages_table.item(row, 1).text()

        # 查找完整的软件包信息
        package = None
        for p in self.filtered_packages:
            if p["name"] == package_name:
                package = p
                break

        if not package:
            return

        # 编辑菜单项
        edit_action = QAction("编辑", self)
        edit_action.triggered.connect(lambda: self.edit_package(package))
        menu.addAction(edit_action)

        # 删除菜单项
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self.delete_package(package))
        menu.addAction(delete_action)

        # 检查AUR菜单项
        check_aur_action = QAction("检查AUR版本", self)
        check_aur_action.triggered.connect(lambda: self.check_aur_version(package["name"]))
        menu.addAction(check_aur_action)

        # 检查上游菜单项
        if package.get("upstream_url"):
            check_upstream_action = QAction("检查上游版本", self)
            check_upstream_action.triggered.connect(lambda: self.check_package_version(
                name=package["name"], 
                upstream_url=package["upstream_url"],
                version_extract_key=package.get("version_extract_key")
            ))
            menu.addAction(check_upstream_action)

            # 添加检查所有版本菜单项
            menu.addSeparator()  # 添加分隔线，使菜单更清晰
            check_all_versions_action = QAction("检查所有版本", self)
            check_all_versions_action.triggered.connect(lambda: self.check_package_all_versions(package))
            menu.addAction(check_all_versions_action)

        # 显示菜单
        menu.exec_(self.packages_table.viewport().mapToGlobal(position))

    def edit_package(self, package):
        """编辑软件包

        Args:
            package: 要编辑的软件包
        """
        dialog = PackageDialog(self, package)
        if dialog.exec_() == PackageDialog.Accepted:
            package_data = dialog.get_package_data()

            # 更新数据库
            try:
                self.db.update_package(package_data["name"], package_data)
                self.logger.info(f"已更新软件包 {package_data['name']}")
                self.load_packages()  # 重新加载软件包列表
            except Exception as e:
                self.logger.error(f"更新软件包时出错: {str(e)}")
                QMessageBox.critical(self, "错误", f"更新软件包时出错: {str(e)}")

    def add_package(self):
        """添加新软件包"""
        dialog = PackageDialog(self)
        if dialog.exec_() == PackageDialog.Accepted:
            package_data = dialog.get_package_data()

            # 检查必填字段
            if not package_data["name"]:
                QMessageBox.warning(self, "警告", "软件包名称不能为空")
                return

            # 添加到数据库
            try:
                self.db.add_package(package_data)
                self.logger.info(f"已添加软件包 {package_data['name']}")
                self.load_packages()  # 重新加载软件包列表
            except Exception as e:
                self.logger.error(f"添加软件包时出错: {str(e)}")
                QMessageBox.critical(self, "错误", f"添加软件包时出错: {str(e)}")

    def delete_package(self, package):
        """删除软件包

        Args:
            package: 要删除的软件包
        """
        confirm = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除软件包 {package['name']} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            try:
                self.db.delete_package(package["name"])
                self.logger.info(f"已删除软件包 {package['name']}")
                self.load_packages()  # 重新加载软件包列表
            except Exception as e:
                self.logger.error(f"删除软件包时出错: {str(e)}")
                QMessageBox.critical(self, "错误", f"删除软件包时出错: {str(e)}")

    def edit_selected_package(self):
        """编辑选中的软件包

        如果有通过复选框选中的软件包，则编辑第一个选中的软件包
        如果没有通过复选框选中的软件包，则编辑当前选中行的软件包
        """
        # 首先检查通过复选框选中的软件包
        selected_packages = self.get_selected_packages()

        if len(selected_packages) > 1:
            QMessageBox.warning(self, "警告", "请只选择一个软件包进行编辑")
            return
        elif len(selected_packages) == 1:
            # 如果通过复选框选中了一个软件包，则编辑它
            self.edit_package(selected_packages[0])
            return

        # 如果没有通过复选框选中的软件包，检查当前选中的行
        current_row = self.packages_table.currentRow()
        if current_row >= 0:
            # 获取软件包名称
            package_name = self.packages_table.item(current_row, 1).text()

            # 查找完整的软件包信息
            for package in self.filtered_packages:
                if package["name"] == package_name:
                    self.edit_package(package)
                    return

        # 如果没有选中任何软件包
        QMessageBox.warning(self, "警告", "请先选择一个软件包")

    def toggle_select_all(self, state):
        """全选或取消全选所有软件包

        Args:
            state: 复选框状态
        """
        for row in range(self.packages_table.rowCount()):
            checkbox_item = self.packages_table.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(Qt.Checked if state == Qt.Checked else Qt.Unchecked)

    def toggle_select_all_button(self):
        """切换全选/取消全选状态

        根据当前按钮文本判断执行全选还是取消全选操作，
        并更新按钮文本以便下次点击执行相反操作
        """
        if self.select_all_toggle_button.text() == "全选":
            # 执行全选操作
            self.toggle_select_all(Qt.Checked)
            # 更新按钮文本为"取消全选"
            self.select_all_toggle_button.setText("取消全选")
        else:
            # 执行取消全选操作
            self.toggle_select_all(Qt.Unchecked)
            # 更新按钮文本为"全选"
            self.select_all_toggle_button.setText("全选")

    def select_all_packages(self):
        """选择所有软件包

        此方法用于在系统托盘菜单操作时自动选择所有软件包
        """
        self.logger.info("自动选择所有软件包")
        # 使用现有的toggle_select_all方法选中所有软件包
        self.toggle_select_all(Qt.Checked)
        # 更新UI中的按钮状态，如果存在
        if hasattr(self, 'select_all_toggle_button'):
            self.select_all_toggle_button.setText("取消全选")

