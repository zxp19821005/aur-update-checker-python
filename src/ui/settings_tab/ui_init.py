# -*- coding: utf-8 -*-
"""
设置标签页UI初始化
"""
import os
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, 
    QWidget, QTabWidget, QGroupBox, QFormLayout, 
    QLineEdit, QFileDialog, QSpinBox, QComboBox, QCheckBox
)
from PySide6.QtCore import Qt

# 从其他模块导入
from .display_settings import setup_display_tab
from .form_controls import create_form_control
from .scheduler_settings import setup_scheduler_tab, _load_scheduler_settings, _update_scheduler_settings, _check_now

# 默认配置路径
default_base_path = os.path.join(os.path.expanduser("~"), ".config", "aur-update-checker-python")

def init_ui(self):
    """初始化UI"""
    # 创建主布局
    main_layout = QVBoxLayout(self)

    # 创建滚动区域
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    main_layout.addWidget(scroll_area)

    # 创建滚动区域的内容小部件
    content_widget = QWidget()
    scroll_area.setWidget(content_widget)

    # 内容小部件的布局
    layout = QVBoxLayout(content_widget)

    # 创建选项卡小部件
    tabs = QTabWidget()
    layout.addWidget(tabs)

    # ---- 显示配置选项卡 ----
    display_tab = QWidget()
    tabs.addTab(display_tab, "显示设置")
    setup_display_tab(self, display_tab)

    # ---- 定时检查选项卡 ----
    scheduler_tab = QWidget()
    tabs.addTab(scheduler_tab, "定时检查")
    setup_scheduler_tab(self, scheduler_tab)

    # ---- API配置选项卡 ----
    api_tab = QWidget()
    tabs.addTab(api_tab, "API设置")
    api_layout = QVBoxLayout(api_tab)

    # GitHub API设置组
    github_group = QGroupBox("GitHub API设置")
    github_layout = QVBoxLayout()
    github_group.setLayout(github_layout)
    api_layout.addWidget(github_group)

    # GitHub API表单
    github_form = QFormLayout()
    github_layout.addLayout(github_form)

    # GitHub令牌
    self.github_token_edit = self._create_form_control(
        github_form, "GitHub令牌:", QLineEdit, "github.token", ""
    )
    self.github_token_edit.setEchoMode(QLineEdit.Password)

    # Gitee API设置组
    gitee_group = QGroupBox("Gitee API设置")
    gitee_layout = QVBoxLayout()
    gitee_group.setLayout(gitee_layout)
    api_layout.addWidget(gitee_group)

    # Gitee API表单
    gitee_form = QFormLayout()
    gitee_layout.addLayout(gitee_form)

    # Gitee API URL
    self.gitee_api_edit = self._create_form_control(
        gitee_form, "Gitee API URL:", QLineEdit, "gitee.api_url", "https://gitee.com/api/v5"
    )

    # Gitee令牌
    self.gitee_token_edit = self._create_form_control(
        gitee_form, "Gitee令牌:", QLineEdit, "gitee.token", ""
    )
    self.gitee_token_edit.setEchoMode(QLineEdit.Password)

    # GitLab API设置组
    gitlab_group = QGroupBox("GitLab API设置")
    gitlab_layout = QVBoxLayout()
    gitlab_group.setLayout(gitlab_layout)
    api_layout.addWidget(gitlab_group)

    # GitLab API表单
    gitlab_form = QFormLayout()
    gitlab_layout.addLayout(gitlab_form)

    # GitLab API URL
    self.gitlab_api_edit = self._create_form_control(
        gitlab_form, "GitLab API URL:", QLineEdit, "gitlab.api_url", "https://gitlab.com/api/v4"
    )

    # GitLab令牌
    self.gitlab_token_edit = self._create_form_control(
        gitlab_form, "GitLab令牌:", QLineEdit, "gitlab.token", ""
    )
    self.gitlab_token_edit.setEchoMode(QLineEdit.Password)

    # NPM设置组
    npm_group = QGroupBox("NPM设置")
    npm_layout = QVBoxLayout()
    npm_group.setLayout(npm_layout)
    api_layout.addWidget(npm_group)

    # NPM表单
    npm_form = QFormLayout()
    npm_layout.addLayout(npm_form)

    # NPM Registry
    self.npm_registry_edit = self._create_form_control(
        npm_form, "NPM Registry:", QLineEdit, "npm.registry", "https://registry.npmjs.org"
    )

    # PyPI设置组
    pypi_group = QGroupBox("PyPI设置")
    pypi_layout = QVBoxLayout()
    pypi_group.setLayout(pypi_layout)
    api_layout.addWidget(pypi_group)

    # PyPI表单
    pypi_form = QFormLayout()
    pypi_layout.addLayout(pypi_form)

    # PyPI API URL
    self.pypi_api_edit = self._create_form_control(
        pypi_form, "PyPI API URL:", QLineEdit, "pypi.api_url", "https://pypi.org/pypi"
    )

    # ---- 路径配置选项卡 ----
    paths_tab = QWidget()
    tabs.addTab(paths_tab, "路径设置")
    paths_layout = QVBoxLayout(paths_tab)

    # 数据库设置组
    db_group = QGroupBox("数据库设置")
    db_layout = QVBoxLayout()
    db_group.setLayout(db_layout)
    paths_layout.addWidget(db_group)

    # 数据库表单
    db_form = QFormLayout()
    db_layout.addLayout(db_form)

    # 数据库路径
    self.db_path_edit = self._create_form_control(
        db_form, "数据库路径:", QLineEdit, "database.path", 
        os.path.join(default_base_path, "packages.db")
    )

    # 数据库备份数量
    self.db_backup_count_spin = self._create_form_control(
        db_form, "备份数量:", QSpinBox, "database.backup_count", 3,
        minimum=0, maximum=10
    )

    # 日志设置组
    log_group = QGroupBox("日志设置")
    log_layout = QVBoxLayout()
    log_group.setLayout(log_layout)
    paths_layout.addWidget(log_group)

    # 日志表单
    log_form = QFormLayout()
    log_layout.addLayout(log_form)

    # 日志目录
    self.log_path_edit = self._create_form_control(
        log_form, "日志目录:", QLineEdit, "logging.path", 
        os.path.join(default_base_path, "logs")
    )

    # 日志文件名
    self.log_file_edit = self._create_form_control(
        log_form, "日志文件:", QLineEdit, "logging.file", "aur_update_checker.log"
    )

    # 日志级别
    self.log_level_combo = self._create_form_control(
        log_form, "日志级别:", QComboBox, "logging.level", "INFO",
        items=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    )

    # 是否输出到控制台
    self.log_console_check = self._create_form_control(
        log_form, "输出到控制台:", QCheckBox, "logging.console", True
    )

    # 日志文件最大大小(MB)
    self.log_max_size_spin = self._create_form_control(
        log_form, "单文件最大大小(MB):", QSpinBox, "logging.max_size", 10,
        minimum=1, maximum=100
    )
    # 日志文件最大个数
    self.log_max_files_spin = self._create_form_control(
        log_form, "最大文件个数:", QSpinBox, "logging.max_files", 5,
        minimum=1, maximum=50
    )

    # ---- 系统配置选项卡 ----
    system_tab = QWidget()
    tabs.addTab(system_tab, "系统设置")
    system_layout = QVBoxLayout(system_tab)

    # 系统设置组
    system_group = QGroupBox("系统设置")
    system_group_layout = QVBoxLayout()
    system_group.setLayout(system_group_layout)
    system_layout.addWidget(system_group)

    # 系统设置表单
    system_form = QFormLayout()
    system_group_layout.addLayout(system_form)

    # 临时目录
    self.temp_dir_edit = self._create_form_control(
        system_form, "临时目录:", QLineEdit, "system.temp_dir", "/tmp"
    )

    # 超时时间
    self.timeout_spin = self._create_form_control(
        system_form, "超时时间(秒):", QSpinBox, "system.timeout", 30,
        minimum=5, maximum=300
    )

    # 并发检查数
    self.concurrent_checks_spin = self._create_form_control(
        system_form, "并发检查数:", QSpinBox, "system.concurrent_checks", 5,
        minimum=1, maximum=20
    )

    # 重试次数
    self.retry_count_spin = self._create_form_control(
        system_form, "重试次数:", QSpinBox, "system.retry_count", 3,
        minimum=0, maximum=10
    )

    # 托盘图标
    self.show_tray_check = self._create_form_control(
        system_form, "显示托盘图标:", QCheckBox, "system.show_tray", True
    )

    # 最小化通知
    self.show_minimize_notification_check = self._create_form_control(
        system_form, "最小化时显示通知:", QCheckBox, "ui.show_minimize_notification", True
    )

    # 关闭操作
    self.close_action_combo = self._create_form_control(
        system_form, "关闭按钮行为:", QComboBox, "ui.close_action", "minimize",
        items=["exit", "minimize"]
    )

    # UI主题
    self.theme_combo = self._create_form_control(
        system_form, "界面主题:", QComboBox, "ui.theme", "system",
        items=["system", "light", "dark"]
    )

    # 包管理器
    self.package_manager_combo = self._create_form_control(
        system_form, "包管理器:", QComboBox, "system.package_manager", "yay",
        items=["yay", "paru", "pacman", "pamac"]
    )

    # 工具设置组
    tools_group = QGroupBox("工具设置")
    tools_layout = QVBoxLayout()
    tools_group.setLayout(tools_layout)
    system_layout.addWidget(tools_group)

    # 工具设置表单
    tools_form = QFormLayout()
    tools_layout.addLayout(tools_form)

    # curl路径设置
    curl_layout = QHBoxLayout()
    self.curl_path_edit = QLineEdit()
    self.curl_path_edit.setText(self.config.get("tools.curl_path", "/usr/bin/curl"))
    curl_layout.addWidget(self.curl_path_edit)

    # 添加浏览按钮
    curl_browse_button = QPushButton("浏览...")
    curl_browse_button.clicked.connect(self.select_curl_path)
    curl_layout.addWidget(curl_browse_button)
    tools_form.addRow("curl路径:", curl_layout)

    # ---- 更新设置选项卡 ----
    update_tab = QWidget()
    tabs.addTab(update_tab, "更新设置")
    update_layout = QVBoxLayout(update_tab)

    # 更新设置组
    update_group = QGroupBox("软件更新设置")
    update_group_layout = QVBoxLayout()
    update_group.setLayout(update_group_layout)
    update_layout.addWidget(update_group)

    # 更新设置表单
    update_form = QFormLayout()
    update_group_layout.addLayout(update_form)

    # 自动检查更新
    self.auto_check_update = self._create_form_control(
        update_form, "自动检查更新:", QCheckBox, "update.auto_check", True
    )

    # 有更新时通知
    self.notify_on_update = self._create_form_control(
        update_form, "有更新时通知:", QCheckBox, "update.notify_on_update", True
    )

    # 检查间隔
    self.check_interval_spin = self._create_form_control(
        update_form, "检查间隔(天):", QSpinBox, "update.check_interval", 7,
        minimum=1, maximum=30
    )

    # 添加填充空间
    update_layout.addStretch()

    # 底部按钮区域
    button_layout = QHBoxLayout()
    layout.addLayout(button_layout)

    # 保存设置按钮
    self.save_settings_button = QPushButton("保存设置")
    self.save_settings_button.clicked.connect(self.save_settings)
    self.save_settings_button.setStyleSheet("""
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QPushButton:pressed {
            background-color: #3d8b40;
        }
    """)
    button_layout.addWidget(self.save_settings_button)

    # 重置设置按钮
    reset_settings_button = QPushButton("重置为默认")
    reset_settings_button.clicked.connect(self.reset_settings)
    reset_settings_button.setStyleSheet("""
        QPushButton {
            background-color: #f44336;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #e53935;
        }
        QPushButton:pressed {
            background-color: #d32f2f;
        }
    """)
    button_layout.addWidget(reset_settings_button)

def select_curl_path(self):
    """选择curl可执行文件路径"""
    from PySide6.QtWidgets import QFileDialog

    file_path, _ = QFileDialog.getOpenFileName(
        self,
        "选择curl可执行文件",
        "/usr/bin",
        "可执行文件 (*)"
    )

    if file_path:
        self.curl_path_edit.setText(file_path)

# 使用从form_controls.py导入的create_form_control方法
_create_form_control = create_form_control
