# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt

class TableSortMixin:
    """表格排序相关的方法混入类"""

    def on_sort_indicator_changed(self, logical_index, order):
        """当表格排序指示器变化时被调用

        Args:
            logical_index: 排序列的逻辑索引
            order: 排序顺序 (Qt.AscendingOrder 或 Qt.DescendingOrder)
        """
        # 复选框列不排序
        if logical_index == 0:
            return
            
        # 获取列名
        header_item = self.packages_table.horizontalHeaderItem(logical_index)
        column_name = header_item.text() if header_item else f"列 {logical_index}"
        
        # 记录排序操作
        order_name = "升序" if order == Qt.AscendingOrder else "降序"
        self.logger.info(f"对{column_name}({logical_index})进行{order_name}排序")
        
        # 在UI更新前禁用排序，避免列内容出现异常
        # 保存当前排序设置，以便在更新数据后恢复
        self.packages_table.setProperty("last_sort_column", logical_index)
        self.packages_table.setProperty("last_sort_order", order)
