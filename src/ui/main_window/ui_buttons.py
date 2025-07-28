# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import QTimer

class UIButtons:
    """
    处理UI按钮样式和交互
    """

    @staticmethod
    def init_colored_buttons(main_window):
        """
        初始化彩色按钮样式
        """
        # 定义按钮样式
        button_styles = {
            "primary": """
                QPushButton {
                    background-color: #007bff;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #0069d9;
                }
                QPushButton:pressed {
                    background-color: #0062cc;
                }
            """,
            "success": """
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
                QPushButton:pressed {
                    background-color: #1e7e34;
                }
            """,
            "warning": """
                QPushButton {
                    background-color: #ffc107;
                    color: #212529;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #e0a800;
                }
                QPushButton:pressed {
                    background-color: #d39e00;
                }
            """,
            "danger": """
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
                QPushButton:pressed {
                    background-color: #bd2130;
                }
            """
        }

        # 应用样式函数
        def apply_button_styles():
            # 设置按钮样式，判断按钮是否存在再设置
            button_map = {
                # 添加包按钮
                "add_package_button": "primary",
                
                # 检查按钮
                "check_aur_button": "success",
                "check_upstream_button": "success",
                "check_all_versions_button": "danger",
                
                # 编辑按钮
                "edit_package_button": "warning",
                
                # 其他按钮
                "refresh_button": "primary",
                "select_all_toggle_button": "primary"
            }
            
            # 遍历按钮映射，设置样式
            for button_name, style_key in button_map.items():
                if hasattr(main_window, button_name):
                    button = getattr(main_window, button_name)
                    try:
                        button.setStyleSheet(button_styles[style_key])
                        main_window.logger.debug(f"成功设置按钮样式 {button_name}")
                    except Exception as e:
                        main_window.logger.error(f"设置按钮样式出错 {button_name}: {str(e)}")
                else:
                    main_window.logger.warning(f"按钮 {button_name} 不存在，无法设置样式")

        # 直接应用样式，不使用延迟
        apply_button_styles()
