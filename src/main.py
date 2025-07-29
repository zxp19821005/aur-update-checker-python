#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import asyncio
import argparse
from pathlib import Path

# 将项目根目录添加到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置当前目录为项目根目录
# 检查是否是编译后的环境
if getattr(sys, "__compiled__", False):
    # 编译后的环境，使用可执行文件所在目录作为根目录
    base_dir = os.path.dirname(sys.executable)
    if not os.path.isdir(base_dir):
        base_dir = os.path.dirname(os.path.abspath(__file__))
else:
    # 开发环境，使用脚本所在目录作为根目录
    base_dir = os.path.dirname(os.path.abspath(__file__))

# 将项目根目录添加到模块搜索路径
sys.path.insert(0, base_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from src.modules.service_provider import ServiceProvider
from src.modules.dependency_container import container
from src.modules.http_client import HttpClient
from src.ui.main_window import MainWindow

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="AUR Update Checker (Python版)")
    parser.add_argument('--config', '-c', help='指定配置文件路径')
    parser.add_argument('--log-level', '-l', choices=['debug', 'info', 'warning', 'error', 'critical'],
                        help='设置日志级别')
    parser.add_argument('--version', '-v', action='store_true', help='显示版本信息')
    return parser.parse_args()

async def main():
    """程序入口函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 显示版本信息并退出
    if args.version:
        print("AUR Update Checker (Python版) v1.0.1")
        sys.exit(0)
    
    # 初始化服务提供者
    await ServiceProvider.bootstrap(config_path=args.config)

    # 获取日志服务
    logger = await container.get("logger")
    logger.info("AUR Update Checker (Python版) 启动中...")
    
    # 如果指定了日志级别，设置日志级别
    if args.log_level:
        logger.set_log_level(args.log_level.upper())
        logger.info(f"日志级别已设置为: {args.log_level.upper()}")

    # 服务已通过ServiceProvider初始化，无需手动初始化
    # 从容器中获取配置和数据库服务
    config = await container.get("config")
    db = await container.get("db")

    # 异步获取HTTP客户端
    http_client = await container.get("http_client")
    logger.debug("HTTP客户端已初始化，准备就绪")

    # 创建Qt应用实例
    app = QApplication(sys.argv)
    app.setApplicationName("AUR Update Checker")
    
    # 尝试加载图标
    icon_paths = [
        os.path.join(base_dir, "assets", "icon.png"),
        os.path.join(os.path.dirname(base_dir), "assets", "icon.png"),
        os.path.join("assets", "icon.png")
    ]
    
    for icon_path in icon_paths:
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
            break

    # 初始化异步执行器
    try:
        # 导入并初始化异步执行器
        from src.modules.async_executor import get_async_executor
        async_executor = get_async_executor(logger)
        logger.info("成功初始化异步执行器")

        # 同时也尝试初始化qasync
        try:
            import qasync
            loop = qasync.QEventLoop(app)
            asyncio.set_event_loop(loop)
            logger.info("成功初始化qasync事件循环")
        except ImportError:
            logger.warning("qasync库未安装，使用标准事件循环")
        except Exception as e:
            logger.warning(f"初始化qasync事件循环出错: {e}")
    except Exception as e:
        logger.error(f"初始化异步执行器失败: {e}")

    # 创建主窗口
    window = MainWindow(config, db, logger)
    
    # 直接显示窗口，让用户看到界面
    window.show()
    logger.info("主窗口已显示")
    
    # 使用QTimer延迟加载数据，确保界面已显示
    def load_data():
        logger.info("开始加载数据")
        if hasattr(window, "load_packages") and callable(window.load_packages):
            window.load_packages()
            logger.info("数据加载完成")
    
    # 立即加载数据
    load_data()

    # 定义简单的清理函数，记录日志但不尝试异步关闭
    def cleanup():
        """清理资源，记录关闭信息"""
        logger.info("正在关闭应用...")

        # 简单记录，不尝试异步关闭，依赖系统自动清理连接
        if container.has("http_client"):
            logger.debug("HTTP客户端将由系统自动清理")

    # 注册应用退出时的清理函数
    app.aboutToQuit.connect(cleanup)

    # 运行应用事件循环
    if 'loop' in locals() and isinstance(loop, qasync.QEventLoop):
        with loop:  # 使用qasync集成的事件循环
            sys.exit(loop.run_forever())
    else:
        sys.exit(app.exec())  # 使用标准Qt事件循环

if __name__ == "__main__":
    asyncio.run(main())