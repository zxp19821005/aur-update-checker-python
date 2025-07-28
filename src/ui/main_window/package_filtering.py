# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt

class PackageFiltering:
    """
    处理软件包过滤和显示相关的功能
    """

    @staticmethod
    def on_outdated_filter_changed(main_window, state):
        """
        处理'仅显示过时'复选框状态变化
        
        Args:
            main_window: 主窗口实例
            state: 复选框状态
        """
        # 记录复选框状态变化
        is_checked = bool(state)
        main_window.logger.info(f"过滤条件改变: 仅显示过时 = {is_checked}")
        
        # 首先确保过滤的包列表被重置为所有包
        if not is_checked:
            main_window.logger.info("取消过时过滤，准备显示所有符合搜索条件的包")
            # 重新加载所有包并过滤
            main_window.load_packages()
        else:
            # 应用标准过滤
            main_window.filter_packages()
    
    @staticmethod
    def filter_packages(main_window):
        """
        根据过滤条件筛选软件包
        """
        filter_text = main_window.filter_edit.text().lower()
        show_aur = main_window.show_aur_checkbox.isChecked()
        show_upstream = main_window.show_upstream_checkbox.isChecked()
        show_both = main_window.show_both_checkbox.isChecked()
        show_none = main_window.show_none_checkbox.isChecked()

        # 清空表格
        main_window.packages_table.setRowCount(0)

        # 填充表格
        row = 0
        for package in main_window.packages:
            name = package.get("name", "")

            # 应用过滤器
            if filter_text and filter_text not in name.lower():
                continue

            has_aur = package.get("aur_version") is not None
            has_upstream = package.get("upstream_version") is not None

            # 应用复选框过滤条件
            if (show_aur and has_aur and not has_upstream) or                (show_upstream and not has_aur and has_upstream) or                (show_both and has_aur and has_upstream) or                (show_none and not has_aur and not has_upstream) or                (not show_aur and not show_upstream and not show_both and not show_none):

                # 添加一行
                main_window.packages_table.insertRow(row)

                # 复选框
                checkbox = QTableWidgetItem()
                checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                checkbox.setCheckState(Qt.Unchecked)
                main_window.packages_table.setItem(row, 0, checkbox)

                # 包名
                name_item = QTableWidgetItem(name)
                main_window.packages_table.setItem(row, 1, name_item)

                # 更新行状态
                main_window.update_package_status(row)

                row += 1

    @staticmethod
    def update_package_status(main_window, row):
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
