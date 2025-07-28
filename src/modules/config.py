# -*- coding: utf-8 -*-
import os
import json
import tempfile
import argparse
import sys
from datetime import datetime
from pathlib import Path

class ConfigModule:
    """配置模块，负责加载和管理应用程序配置"""

    def __init__(self, logger):
        """初始化配置模块

        Args:
            logger: 日志模块实例
        """
        self.logger = logger
        
        # 获取配置文件路径
        self.config_dir, self.config_file = self._get_config_paths()
        self.config = self._load_default_config()

        # 确保配置目录存在
        self._ensure_config_dir()

        # 加载用户配置
        self._load_config()
        
    def _get_config_paths(self):
        """获取配置文件路径，优先级：命令行参数 > 环境变量 > 默认路径
        
        Returns:
            tuple: (config_dir, config_file) 配置目录和配置文件路径
        """
        # 默认配置路径
        default_config_dir = os.path.join(os.path.expanduser("~"), ".config", "aur-update-checker-python")
        default_config_file = os.path.join(default_config_dir, "config.json")
        
        # 从环境变量获取配置路径
        env_config_file = os.environ.get("AUR_UPDATE_CHECKER_CONFIG")
        
        # 从命令行参数获取配置路径
        config_file = None
        try:
            # 只解析与配置相关的参数，不影响其他参数
            parser = argparse.ArgumentParser(add_help=False)
            parser.add_argument('--config', '-c', help='配置文件路径')
            args, _ = parser.parse_known_args()
            if args.config:
                config_file = args.config
                self.logger.info(f"从命令行参数获取配置文件路径: {config_file}")
        except Exception as e:
            self.logger.warning(f"解析命令行参数时出错: {str(e)}")
        
        # 确定最终使用的配置文件路径（优先级：命令行 > 环境变量 > 默认路径）
        final_config_file = config_file or env_config_file or default_config_file
        final_config_dir = os.path.dirname(final_config_file)
        
        self.logger.info(f"使用配置文件: {final_config_file}")
        return final_config_dir, final_config_file

    def _ensure_config_dir(self):
        """确保配置目录存在"""
        try:
            if not os.path.exists(self.config_dir):
                self.logger.info(f"创建配置目录: {self.config_dir}")
                os.makedirs(self.config_dir, exist_ok=True)
        except Exception as e:
            self.logger.error(f"创建配置目录时出错: {str(e)}")

    def _load_default_config(self):
        """加载默认配置

        Returns:
            dict: 默认配置字典
        """
        return {
            # 数据库配置
            "database": {
                "path": os.path.join(self.config_dir, "packages.db"),
                "backup_count": 3
            },

            # 日志配置
            "logging": {
                "level": "info",  # debug, info, warning, error, critical
                "file": os.path.join(self.config_dir, "aur-checker.log"),
                "console": True,
                "max_size": 10 * 1024 * 1024,  # 10MB
                "max_files": 5
            },

            # AUR配置
            "aur": {
                "base_url": "https://aur.archlinux.org",
                "timeout": 30  # 30秒
            },

            # 上游检查配置
            "upstream": {
                "timeout": 30,  # 30秒
                "user_agent": "AUR-Update-Checker/1.0",
                "cache_time": 24 * 60 * 60,  # 24小时（秒）
                "retry": {
                    "count": 3,
                    "delay": 1  # 1秒
                }
            },

            # GitHub API配置
            "github": {
                "api_url": "https://api.github.com",
                "token": "",  # 用户需要提供自己的令牌
                "per_page": 100
            },

            # Gitee API配置
            "gitee": {
                "api_url": "https://gitee.com/api/v5",
                "token": "",  # 用户需要提供自己的令牌
                "per_page": 100
            },

            # GitLab API配置
            "gitlab": {
                "api_url": "https://gitlab.com/api/v4",
                "token": "",  # 用户需要提供自己的令牌
                "per_page": 100
            },

            # NPM配置
            "npm": {
                "registry": "https://registry.npmjs.org"
            },

            # PyPI配置
            "pypi": {
                "api_url": "https://pypi.org/pypi"
            },

            # 系统配置
            "system": {
                "temp_dir": os.path.join(tempfile.gettempdir(), "aur-update-checker"),
                "concurrent_checks": 5,  # 同时检查的包数量
                "package_manager": "auto"  # auto, yay, paru, aurman等
            },

            # 外部工具配置
            "tools": {
                "curl_path": "",        # curl可执行文件路径，为空则使用系统默认
                # 已删除浏览器相关配置，使用playwright自带的浏览器
            },

            # 定时检查配置
            "scheduler": {
                "enabled": True,         # 是否启用定时检查
                "aur_check_interval": 24,  # AUR版本检查间隔，单位为小时
                "upstream_check_interval": 48,  # 上游版本检查间隔，单位为小时
                "check_on_startup": True,  # 启动时是否检查
                "notification_enabled": True  # 是否启用通知
            },

            # UI配置
            "ui": {
                "theme": "system",  # system, light, dark
                "font_size": 12,
                "show_tray_icon": True,
                "minimize_to_tray": True,
                "start_minimized": False,
                "show_name": True,
                "show_aur_version": True,
                "show_upstream_version": True,
                "show_status": True,
                "show_aur_check_time": True,
                "show_upstream_check_time": True,
                "show_checker_type": True,
                "show_upstream_url": True,
                "show_notes": True,
                "close_action": "minimize",
                "show_minimize_notification": True,
                "text_alignment": {
                    "name": "center",
                    "aur_version": "center",
                    "upstream_version": "center",
                    "status": "center",
                    "aur_check_time": "center",
                    "upstream_check_time": "center",
                    "checker_type": "center",
                    "upstream_url": "center",
                    "notes": "center"
                }
            }
        }

    def _load_config(self):
        """加载用户配置"""
        try:
            if os.path.exists(self.config_file):
                self.logger.debug(f"从 {self.config_file} 加载配置")
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)

                # 深度合并配置
                self.config = self._merge_configs(self.config, user_config)
                self.logger.debug("配置加载成功")
            else:
                self.logger.info(f"配置文件不存在，创建默认配置模板: {self.config_file}")
                # 创建默认配置模板
                self._create_default_template()
        except Exception as e:
            self.logger.error(f"加载配置时出错: {str(e)}")
            self.logger.info("使用默认配置")
            
    def _create_default_template(self):
        """创建默认配置模板文件"""
        try:
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # 添加配置文件注释
            config_with_comments = {
                "# 配置文件说明": "这是AUR Update Checker的配置文件，可以根据需要修改以下配置项",
                "# 配置文件版本": "1.0.0",
                "# 最后更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "# 提示": "可以通过环境变量AUR_UPDATE_CHECKER_CONFIG或命令行参数--config指定配置文件路径",
                
                # 实际配置项
                **self.config
            }
            
            # 写入配置文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_with_comments, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"默认配置模板已创建: {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(f"创建默认配置模板时出错: {str(e)}")
            return False

    def _save_config(self):
        """保存配置到文件"""
        try:
            self.logger.debug(f"开始保存配置到 {self.config_file}")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # 使用临时文件进行原子写入
            temp_file = None
            try:
                # 创建临时文件
                temp_file = self.config_file + '.tmp'
                
                # 写入临时文件
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
                
                # 替换原文件
                if os.path.exists(self.config_file):
                    os.replace(temp_file, self.config_file)
                else:
                    os.rename(temp_file, self.config_file)
                
                self.logger.info(f"配置已成功保存到 {self.config_file}")
                return True
            except Exception as e:
                self.logger.error(f"保存配置时出错: {str(e)}")
                # 清理临时文件
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                return False
        except Exception as e:
            self.logger.error(f"保存配置过程中发生严重错误: {str(e)}")
            return False

    def _merge_configs(self, target, source):
        """深度合并配置对象

        Args:
            target: 目标配置字典
            source: 源配置字典

        Returns:
            dict: 合并后的配置字典
        """
        result = target.copy()

        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(target[key], value)
            else:
                result[key] = value

        return result

    def get(self, key, default_value=None):
        """获取指定配置

        Args:
            key: 配置键，支持点号分隔的嵌套键，例如 'database.path'
            default_value: 如果配置不存在，返回的默认值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if not isinstance(value, dict) or k not in value:
                return default_value
            value = value[k]

        return value

    def set(self, key, value, auto_save=False):
        """设置指定配置

        Args:
            key: 配置键，支持点号分隔的嵌套键
            value: 配置值
            auto_save: 是否自动保存配置，默认为False

        Returns:
            ConfigModule: 返回自身, 支持链式调用
        """
        keys = key.split('.')
        current = self.config

        for i in range(len(keys) - 1):
            k = keys[i]
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value
        
        if auto_save:
            self._save_config()

        return self

    def get_config(self):
        """获取完整配置

        Returns:
            dict: 完整配置字典
        """
        return self.config.copy()

    def __setitem__(self, key, value):
        """实现字典风格的赋值操作

        Args:
            key: 配置键
            value: 配置值
        """
        self.set(key, value)
        return self.config

    def update_config(self, new_config):
        """更新配置

        Args:
            new_config: 新配置字典

        Returns:
            ConfigModule: 返回自身, 支持链式调用
        """
        self.config = self._merge_configs(self.config, new_config)
        self._save_config()
        return self

    def reset_to_default(self):
        """重置为默认配置

        Returns:
            ConfigModule: 返回自身, 支持链式调用
        """
        self.config = self._load_default_config()
        self._save_config()
        return self
