# -*- coding: utf-8 -*-
import asyncio
import re
import os
import subprocess
import tempfile
from datetime import datetime
from .base_checker import BaseChecker
from ..version_processor import VersionProcessor

class UpstreamCurlChecker(BaseChecker):
    """使用curl获取上游版本信息的检查器"""

    def __init__(self, logger, config=None, main_checker=None):
        """初始化curl检查器

        Args:
            logger: 日志模块实例
            config: 配置模块实例（可选）
            main_checker: 主检查器实例，用于版本比较（可选）
        """
        super().__init__(logger)
        self.logger.debug("curl上游检查器初始化")
        self.config = config
        self.main_checker = main_checker
        self.package_config = None
        self.version_processor = VersionProcessor(logger, self.package_config)

    def extract_version_from_context(self, context, version_extract_key, check_test_versions=False):
        """
        从上下文中提取版本号的增强版提取逻辑

        Args:
            context: 包含版本号的上下文文本
            version_extract_key: 版本提取关键字
            check_test_versions: 是否检查测试版本(alpha、beta、rc等)

        Returns:
            str: 提取到的版本号，如果未找到则为None
        """
        try:
            self.logger.debug(f"开始提取版本，提取键: '{version_extract_key}'")
            # 先检查是否包含文件大小（如 "10.4 MB", "4.0 MB"），避免将其误认为版本号
            size_patterns = [r'(\d+\.\d+)\s*[KMG]B', r'(\d+\.\d+)\s*(KB|MB|GB)', r'title="(\d+\.\d+)\s*[KMG]B"']
            file_sizes = []
            for pattern in size_patterns:
                size_matches = re.findall(pattern, context)
                if size_matches:
                    file_sizes.extend([m[0] if isinstance(m, tuple) else m for m in size_matches])
            self.logger.debug(f"检测到可能的文件大小: {file_sizes}")

            # 统一的版本提取策略：获取关键字前后100个字符，并从中提取版本号
            if version_extract_key and version_extract_key in context:
                self.logger.debug(f"找到关键字: '{version_extract_key}'，获取前后100个字符进行分析")

                # 找到关键字的所有位置
                positions = [m.start() for m in re.finditer(re.escape(version_extract_key), context)]
                version_candidates = []

                for pos in positions:
                    # 获取关键字前后100个字符的上下文
                    start = max(0, pos - 100)
                    end = min(len(context), pos + len(version_extract_key) + 100)
                    surrounding_text = context[start:end]

                    self.logger.debug(f"提取上下文: '{surrounding_text}'")

                    # 首先尝试直接从关键字后提取版本
                    # 例如对于 xxcVersion: "9.3" 这种格式，直接提取引号中的内容
                    # 尝试几种常见的格式模式
                    direct_patterns = [
                        # 从文件名中提取版本号：yozo-office_9.0.3988.101ZH.S1_amd64.deb
                        r'[^0-9]*(\d+\.\d+\.\d+\.\d+[A-Za-z0-9._-]+)' + re.escape(version_extract_key),
                        # xxcVersion: "9.3"
                        re.escape(version_extract_key) + r'"([0-9.]+)"',
                        # xxcVersion: "9.3",
                        re.escape(version_extract_key) + r'"([0-9.]+)"[,\s]',
                        # xxcVersion: 9.3,
                        re.escape(version_extract_key) + r'([0-9.]+)[,\s]',
                        # xxcVersion: 9.3
                        re.escape(version_extract_key) + r'([0-9.]+)'
                    ]

                    direct_version = None
                    for pattern in direct_patterns:
                        direct_match = re.search(pattern, surrounding_text)
                        if direct_match:
                            direct_version = direct_match.group(1)
                            # 清理版本号，移除末尾的点号（通常是扩展名的一部分）
                            direct_version = direct_version.rstrip('.')
                            if direct_version not in file_sizes and direct_version not in version_candidates:
                                self.logger.debug(f"从关键字后直接提取到版本: {direct_version} (使用模式: {pattern})")
                                version_candidates.append(direct_version)
                                break

                    if direct_version:
                        continue  # 如果直接找到了版本号，优先使用

                    # 在上下文中查找版本号模式
                    # 根据是否检查测试版本决定使用的匹配模式
                    if check_test_versions:
                        # 包括测试版本的完整模式列表
                        version_patterns = [
                            # 匹配常见测试版本格式
                            r'(\d+\.\d+\.\d+(?:-(?:alpha|beta|rc|dev|preview|pre|snapshot|nightly|test)(?:\.\d+)?)?)',
                            # 匹配数字带字母的版本，如 1.2.3a, 1.2.3b1
                            r'(\d+\.\d+\.\d+[a-zA-Z]\d*)',
                            # 匹配 1.2.3.4 格式
                            r'(\d+\.\d+\.\d+\.\d+)',
                            # 匹配 1.2.3 格式
                            r'(\d+\.\d+\.\d+)',
                            # 匹配 1.2 格式
                            r'(\d+\.\d+)'
                        ]
                        self.logger.debug("启用测试版本检查，将匹配alpha/beta/rc等测试版本")
                    else:
                        # 仅匹配稳定版本的模式
                        version_patterns = [
                            # 特殊格式：从文件名中提取带字母和标记的产品版本号（如从yozo-office_9.0.3988.101ZH.S1_amd64.deb提取9.0.3988.101ZH.S1）
                            r'[^0-9]*(\d+\.\d+\.\d+\.\d+[A-Za-z0-9._-]+)_amd64\.deb',
                            # 带字母后缀的版本号（但排除明确的开发版标记）
                            r'[^0-9]*(\d+\.\d+\.\d+[A-Za-z0-9._-]+)(?!(?:alpha|beta|rc|dev))_amd64\.deb',
                            # 先匹配完整稳定版本格式，如 3.16 或 3.16.2
                            r'[^0-9](\d+\.\d+\d*(?:\.\d+)*)(?![a-zA-Z])',
                            # 稳定版本格式，排除包含alpha/beta/rc等标记的版本
                            r'(\d+\.\d+\.\d+)(?![a-zA-Z-])',
                            # 匹配 1.2.3.4 格式，确保后面不跟字母
                            r'(\d+\.\d+\.\d+\.\d+)(?![a-zA-Z-])',
                            # 匹配 1.2 格式，确保后面不跟字母
                            r'(\d+\.\d+)(?![a-zA-Z-])'
                        ]
                        self.logger.debug("禁用测试版本检查，将只匹配稳定版本")

                    for pattern in version_patterns:
                        matches = re.findall(pattern, surrounding_text)
                        if matches:
                            for match in matches:
                                # 检查版本号是否来自于开发版文件名
                                if not check_test_versions:
                                    # 如果上下文中包含dev、alpha、beta、rc等关键词，且不检查测试版本，则跳过
                                    dev_keywords = ['dev', 'alpha', 'beta', 'rc', 'snapshot', 'nightly', 'preview', 'test']
                                    # 检查关键词是否出现在版本号附近
                                    is_dev_version = any(keyword in surrounding_text.lower() for keyword in dev_keywords)
                                    if is_dev_version:
                                        self.logger.debug(f"跳过测试版本: {match} (上下文包含测试版本关键词)")
                                        continue

                                # 清理版本号，移除末尾的点号
                                match = match.rstrip('.')
                                if match not in file_sizes and match not in version_candidates:
                                    version_candidates.append(match)

                if version_candidates:
                    # 排序版本候选项，返回语义上最高的版本
                    # 简单排序：按长度和数值大小
                    version_candidates.sort(key=lambda v: (len(v.split('.')), [int(x) if x.isdigit() else x for x in re.findall(r'\d+|[a-zA-Z]+', v)]), reverse=True)

                    self.logger.info(f"从关键字上下文中提取到版本: {version_candidates[0]}")
                    return version_candidates[0]
                else:
                    self.logger.debug("在关键字上下文中未找到版本号")
            else:
                # 如果没有找到关键字或没有提供关键字，尝试在整个内容中查找常见的版本号模式
                self.logger.debug("未找到关键字或未提供关键字，尝试在整个内容中查找版本号")
                common_patterns = [
                    # 针对 "Latest version: 9.3" 这样的文本
                    r'[Ll]atest(?:\s+[Vv]ersion)?(?:\s+is)?(?:\s*[:-])?\s*(?:v)?(\d+\.\d+(?:\.\d+)?)',
                    # 针对 "当前版本: 9.3" 这样的文本
                    r'当前(?:版本|版本号)(?:\s*[:-])?\s*(?:v)?(\d+\.\d+(?:\.\d+)?)',
                    # 针对 "Version 9.3" 这样的文本
                    r'[Vv]ersion\s+(?:v)?(\d+\.\d+(?:\.\d+)?)',
                    # 针对 "v9.3" 这样的文本
                    r'[Vv](\d+\.\d+(?:\.\d+)?)',
                    # 通用版本号格式
                    r'(\d+\.\d+(?:\.\d+)?)'
                ]

                for pattern in common_patterns:
                    matches = re.findall(pattern, context)
                    if matches:
                        # 过滤掉可能是文件大小的匹配
                        filtered_matches = [m for m in matches if m not in file_sizes]
                        if filtered_matches:
                            self.logger.debug(f"找到可能的版本号: {filtered_matches}")
                            # 按版本号长度和数值排序
                            filtered_matches.sort(key=lambda v: (len(v.split('.')), [int(x) if x.isdigit() else x for x in re.findall(r'\d+|[a-zA-Z]+', v)]), reverse=True)
                            self.logger.info(f"从全文提取到可能的版本号: {filtered_matches[0]}")
                            return filtered_matches[0]

        except Exception as e:
            self.logger.warning(f"从上下文提取版本号时出错: {str(e)}")

        return None

    async def check_version(self, package_name, url, version_pattern_regex=None, **kwargs):
        """检查上游版本

        Args:
            package_name: 软件包名称
            url: 上游URL
            version_pattern_regex: 版本提取正则表达式
            **kwargs: 其他参数，如version_extract_key, aur_version, version_pattern, check_test_versions等

        Returns:
            dict: 包含版本信息的字典
        """
        self.logger.debug(f"使用curl检查器检查软件包 {package_name} 的版本")

        # 从kwargs获取参数
        version_extract_key = kwargs.get("version_extract_key")
        check_test_versions = kwargs.get("check_test_versions", False)
        aur_version = kwargs.get("aur_version")
        version_pattern = kwargs.get("version_pattern")

        try:
            # 使用临时文件保存curl输出
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

            # 执行curl命令获取页面内容
            curl_cmd = ["curl", "-L", "-s", "-o", temp_path, url]
            process = await asyncio.create_subprocess_exec(*curl_cmd)
            await process.communicate()

            if process.returncode != 0:
                self.logger.error(f"curl命令执行失败: {url}")
                return {
                    "name": package_name,
                    "success": False, 
                    "message": "Curl命令执行失败"
                }

            # 读取临时文件内容
            with open(temp_path, "r", errors="ignore") as f:
                content = f.read()

            # 清理临时文件
            try:
                os.unlink(temp_path)
            except:
                pass

            # 优先使用传入的version_pattern_regex
            version = None
            if version_pattern_regex:
                try:
                    pattern = re.compile(version_pattern_regex)
                    match = pattern.search(content)
                    if match:
                        version = match.group(1) if match.groups() else match.group(0)
                        self.logger.info(f"使用传入的版本模式提取到版本号: {version}")

                        # 尝试验证版本合理性
                        if aur_version and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                            if self.main_checker._is_version_similar(version, version_pattern):
                                self.logger.info(f"提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                                return {
                                    "name": package_name,
                                    "success": True,
                                    "version": version,
                                    "date": datetime.now().isoformat(),
                                    "message": "成功使用传入模式提取版本"
                                }
                            else:
                                self.logger.debug(f"提取的版本 {version} 与AUR版本格式不匹配，继续尝试其他方法")
                        else:
                            # 无法验证版本合理性，但仍然返回结果
                            return {
                                "name": package_name,
                                "success": True,
                                "version": version,
                                "date": datetime.now().isoformat(),
                                "message": "成功使用传入模式提取版本（未验证格式）"
                            }
                except Exception as e:
                    self.logger.debug(f"使用传入的版本模式提取失败: {str(e)}")

            # 如果无法使用正则表达式提取，则使用提取函数
            self.logger.debug(f"使用版本提取键: '{version_extract_key}'")
            self.logger.debug(f"是否检查测试版本: {check_test_versions}")
            version = self.extract_version_from_context(content, version_extract_key or "", check_test_versions)

            if version:
                self.logger.info(f"提取到上游版本: {version}")

                # 尝试验证版本合理性
                if aur_version and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                    if self.main_checker._is_version_similar(version, version_pattern):
                        self.logger.info(f"提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                    else:
                        self.logger.debug(f"提取的版本 {version} 与AUR版本格式不匹配，但仍然返回")

                return {
                    "name": package_name,
                    "success": True,
                    "version": version,
                    "date": datetime.now().isoformat(),
                    "message": "成功提取版本"
                }
            else:
                # 尝试从URL中提取版本信息（特别是针对下载页面）
                if aur_version:
                    # 直接在URL中查找完全匹配的版本号
                    escaped_version = re.escape(aur_version)
                    exact_match = re.search(f"(?:^|[^0-9])({escaped_version})(?:[^0-9]|$)", url)
                    if exact_match:
                        version = exact_match.group(1)
                        self.logger.info(f"在URL中找到与AUR版本完全匹配的版本号: {version}")
                        return {
                            "name": package_name,
                            "success": True,
                            "version": version,
                            "date": datetime.now().isoformat(),
                            "message": "从URL中提取到与AUR版本匹配的版本号"
                        }

                self.logger.warning(f"无法从URL提取版本: {url}")
                return {
                    "name": package_name,
                    "success": False,
                    "message": "无法提取版本"
                }

        except Exception as e:
            self.logger.error(f"检查版本时出错: {str(e)}")
            return {
                "name": package_name,
                "success": False,
                "message": str(e)
            }