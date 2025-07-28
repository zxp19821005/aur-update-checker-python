# -*- coding: utf-8 -*-
"""
更新界面相关功能模块
"""
from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

class UpdateUIMixin:
    """更新界面相关的方法混入类"""

    def _get_alignment(self, alignment_text):
        """获取对齐方式的Qt标志

        Args:
            alignment_text: 对齐方式文本

        Returns:
            int: Qt对齐标志
        """
        if alignment_text == "center":
            return Qt.AlignCenter
        elif alignment_text == "right":
            return Qt.AlignRight | Qt.AlignVCenter
        else:  # "left" or default
            return Qt.AlignLeft | Qt.AlignVCenter

    def load_packages(self):
        """加载软件包列表"""
        self.logger.info("加载软件包列表")

        # 从数据库加载所有软件包
        self.packages = self.db.get_all_packages()

        # 更新过滤后的软件包列表，但不更新表格
        self.filter_packages(update_table=False)
        
        # 手动调用一次update_packages_table
        self.logger.info("刷新表格显示")
        self.update_packages_table()

    def filter_packages(self, update_table=True):
        """根据搜索和过滤条件过滤软件包
        
        Args:
            update_table: 是否更新表格，默认为True
        """
        search_text = self.search_edit.text().lower()
        show_outdated = self.show_outdated_check.isChecked()
        
        # 记录过滤条件
        self.logger.info(f"过滤条件: 搜索文本='{search_text}', 仅显示过时={show_outdated}")
        
        filtered = []

        for pkg in self.packages:
            # 搜索过滤
            name = pkg.get("name", "").lower()
            if search_text and search_text not in name:
                continue

            # 过滤过时的包
            if show_outdated:
                aur_version = pkg.get("aur_version", "")
                upstream_version = pkg.get("upstream_version", "")
                
                # 只有当两个版本都存在且AUR版本小于上游版本时，才视为过时
                is_outdated = False
                if aur_version and upstream_version:
                    try:
                        is_outdated = aur_version < upstream_version
                    except Exception:
                        # 如果版本比较失败，尝试字符串比较
                        is_outdated = aur_version != upstream_version
                
                if not is_outdated:
                    continue

            filtered.append(pkg)

        # 记录过滤结果
        self.logger.info(f"过滤后的软件包数量: {len(filtered)}/{len(self.packages)}")
        
        self.filtered_packages = filtered
        if update_table:
            self.update_packages_table()

    def update_single_package(self, package_info):
        """更新单个软件包的信息并立即刷新显示

        Args:
            package_info: 包含软件包更新信息的字典
        """
        # 记录日志
        self.logger.debug(f"实时更新软件包: {package_info.get('name')}")

        # 更新内存中的软件包数据
        for i, pkg in enumerate(self.packages):
            if pkg.get("name") == package_info.get("name"):
                # 更新内存中的软件包数据
                self.packages[i].update(package_info)
                break

        # 获取软件包名称
        package_name = package_info.get("name")

        # 使用延迟更新UI，避免可能的递归重绘
        from PySide6.QtCore import QTimer

        def delayed_update():
            # 查找表格中对应的行
            found = False
            for row in range(self.packages_table.rowCount()):
                name_item = self.packages_table.item(row, 1)  # 名称列
                if name_item and name_item.text() == package_name:
                    # 更新UI中的相关列
                    if package_info.get("version"):
                        # 更新AUR版本列
                        aur_version_item = self.packages_table.item(row, 2)
                        if aur_version_item:
                            aur_version_item.setText(package_info.get("version", ""))
                        else:
                            aur_version_item = QTableWidgetItem(package_info.get("version", ""))
                            self.packages_table.setItem(row, 2, aur_version_item)

                    if package_info.get("upstream_version"):
                        # 更新上游版本列
                        upstream_version_item = self.packages_table.item(row, 3)
                        if upstream_version_item:
                            upstream_version_item.setText(package_info.get("upstream_version", ""))
                        else:
                            upstream_version_item = QTableWidgetItem(package_info.get("upstream_version", ""))
                            self.packages_table.setItem(row, 3, upstream_version_item)

                    if package_info.get("last_modified"):
                        # 更新AUR检查时间列
                        aur_check_time_item = self.packages_table.item(row, 5)
                        if aur_check_time_item:
                            aur_check_time_item.setText(package_info.get("last_modified", ""))
                        else:
                            aur_check_time_item = QTableWidgetItem(package_info.get("last_modified", ""))
                            self.packages_table.setItem(row, 5, aur_check_time_item)

                    # 更新状态列
                    self.update_package_status(row)
                    found = True
                    break

            # 只有在找到对应行并更新后才应用过滤
            if found:
                # 再次延迟应用过滤，确保表格更新完成
                QTimer.singleShot(50, lambda: self.filter_packages())

        # 启动延迟更新
        QTimer.singleShot(10, delayed_update)

    def update_package_status(self, row):
        """更新指定行的软件包状态

        Args:
            row: 行索引
        """
        # 使用延时机制更新状态，避免递归重绘
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtGui import QColor

        def do_update_status():
            try:
                # 记录调试信息
                self.logger.debug(f"更新行 {row} 的状态")

                # 检查行号是否有效
                if row < 0 or row >= self.packages_table.rowCount():
                    self.logger.error(f"行号 {row} 超出范围")
                    return

                # 获取AUR版本和上游版本
                aur_version_item = self.packages_table.item(row, 2)
                upstream_version_item = self.packages_table.item(row, 3)

                if not aur_version_item or not upstream_version_item:
                    self.logger.warning(f"行 {row} 的版本项目为空")
                    # 创建空项
                    if not aur_version_item:
                        aur_version_item = QTableWidgetItem("")
                        self.packages_table.setItem(row, 2, aur_version_item)
                    if not upstream_version_item:
                        upstream_version_item = QTableWidgetItem("")
                        self.packages_table.setItem(row, 3, upstream_version_item)

                aur_version = aur_version_item.text()
                upstream_version = upstream_version_item.text()

                self.logger.debug(f"行 {row} 的版本: AUR={aur_version}, 上游={upstream_version}")

                # 设置状态
                status_item = self.packages_table.item(row, 4)
                if not status_item:
                    status_item = QTableWidgetItem()
                    self.packages_table.setItem(row, 4, status_item)

                # 设置状态文本（先设置文本，避免背景色触发额外的重绘）
                if not aur_version or not upstream_version:
                    status_item.setText("未知")
                elif aur_version == upstream_version:
                    status_item.setText("最新")
                elif aur_version < upstream_version:
                    status_item.setText("过时")
                else:
                    status_item.setText("超前")

                self.logger.debug(f"行 {row} 的状态设置为: {status_item.text()}")

                # 使用另一个延时设置背景色
                def set_background():
                    try:
                        # 根据版本比较确定状态背景色
                        if not aur_version or not upstream_version:
                            status_item.setBackground(QColor("#E0E0E0"))  # 灰色背景
                        elif aur_version == upstream_version:
                            status_item.setBackground(QColor("#C8E6C9"))  # 绿色背景
                        elif aur_version < upstream_version:
                            status_item.setBackground(QColor("#FFCDD2"))  # 红色背景
                        else:
                            status_item.setBackground(QColor("#BBDEFB"))  # 蓝色背景
                    except Exception as bg_error:
                        self.logger.error(f"设置背景色时出错: {bg_error}")

                # 延迟5毫秒设置背景色
                QTimer.singleShot(5, set_background)
            except Exception as e:
                # 记录任何错误但不中断程序执行
                if hasattr(self, 'logger'):
                    self.logger.error(f"更新状态时出错: {e}")

        # 延时执行状态更新
        QTimer.singleShot(1, do_update_status)

    def update_packages_table(self):
        """更新软件包表格"""
        self.packages_table.setRowCount(0)
        self.packages_table.setRowCount(len(self.filtered_packages))

        # 应用显示设置
        # 从ui部分直接获取显示设置，确保获取正确的配置值
        ui_config = self.config.get("ui", {})

        # 获取列显示设置，并直接将其类型转换为布尔值，以避免任何类型问题
        show_name = bool(ui_config.get("show_name", True))
        show_aur_version = bool(ui_config.get("show_aur_version", True))
        show_upstream_version = bool(ui_config.get("show_upstream_version", True))
        show_status = bool(ui_config.get("show_status", False))
        show_aur_check_time = bool(ui_config.get("show_aur_check_time", True))
        show_upstream_check_time = bool(ui_config.get("show_upstream_check_time", True))
        show_checker_type = bool(ui_config.get("show_checker_type", True))
        show_upstream_url = bool(ui_config.get("show_upstream_url", False))
        show_notes = bool(ui_config.get("show_notes", False))

        # 检查设置类型，以便调试
        self.logger.debug(f"列显示设置类型: status={type(show_status)}, url={type(show_upstream_url)}, notes={type(show_notes)}")
        
        # 输出日志，记录读取到的配置值
        self.logger.info(f"列显示配置: name={show_name}, aur_version={show_aur_version}, upstream_version={show_upstream_version}, status={show_status}, aur_check_time={show_aur_check_time}, upstream_check_time={show_upstream_check_time}, checker_type={show_checker_type}, upstream_url={show_upstream_url}, notes={show_notes}")
        
        # 记录此时的配置对象状态
        ui_config = {k: v for k, v in self.config.get("ui", {}).items() if k.startswith("show_")}
        self.logger.info(f"配置对象中的UI显示设置: {ui_config}")

        # 先设置列可见性，再填充数据
        # 所有列根据配置显示或隐藏
        self.packages_table.setColumnHidden(1, not show_name)  # 名称列
        self.packages_table.setColumnHidden(2, not show_aur_version)  # AUR版本列
        self.packages_table.setColumnHidden(3, not show_upstream_version)  # 上游版本列
        self.packages_table.setColumnHidden(4, not show_status)  # 状态列
        self.packages_table.setColumnHidden(5, not show_aur_check_time)  # AUR检查时间列
        self.packages_table.setColumnHidden(6, not show_upstream_check_time)  # 上游检查时间列
        self.packages_table.setColumnHidden(7, not show_checker_type)  # 检查器类型列
        self.packages_table.setColumnHidden(8, not show_upstream_url)  # 上游URL列
        self.packages_table.setColumnHidden(9, not show_notes)  # 备注列

        # 列可见性设置已应用

        # 确保表格已正确初始化
        if self.packages_table.columnCount() != 10:
            self.packages_table.setColumnCount(10)
            self.packages_table.setHorizontalHeaderLabels([
                "", "名称", "AUR版本", "上游版本", "状态", "AUR检查时间", "上游检查时间",
                "检查器类型", "上游URL", "备注"
            ])

        # 延迟调整列大小，待数据填充后再执行，避免重绘问题
        from PySide6.QtCore import QTimer
        self._resize_timer = QTimer.singleShot(100, self.packages_table.resizeColumnsToContents)
        
        # 恢复之前的排序状态
        last_sort_column = self.packages_table.property("last_sort_column")
        last_sort_order = self.packages_table.property("last_sort_order")
        
        if last_sort_column is not None and last_sort_column >= 0:
            # 记录正在恢复排序状态
            order_name = "升序" if last_sort_order == Qt.AscendingOrder else "降序"
            self.logger.info(f"恢复表格排序状态：列 {last_sort_column} {order_name}")
            
            # 暂时禁用排序以避免触发排序信号
            self.packages_table.setSortingEnabled(False)
            
            # 设置排序指示器
            self.packages_table.horizontalHeader().setSortIndicator(last_sort_column, last_sort_order)
            
            # 重新启用排序
            self.packages_table.setSortingEnabled(True)

        # 填充数据
        for row, pkg in enumerate(self.filtered_packages):
            # 生成表格行数据
            self._create_table_row(row, pkg)
            
        # 填充数据后，如果有之前的排序状态，重新应用排序
        last_sort_column = self.packages_table.property("last_sort_column")
        if last_sort_column is not None and last_sort_column >= 0:
            # 应用实际的排序
            self.packages_table.sortItems(last_sort_column, self.packages_table.property("last_sort_order"))

    def _create_table_row(self, row, pkg):
        """创建表格行数据

        Args:
            row: 行索引
            pkg: 软件包数据
        """
        # 使用最精确的方式创建复选框，确保没有额外内容
        # 使用空字符串作为项目文本，防止显示默认内容
        check = QTableWidgetItem("")

        # 只保留必要的标志，移除所有可能导致额外显示的标志
        check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)

        # 设置初始复选框状态
        check.setCheckState(Qt.Unchecked)

        # 显式设置空显示角色和编辑角色，确保没有任何显示内容
        check.setData(Qt.DisplayRole, None)
        check.setData(Qt.EditRole, None)

        # 将项添加到表格
        self.packages_table.setItem(row, 0, check)

        # 名称
        name_item = QTableWidgetItem(pkg.get("name", ""))
        alignment = self.config.get("ui.text_alignment.name", "left")
        
        # 设置对齐方式
        
        alignment_flag = Qt.AlignLeft | Qt.AlignVCenter
        if alignment == "center":
            alignment_flag = Qt.AlignCenter
        elif alignment == "right":
            alignment_flag = Qt.AlignRight | Qt.AlignVCenter
        name_item.setTextAlignment(alignment_flag)
        self.packages_table.setItem(row, 1, name_item)

        # AUR版本 - 尝试多种键名来获取AUR版本
        aur_version = pkg.get("aur_version", "")
        if not aur_version:
            aur_version = pkg.get("version", "")
        aur_item = QTableWidgetItem(aur_version)
        ui_config = self.config.get("ui", {})
        text_alignment = ui_config.get("text_alignment", {})
        alignment = text_alignment.get("aur_version", "left")
        alignment_flag = Qt.AlignLeft | Qt.AlignVCenter
        if alignment == "center":
            alignment_flag = Qt.AlignCenter
        elif alignment == "right":
            alignment_flag = Qt.AlignRight | Qt.AlignVCenter
        aur_item.setTextAlignment(alignment_flag)
        self.packages_table.setItem(row, 2, aur_item)

        # 上游版本
        upstream_version = pkg.get("upstream_version", "")
        upstream_item = QTableWidgetItem(upstream_version)
        ui_config = self.config.get("ui", {})
        text_alignment = ui_config.get("text_alignment", {})
        alignment = text_alignment.get("upstream_version", "left")
        upstream_item.setTextAlignment(self._get_alignment(alignment))
        self.packages_table.setItem(row, 3, upstream_item)

        # 状态
        status_text = ""
        status_color = "#FFFFFF"  # 默认白色背景

        if aur_version and upstream_version:
            if aur_version == upstream_version:
                status_text = "最新"
                status_color = "#C8E6C9"  # 绿色背景
            elif aur_version < upstream_version:
                status_text = "过时"
                status_color = "#FFCDD2"  # 红色背景
            else:
                status_text = "超前"
                status_color = "#BBDEFB"  # 蓝色背景
        else:
            status_text = "未知"
            status_color = "#E0E0E0"  # 灰色背景

        status_item = QTableWidgetItem(status_text)
        status_item.setBackground(QColor(status_color))
        ui_config = self.config.get("ui", {})
        text_alignment = ui_config.get("text_alignment", {})
        alignment = text_alignment.get("status", "center")
        status_item.setTextAlignment(self._get_alignment(alignment))
        self.packages_table.setItem(row, 4, status_item)

        # AUR检查时间
        aur_check_time = pkg.get("aur_update_date", "")
        # 格式化时间，只显示年月日
        if aur_check_time:
            try:
                # 假设时间是ISO格式，如2025-07-24T06:18:29
                formatted_time = aur_check_time.split("T")[0]
            except Exception:
                formatted_time = aur_check_time
        else:
            formatted_time = ""
        aur_check_item = QTableWidgetItem(formatted_time)
        alignment = self.config.get("ui.text_alignment.aur_check_time", "left")
        aur_check_item.setTextAlignment({
            "left": Qt.AlignLeft | Qt.AlignVCenter,
            "center": Qt.AlignCenter,
            "right": Qt.AlignRight | Qt.AlignVCenter
        }[alignment])
        self.packages_table.setItem(row, 5, aur_check_item)

        # 上游检查时间
        upstream_check_time = pkg.get("upstream_update_date", "")
        # 格式化时间，只显示年月日
        if upstream_check_time:
            try:
                # 假设时间是ISO格式，如2025-07-24T06:18:29
                formatted_time = upstream_check_time.split("T")[0]
            except Exception:
                formatted_time = upstream_check_time
        else:
            formatted_time = ""
        upstream_check_item = QTableWidgetItem(formatted_time)
        alignment = self.config.get("ui.text_alignment.upstream_check_time", "left")
        upstream_check_item.setTextAlignment({
            "left": Qt.AlignLeft | Qt.AlignVCenter,
            "center": Qt.AlignCenter,
            "right": Qt.AlignRight | Qt.AlignVCenter
        }[alignment])
        self.packages_table.setItem(row, 6, upstream_check_item)

        # 检查器类型
        checker_type = pkg.get("checker_type", "")
        checker_type_item = QTableWidgetItem(checker_type)
        alignment = self.config.get("ui.text_alignment.checker_type", "left")
        checker_type_item.setTextAlignment({
            "left": Qt.AlignLeft | Qt.AlignVCenter,
            "center": Qt.AlignCenter,
            "right": Qt.AlignRight | Qt.AlignVCenter
        }[alignment])
        self.packages_table.setItem(row, 7, checker_type_item)

        # 上游URL
        upstream_url = pkg.get("upstream_url", "")
        upstream_url_item = QTableWidgetItem(upstream_url)
        alignment = self.config.get("ui.text_alignment.upstream_url", "left")
        upstream_url_item.setTextAlignment({
            "left": Qt.AlignLeft | Qt.AlignVCenter,
            "center": Qt.AlignCenter,
            "right": Qt.AlignRight | Qt.AlignVCenter
        }[alignment])
        self.packages_table.setItem(row, 8, upstream_url_item)

        # 备注
        notes = pkg.get("notes", "")
        notes_item = QTableWidgetItem(notes)
        alignment = self.config.get("ui.text_alignment.notes", "left")
        notes_item.setTextAlignment(self._get_alignment(alignment))
        self.packages_table.setItem(row, 9, notes_item)