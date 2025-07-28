# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt
from datetime import datetime

class TableOperations:
    """
    处理表格操作相关的功能
    """

    @staticmethod
    def update_packages_table(main_window):
        """
        更新软件包表格的内容
        """
        # 保存当前滚动位置
        scrollbar = main_window.packages_table.verticalScrollBar()
        scroll_position = scrollbar.value()

        # 清空表格
        main_window.packages_table.setRowCount(0)

        # 填充表格
        for row, package in enumerate(main_window.packages):
            # 添加一行
            main_window.packages_table.insertRow(row)

            # 复选框
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox.setCheckState(Qt.Unchecked)
            main_window.packages_table.setItem(row, 0, checkbox)

            # 包名
            name_item = QTableWidgetItem(package.get("name", ""))
            main_window.packages_table.setItem(row, 1, name_item)

            # 本地版本
            local_version = package.get("local_version", "")
            local_item = QTableWidgetItem(local_version)
            main_window.packages_table.setItem(row, 2, local_item)

            # AUR版本
            aur_version = package.get("aur_version", "")
            aur_item = QTableWidgetItem(aur_version)
            main_window.packages_table.setItem(row, 3, aur_item)

            # 上游版本
            upstream_version = package.get("upstream_version", "")
            upstream_item = QTableWidgetItem(upstream_version)
            main_window.packages_table.setItem(row, 4, upstream_item)

            # 上次检查时间
            last_check = package.get("last_check", "")
            if last_check:
                try:
                    # 格式化为易读的日期时间
                    last_check_item = QTableWidgetItem(last_check)
                except ValueError:
                    last_check_item = QTableWidgetItem(str(last_check))
            else:
                last_check_item = QTableWidgetItem("")
            main_window.packages_table.setItem(row, 5, last_check_item)

            # 不再高亮有更新的行 - 通过状态列显示更新状态
            # 状态信息将在update_ui.py中通过状态列显示

        # 恢复滚动位置
        scrollbar.setValue(scroll_position)

    @staticmethod
    def update_single_package(main_window, package_info):
        """
        更新单个包的信息

        Args:
            package_info: 包信息字典
        """
        # 查找包并更新信息
        for i, package in enumerate(main_window.packages):
            if package.get("name") == package_info.get("name"):
                # 更新本地数据
                main_window.packages[i].update(package_info)

                # 如果显示了这个包，更新表格中的行
                name = package.get("name")
                for row in range(main_window.packages_table.rowCount()):
                    name_item = main_window.packages_table.item(row, 1)
                    if name_item and name_item.text() == name:
                        # 本地版本
                        local_version = package_info.get("local_version", package.get("local_version", ""))
                        local_item = QTableWidgetItem(local_version)
                        main_window.packages_table.setItem(row, 2, local_item)

                        # AUR版本
                        aur_version = package_info.get("aur_version", package.get("aur_version", ""))
                        aur_item = QTableWidgetItem(aur_version)
                        main_window.packages_table.setItem(row, 3, aur_item)

                        # 上游版本
                        upstream_version = package_info.get("upstream_version", package.get("upstream_version", ""))
                        upstream_item = QTableWidgetItem(upstream_version)
                        main_window.packages_table.setItem(row, 4, upstream_item)

                        # 上次检查时间
                        last_check = package_info.get("last_check", package.get("last_check", ""))
                        if last_check:
                            try:
                                last_check_item = QTableWidgetItem(last_check)
                            except ValueError:
                                last_check_item = QTableWidgetItem(str(last_check))
                        else:
                            last_check_item = QTableWidgetItem("")
                        main_window.packages_table.setItem(row, 5, last_check_item)

                        # 不再使用行高亮显示更新状态
                        # 状态信息将在update_ui.py中通过状态列显示

                        break
                break

    @staticmethod
    def update_single_package_status(main_window, row):
        """
        更新特定行的包状态信息

        Args:
            row: 表格中的行号
        """
        # 获取包名
        name_item = main_window.packages_table.item(row, 1)
        if not name_item:
            return

        name = name_item.text()

        # 查找包数据
        package = None
        for p in main_window.packages:
            if p.get("name") == name:
                package = p
                break

        if not package:
            return

        # 本地版本
        local_version = package.get("local_version", "")
        local_item = QTableWidgetItem(local_version)
        main_window.packages_table.setItem(row, 2, local_item)

        # AUR版本
        aur_version = package.get("aur_version", "")
        aur_item = QTableWidgetItem(aur_version)
        main_window.packages_table.setItem(row, 3, aur_item)

        # 上游版本
        upstream_version = package.get("upstream_version", "")
        upstream_item = QTableWidgetItem(upstream_version)
        main_window.packages_table.setItem(row, 4, upstream_item)

        # 上次检查时间
        last_check = package.get("last_check", "")
        if last_check:
            try:
                # 格式化为易读的日期时间
                last_check_item = QTableWidgetItem(last_check)
            except ValueError:
                last_check_item = QTableWidgetItem(str(last_check))
        else:
            last_check_item = QTableWidgetItem("")
        main_window.packages_table.setItem(row, 5, last_check_item)

