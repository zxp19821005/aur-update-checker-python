# -*- coding: utf-8 -*-
import requests
from datetime import datetime
from .version_processor import VersionProcessor

class AurCheckerModule:
    """AUR检查器模块，负责检查AUR软件包版本"""

    def __init__(self, logger, db_module):
        """初始化AUR检查器

        Args:
            logger: 日志模块实例
            db_module: 数据库模块实例
        """
        self.logger = logger
        self.db_module = db_module
        self.logger.debug("AUR 检查模块初始化")
        
        # 初始化版本处理器
        self.version_processor = VersionProcessor(logger)

        # AUR RPC API地址
        self.aur_rpc_url = "https://aur.archlinux.org/rpc/v5/info"

    async def check_aur_version(self, package_name, callback=None):
        """检查单个软件包的 AUR 版本

        Args:
            package_name: 软件包名称
            callback: 检查完成后的回调函数，接收包含版本信息的字典

        Returns:
            dict: 包含版本信息的字典
        """
        self.logger.info(f"开始检查 AUR 软件包: {package_name}")

        try:
            # 查询 AUR API
            response = requests.get(
                self.aur_rpc_url,
                params={"arg": package_name},
                timeout=10
            )

            if response.status_code != 200:
                raise Exception(f"AUR API 请求失败，状态码: {response.status_code}")

            data = response.json()

            if data["type"] != "multiinfo" or not data["results"] or len(data["results"]) == 0:
                self.logger.warning(f"软件包 {package_name} 在 AUR 中未找到")
                return {
                    "name": package_name,
                    "found": False,
                    "message": "在 AUR 中未找到该软件包"
                }

            # 在结果中查找匹配的软件包
            package_info = None
            for pkg in data["results"]:
                if pkg["Name"].lower() == package_name.lower():
                    package_info = pkg
                    break

            if not package_info:
                self.logger.warning(f"软件包 {package_name} 在 AUR 中未找到")
                return {
                    "name": package_name,
                    "found": False,
                    "message": "在 AUR 中未找到该软件包"
                }

            self.logger.debug(f"软件包信息: {package_info}")

            # 解析版本信息
            version_info = self._parse_version_string(package_info.get("Version", ""))

            # 如果提供了数据库模块，更新数据库中的信息
            if self.db_module:
                try:
                    self.db_module.update_aur_version(
                        package_info["Name"],
                        version_info["version"],
                        version_info["epoch"],
                        version_info["release"]
                    )
                    self.logger.debug(f"已更新数据库中 {package_name} 的 AUR 版本信息")
                except Exception as db_error:
                    self.logger.error(f"更新数据库中 {package_name} 的 AUR 版本信息时出错: {str(db_error)}")

            self.logger.info(f"软件包 {package_name} 检查完成，版本: {version_info['version']}")

            return {
                "name": package_info["Name"],
                "found": True,
                "version": version_info["version"],
                "epoch": version_info["epoch"],
                "release": version_info["release"],
                "last_modified": package_info.get("LastModified") and
                                datetime.fromtimestamp(package_info["LastModified"]).isoformat(),
                "success": True
            }

        except Exception as error:
            self.logger.error(f"检查软件包 {package_name} 时出错: {str(error)}")
            return {
                "name": package_name,
                "found": False,
                "message": str(error),
                "success": False
            }

    async def check_multiple_aur_versions(self, package_names):
        """批量检查多个软件包的 AUR 版本，使用AUR API的批量查询功能

        Args:
            package_names: 软件包名称列表

        Returns:
            list: 包含各个软件包版本信息的列表
        """
        if not package_names:
            self.logger.warning("没有要检查的AUR软件包")
            return []

        self.logger.info(f"开始批量检查 {len(package_names)} 个 AUR 软件包")

        # AUR API 每次请求限制包数量，将包列表分批处理
        batch_size = 50  # AUR API支持的最大批量查询数量
        results = []

        try:
            # 分批处理包
            for i in range(0, len(package_names), batch_size):
                batch = package_names[i:i+batch_size]
                self.logger.debug(f"处理批次 {i//batch_size + 1}，包含 {len(batch)} 个包")

                # 构建查询参数 - AUR API支持多个"arg[]"参数进行批量查询
                params = []
                for pkg in batch:
                    params.append(("arg[]", pkg))

                # 查询 AUR API
                response = requests.get(
                    self.aur_rpc_url,
                    params=params,
                    timeout=15  # 批量查询给予更多时间
                )

                if response.status_code != 200:
                    self.logger.error(f"AUR API 请求失败，状态码: {response.status_code}")
                    continue

                data = response.json()

                if data["type"] != "multiinfo" or not data["results"]:
                    self.logger.warning(f"批次 {i//batch_size + 1} 没有返回结果")
                    continue

                # 处理返回的包信息
                aur_packages = {pkg["Name"].lower(): pkg for pkg in data["results"]}

                # 更新数据库并构建结果
                for package_name in batch:
                    lower_name = package_name.lower()

                    if lower_name in aur_packages:
                        # 找到包
                        pkg_info = aur_packages[lower_name]
                        version_info = self._parse_version_string(pkg_info.get("Version", ""))

                        # 更新数据库
                        if self.db_module:
                            try:
                                self.db_module.update_aur_version(
                                    pkg_info["Name"],
                                    version_info["version"],
                                    version_info["epoch"],
                                    version_info["release"]
                                )
                            except Exception as db_error:
                                self.logger.error(f"更新数据库中 {package_name} 的 AUR 版本信息时出错: {str(db_error)}")

                        # 添加到结果
                        results.append({
                            "name": pkg_info["Name"],
                            "found": True,
                            "version": version_info["version"],
                            "epoch": version_info["epoch"],
                            "release": version_info["release"],
                            "last_modified": pkg_info.get("LastModified") and
                                            datetime.fromtimestamp(pkg_info["LastModified"]).isoformat(),
                            "success": True
                        })
                    else:
                        # 未找到包
                        results.append({
                            "name": package_name,
                            "found": False,
                            "message": "在 AUR 中未找到该软件包",
                            "success": True  # 查询成功，只是没找到包
                        })

                self.logger.info(f"批次 {i//batch_size + 1} 处理完成")

            self.logger.info(f"批量检查 AUR 完成，共 {len(results)} 个软件包")
            return results

        except Exception as error:
            self.logger.error(f"批量检查 AUR 版本时发生错误: {str(error)}")
            return results  # 返回已处理的结果



    def _parse_version_string(self, version_str):
        """解析版本字符串 (epoch:version-release)

        Args:
            version_str: 版本字符串

        Returns:
            dict: 包含解析后的epoch, version, release信息的字典
        """
        # 使用VersionProcessor解析Arch/AUR版本字符串格式
        return self.version_processor.parse_arch_version_string(version_str)
