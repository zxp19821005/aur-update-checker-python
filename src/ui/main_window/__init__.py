# -*- coding: utf-8 -*-
# 导入主窗口类的组件
from .main_window import MainWindowWrapper
from .package_dialog import PackageDialog
from .package_operations import PackageOperationsMixin
from .system_tray import SystemTrayMixin
from .ui_init import UIInitMixin
from .update_ui import UpdateUIMixin
from .version_check import VersionCheckMixin
from .package_filtering import PackageFiltering
from .table_operations import TableOperations
from .ui_buttons import UIButtons
from .utils import run_async

# 兼容导入，使用MainWindowWrapper作为MainWindow
MainWindow = MainWindowWrapper

# 导出类，方便导入
__all__ = [
    'MainWindow',
    'MainWindowWrapper',
    'PackageDialog',
    'PackageOperationsMixin',
    'SystemTrayMixin',
    'UIInitMixin',
    'UpdateUIMixin',
    'VersionCheckMixin',
    'PackageFiltering',
    'TableOperations',
    'UIButtons',
    'run_async'
]

