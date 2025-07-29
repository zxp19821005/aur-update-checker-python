# -*- coding: utf-8 -*-
from typing import Dict, List, Optional, Tuple, Union, Any
import re
import aiohttp
from urllib.parse import urlparse, urljoin
from datetime import datetime


class VersionProcessor:
    """版本处理器，用于清理、规范化和提取版本信息"""

    def __init__(self, logger: Any, package_config: Optional[Dict[str, Any]] = None) -> None:
        """初始化版本处理器

        Args:
            logger: 日志模块实例
            package_config: 软件包配置
        """
        self.logger = logger
        self.package_config = package_config

    def parse_arch_version_string(self, version_str: Optional[str]) -> Dict[str, str]:
        """解析Arch/AUR版本字符串 (epoch:version-release)

        Args:
            version_str: 版本字符串

        Returns:
            dict: 包含解析后的epoch, version, release信息的字典
        """
        if not version_str:
            return {"version": "", "epoch": "", "release": ""}

        epoch: str = ""
        version: str = ""
        release: str = ""

        # 检查是否有 epoch (格式为 epoch:version-release)
        epoch_parts: List[str] = version_str.split(":")
        if len(epoch_parts) > 1:
            epoch = epoch_parts[0]
            version_str = ":".join(epoch_parts[1:])

        # 分离 version 和 release (格式为 version-release)
        release_parts: List[str] = version_str.split("-")
        if len(release_parts) > 1:
            release = release_parts[-1]
            version = "-".join(release_parts[:-1])
        else:
            version = version_str

        # 将版本号中的下划线(_)转换为连字符(-)，以便与上游版本格式匹配
        normalized_version: str = version.replace("_", "-")
        if normalized_version != version:
            self.logger.debug(f"版本号已标准化: {version} -> {normalized_version}")
            version = normalized_version

        return {"epoch": epoch, "version": version, "release": release}

    def clean_version(self, version: Optional[str]) -> Optional[str]:
        """清理版本字符串，移除不必要的字符

        Args:
            version: 原始版本字符串

        Returns:
            str: 清理后的版本字符串
        """
        if version is None:
            return None

        # 移除文件扩展名（如 .zip, .tar.gz 等）
        cleaned_version: str = re.sub(r"\.(zip|tar\.gz|tgz|rpm|deb|exe|dmg|pkg)$", "", version, flags=re.IGNORECASE)
        # 移除其他常见干扰字符
        cleaned_version = re.sub(r"[-_]v?", "", cleaned_version)
        return cleaned_version

    def normalize_version(self, version: Optional[str]) -> Optional[str]:
        """规范化版本字符串，确保格式统一

        Args:
            version: 清理后的版本字符串

        Returns:
            str: 规范化后的版本字符串
        """
        if version is None:
            return None

        # 确保版本号以数字开头
        normalized_version: str = re.sub(r"^[^0-9]*", "", version)
        # 移除末尾的非数字字符
        normalized_version = re.sub(r"[^0-9.]*$", "", normalized_version)
        return normalized_version

    def extract_semantic_version(self, version: Optional[str], keep_full_version: bool = False) -> Optional[str]:
        """提取语义化版本号（如 1.2.3）

        Args:
            version: 规范化后的版本字符串
            keep_full_version: 是否保留完整版本号

        Returns:
            str: 语义化版本号
        """
        if version is None:
            return None

        # 提取语义化版本号（如 1.2.3）
        match = re.search(r"(\d+\.\d+\.\d+)", version)
        if match:
            return match.group(1)
        elif keep_full_version:
            return version
        else:
            return None

    def extract_version_from_text(self, text: Optional[str]) -> Optional[str]:
        """从文本中提取版本号

        Args:
            text: 包含版本号的文本

        Returns:
            str: 提取到的版本号
        """
        if text is None:
            return None

        # 尝试匹配常见的版本号格式
        patterns: List[str] = [
            r"(\d+\.\d+\.\d+\.\d+)",  # 四段式 1.2.3.4
            r"(\d+\.\d+\.\d+)",  # 标准三段式 1.2.3
            r"(\d+\.\d+)",        # 两段式 1.2
            r"(\d+)",             # 单数字 1
            r"[_-](\d+\.\d+\.\d+)", # 下划线或连字符后跟版本 _1.2.3 或 -1.2.3
            r"[_-](\d+\.\d+)",    # 下划线或连字符后跟版本 _1.2 或 -1.2
            r"[_-](\d+)",         # 下划线或连字符后跟版本 _1 或 -1
            r"/(\d+\.\d+\.\d+)/", # 斜杠分隔的版本 /1.2.3/
            r"/(\d+\.\d+)/",      # 斜杠分隔的版本 /1.2/
            r"/(\d+)/",           # 斜杠分隔的版本 /1/
            r"/([^/]+?)-(\d+\.\d+\.\d+)", # 文件名格式 name-1.2.3
            r"/([^/]+?)-(\d+\.\d+)",      # 文件名格式 name-1.2
            r"/([^/]+?)-(\d+)",           # 文件名格式 name-1
            r"([^/]+?)-(\d+\.\d+\.\d+)",  # 文件名格式 name-1.2.3
            r"([^/]+?)-(\d+\.\d+)",       # 文件名格式 name-1.2
            r"([^/]+?)-(\d+)"             # 文件名格式 name-1
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                # 根据正则表达式的不同，版本号可能在不同的捕获组中
                # 尝试获取最后一个非空的捕获组
                for i in range(len(match.groups()), 0, -1):
                    if match.group(i):
                        return match.group(i)

        return None

    def is_version_similar(self, version: Optional[str], version_pattern: Optional[str]) -> bool:
        """
        检查版本号是否与version_pattern类似

        Args:
            version: 待检查的版本号
            version_pattern: 版本模式（如x.y）

        Returns:
            bool: 是否类似
        """
        if not version or not version_pattern:
            return False

        # 将版本号按点分割
        version_parts: List[str] = version.split('.')
        pattern_parts: List[str] = version_pattern.split('.')

        # 检查部分数量是否一致
        if len(version_parts) < len(pattern_parts):
            # 允许部分匹配，例如 "6.37" 可以匹配 "x.y" 或 "x.y.z"
            return len(version_parts) >= 2  # 至少需要两个部分

        # 检查每个部分是否为数字
        for part in version_parts:
            if not part.isdigit():
                return False

        return True

    def get_latest_version(self, versions: List[Optional[str]]) -> Optional[str]:
        """比较多个版本号，获取最新版本

        使用版本号比较规则来确定哪个版本是最新的。
        - 先将版本号按点分割成数组，如1.2.3分割成[1,2,3]
        - 然后按照数组位置依次比较数字大小

        Args:
            versions: 版本号列表

        Returns:
            str: 最新的版本号
        """
        if not versions:
            self.logger.warning("传入的版本列表为空")
            return None

        if len(versions) == 1:
            return versions[0]

        self.logger.debug(f"比较版本: {versions}")

        # 移除非有效版本
        valid_versions: List[Tuple[str, str]] = []
        for v in versions:
            if v is None:
                continue

            # 清理版本字符串，确保格式统一
            cleaned = self.clean_version(v)
            normalized = self.normalize_version(cleaned)
            if normalized:
                valid_versions.append((v, normalized))

        if not valid_versions:
            self.logger.warning("没有有效的版本可比较")
            return None

        if len(valid_versions) == 1:
            return valid_versions[0][0]  # 返回原始版本字符串

        # 比较版本
        latest_version: Tuple[str, str] = valid_versions[0]  # 初始设置第一个版本为最新

        for original_ver, normalized_ver in valid_versions[1:]:
            # 获取版本号的各部分
            current_parts: List[str] = normalized_ver.split(".")
            latest_parts: List[str] = latest_version[1].split(".")

            # 逐部分比较
            is_newer: bool = False
            for i in range(max(len(current_parts), len(latest_parts))):
                # 如果某个版本的部分数量不足，则认为该部分为0
                current_part: int = int(current_parts[i]) if i < len(current_parts) else 0
                latest_part: int = int(latest_parts[i]) if i < len(latest_parts) else 0

                if current_part > latest_part:
                    is_newer = True
                    break
                elif current_part < latest_part:
                    break  # 当前版本低，不是最新版
                # 如果相等则继续比较下一部分

            if is_newer:
                latest_version = (original_ver, normalized_ver)
                self.logger.debug(f"发现新版本: {latest_version[0]}")

        # 额外检查：确保返回的版本号格式与AUR版本格式一致
        if self.package_config and self.package_config.get("version_pattern"):
            version_pattern = self.package_config["version_pattern"]
            if not self.is_version_similar(latest_version[0], version_pattern):
                self.logger.warning(f"最新版本 {latest_version[0]} 与AUR版本格式 {version_pattern} 不匹配")
                # 尝试从所有版本中找出格式匹配的最新版本
                for ver, norm_ver in valid_versions:
                    if self.is_version_similar(ver, version_pattern):
                        if self.get_latest_version([latest_version[0], ver]) == ver:
                            latest_version = (ver, norm_ver)
                            self.logger.debug(f"选择格式匹配的最新版本: {latest_version[0]}")
                            break

        self.logger.debug(f"最终确定的最新版本是: {latest_version[0]}")
        return latest_version[0]  # 返回原始版本字符串
