# -*- coding: utf-8 -*-
"""
UI初始化相关功能模块
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QTabWidget, QWidget
)
from PySide6.QtCore import Qt

class UIInitMixin:
    """UI初始化相关的方法混入类"""

    def init_ui(self):
        """初始化UI"""
        # 设置窗口标题和大小
        self.setWindowTitle("AUR Update Checker")
        self.setMinimumSize(900, 600)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建标签页控件
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # 软件包标签页
        self.packages_tab = QWidget()
        self.tabs.addTab(self.packages_tab, "软件包")

        # 日志标签页
        self.logs_tab = QWidget()
        self.tabs.addTab(self.logs_tab, "日志")

        # 设置标签页
        self.settings_tab = QWidget()
        self.tabs.addTab(self.settings_tab, "设置")

        # 初始化软件包标签页
        self.init_packages_tab()

        # 初始化日志标签页
        self.logs_tab_widget = self.LogsTabClass(logger=self.logger)
        self.logs_tab.setLayout(QVBoxLayout())
        self.logs_tab.layout().addWidget(self.logs_tab_widget)

        # 初始化设置标签页
        self.settings_tab_widget = self.SettingsTabClass(config=self.config, logger=self.logger)
        self.settings_tab.setLayout(QVBoxLayout())
        self.settings_tab.layout().addWidget(self.settings_tab_widget)

        # 连接配置变更信号
        self.settings_tab_widget.settings_saved.connect(self.apply_all_settings)

    def apply_all_settings(self):
        """应用所有设置"""
        self.logger.info("应用所有设置")

        # 更新表格显示
        self.update_packages_table()

        # 刷新其他设置（托盘图标、关闭行为等）
        show_tray = self.config.get("system.show_tray", True)
        if hasattr(self, 'tray_icon'):
            self.tray_icon.setVisible(show_tray)

        # 记录当前应用的配置
        self.logger.info(f"当前应用的关闭行为: {self.config.get('ui.close_action', 'minimize')}")
        self.logger.info(f"当前应用的托盘图标显示: {show_tray}")

    def init_packages_tab(self):
        """初始化软件包标签页"""
        # 创建布局
        layout = QVBoxLayout(self.packages_tab)

        # 工具栏布局
        toolbar_layout = QHBoxLayout()
        layout.addLayout(toolbar_layout)

        # 全选/取消全选切换按钮
        self.select_all_toggle_button = QPushButton("全选")
        self.select_all_toggle_button.clicked.connect(self.toggle_select_all_button)
        toolbar_layout.addWidget(self.select_all_toggle_button)

        # 添加软件包按钮
        self.add_package_button = QPushButton("添加")
        self.add_package_button.clicked.connect(self.add_package)
        toolbar_layout.addWidget(self.add_package_button)

        # 编辑软件包按钮
        self.edit_package_button = QPushButton("编辑")
        self.edit_package_button.clicked.connect(self.edit_selected_package)
        self.edit_package_button.setToolTip("编辑选中的软件包\n可通过复选框或直接用鼠标选中单行来选择\n(一次只能编辑一个包)")
        toolbar_layout.addWidget(self.edit_package_button)

        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索软件包...")
        self.search_edit.textChanged.connect(self.on_search_text_changed)
        toolbar_layout.addWidget(self.search_edit)

        # 显示过时软件包复选框
        self.show_outdated_check = QCheckBox("仅显示过时")
        
        # 连接到专门处理复选框变化的方法
        self.show_outdated_check.stateChanged.connect(self.on_outdated_filter_changed)
        toolbar_layout.addWidget(self.show_outdated_check)

        # 操作按钮
        
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.load_packages)
        toolbar_layout.addWidget(self.refresh_button)

        self.check_aur_button = QPushButton("检查AUR版本")
        # 连接到处理选中软件包的AUR版本检查方法
        self.check_aur_button.clicked.connect(self.check_selected_aur)
        self.check_aur_button.setToolTip("检查已选择的软件包的AUR版本\n可通过复选框或直接用鼠标选中行来选择")
        toolbar_layout.addWidget(self.check_aur_button)

        self.check_upstream_button = QPushButton("检查上游版本")
        # 连接到处理选中软件包的上游版本检查方法
        self.check_upstream_button.clicked.connect(self.check_selected_upstream)
        self.check_upstream_button.setToolTip("检查已选择的软件包的上游版本\n可通过复选框或直接用鼠标选中行来选择")
        toolbar_layout.addWidget(self.check_upstream_button)

        self.check_all_versions_button = QPushButton("检查所有版本")
        # 连接到处理选中软件包的所有版本检查方法
        self.check_all_versions_button.clicked.connect(self.check_selected_all_versions)
        self.check_all_versions_button.setToolTip("同时检查已选择的软件包的AUR和上游版本\n可通过复选框或直接用鼠标选中行来选择")
        toolbar_layout.addWidget(self.check_all_versions_button)

        # 软件包表格
        self.packages_table = QTableWidget()
        # 设置表格全局样式表，使复选框在深色主题中更明显和居中
        self.packages_table.setStyleSheet("""
            /* 表格项样式 */
            QTableWidget::item {
                color: white;
            }
            /* 第一列(复选框列)的特殊样式 */
            QTableWidget::item:first {
                padding: 0px;
                margin: 0px;
                border-right: 1px solid #444;
                background-color: rgba(80, 80, 80, 50);
                color: transparent;
            }

            /* 复选框样式 - 自适应列宽的居中方法 */
            QTableWidget::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #666;
                background: #333;
                position: absolute;
                left: 15%;
                margin-left: -7px;  /* 负的宽度一半 */
            }
            QTableWidget::indicator:checked {
                background: #4CAF50;
                border: 1px solid #4CAF50;
            }
            /* 确保复选框容器使用相对定位 */
            QTableWidget QCheckBox {
                position: relative;
            }
        """)

        # 设置表格属性
        self.packages_table.setSelectionBehavior(QTableWidget.SelectRows)
        # 启用多行选择
        self.packages_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.packages_table.setColumnCount(10)
        self.packages_table.setHorizontalHeaderLabels([
            "", "名称", "AUR版本", "上游版本", "状态", "AUR检查时间", "上游检查时间", 
            "检查器类型", "上游URL", "备注"
        ])
        # 设置列宽度调整模式
        self.packages_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        
        # 根据配置设置列的显示与调整模式
        # 列的顺序必须与update_ui.py中的列顺序一致
        column_configs = [
            {"index": 1, "key": "name", "default_resize": QHeaderView.Stretch},
            {"index": 2, "key": "aur_version", "default_resize": QHeaderView.ResizeToContents},
            {"index": 3, "key": "upstream_version", "default_resize": QHeaderView.ResizeToContents},
            {"index": 4, "key": "status", "default_resize": QHeaderView.ResizeToContents},
            {"index": 5, "key": "aur_check_time", "default_resize": QHeaderView.ResizeToContents},
            {"index": 6, "key": "upstream_check_time", "default_resize": QHeaderView.ResizeToContents},
            {"index": 7, "key": "checker_type", "default_resize": QHeaderView.ResizeToContents},
            {"index": 8, "key": "upstream_url", "default_resize": QHeaderView.ResizeToContents},
            {"index": 9, "key": "notes", "default_resize": QHeaderView.Stretch}
        ]
        
        # 应用列配置
        for col_config in column_configs:
            # 设置列的宽度调整模式
            self.packages_table.horizontalHeader().setSectionResizeMode(
                col_config["index"], 
                col_config["default_resize"]
            )
            
            # 注意：列的可见性在update_ui.py的update_packages_table方法中根据配置动态设置
            # 在初始化时，我们只设置宽度调整模式，不需要在这里设置列显示状态
            # 列的对齐方式是在update_ui.py的_create_table_row方法中设置的
        self.packages_table.verticalHeader().setVisible(False)
        self.packages_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.packages_table.setColumnWidth(0, 30)  # 第一列(复选框列)宽度固定为30像素，确保充分显示

        # 添加表格右键菜单
        self.packages_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.packages_table.customContextMenuRequested.connect(self.show_package_context_menu)

        # 添加表格双击事件 - 用于复制内容
        self.packages_table.cellDoubleClicked.connect(self.copy_cell_content)
        
        # 启用表格排序功能
        self.packages_table.setSortingEnabled(True)
        
        # 获取表头对象
        header = self.packages_table.horizontalHeader()
        
        # 连接排序指示器改变信号
        header.sortIndicatorChanged.connect(self.on_sort_indicator_changed)
        
        # 设置默认排序为第二列（软件包名称），升序
        if self.packages_table.columnCount() > 1:
            header.setSortIndicator(1, Qt.AscendingOrder)
        
        self.logger.info("已启用表格排序功能")

        # 添加表格到布局
        layout.addWidget(self.packages_table)

        # 底部工具栏
        bottom_toolbar = QHBoxLayout()
        layout.addLayout(bottom_toolbar)

        # 状态标签
        self.status_label = QLabel("就绪")
        bottom_toolbar.addWidget(self.status_label)

        # 添加加载进度条
        from PySide6.QtWidgets import QProgressBar
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 100)
        self.loading_progress.setValue(0)
        self.loading_progress.setFixedWidth(200)
        self.loading_progress.setVisible(False)
        bottom_toolbar.addWidget(self.loading_progress)

        # 填充空间
        bottom_toolbar.addStretch(1)
