# -*- coding: utf-8 -*-
import re
import json
import asyncio
import aiohttp
import ssl
from datetime import datetime

from .base_checker import BaseChecker
from ..version_processor import VersionProcessor

class UpstreamJsonChecker(BaseChecker):
    """JSON API 上游检查器"""

    def __init__(self, logger, config=None, main_checker=None):
        super().__init__(logger)
        self.config = config
        self.main_checker = main_checker
        self.version_processor = VersionProcessor(logger, self.package_config)

    def _log_debug_info(self, package_name, url, version_extract_key, aur_version, version_pattern, version_pattern_regex):
        """记录调试信息"""
        self.logger.debug(f"包名: {package_name}, URL: {url}")
        self.logger.debug(f"版本提取路径: {version_extract_key}")
        self.logger.debug(f"AUR参考版本: {aur_version}")
        self.logger.debug(f"版本模式: {version_pattern}")
        self.logger.debug(f"版本正则表达式: {version_pattern_regex}")
    async def check_version(self, package_name, url, version_pattern_regex=None, **kwargs):
        """从JSON API获取版本信息"""
        self.logger.info(f"正在检查JSON API上游版本: {url}")

        version_extract_key = kwargs.get('version_extract_key')
        aur_version = kwargs.get('aur_version')
        version_pattern = kwargs.get('version_pattern')

        self._log_debug_info(package_name, url, version_extract_key, aur_version, version_pattern, version_pattern_regex)

        if not version_extract_key:
            self.logger.info("未提供version_extract_key参数，将尝试从常见路径提取版本号")

        try:
            # 获取API响应
            data = await self._fetch_json_data(url)
            if not data:
                return {"name": package_name, "success": False, "version": None, "message": "获取数据失败"}

            # 规范化输出JSON响应，便于调试
            self.logger.debug(f"JSON API响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")

            # 提取版本
            version = None
            version_extraction_methods = [
                lambda: self._extract_by_path(data, version_extract_key),
            ]

            for method in version_extraction_methods:
                version = method()
                if version:
                    processed_version = str(version).strip()

                    # 使用AUR版本标准化
                    if aur_version and self.version_processor:
                        processed_version = self.version_processor.normalize_version(processed_version)

                    # 验证版本格式
                    if version_pattern_regex and isinstance(processed_version, str):
                        match = re.search(version_pattern_regex, processed_version)
                        if not match:
                            self.logger.warning(f"版本 {processed_version} 不符合正则表达式 {version_pattern_regex}")
                            # 如果版本不符合正则表达式，尝试从整个JSON数据中搜索版本号
                            version = self._extract_version_from_string(str(data))
                            if version:
                                processed_version = str(version).strip()
                                if aur_version and self.version_processor:
                                    processed_version = self.version_processor.normalize_version(processed_version)
                    elif version_pattern and isinstance(processed_version, str):
                        # 检查版本是否与version_pattern类似
                        if self.main_checker is not None and not self.main_checker._is_version_similar(processed_version, version_pattern):
                            self.logger.warning(f"版本 {processed_version} 与模式 {version_pattern} 不匹配")
                            # 如果版本与模式不匹配，尝试从整个JSON数据中搜索版本号
                            version = self._extract_version_from_string(str(data))
                            if version:
                                processed_version = str(version).strip()
                                if aur_version and self.version_processor:
                                    processed_version = self.version_processor.normalize_version(processed_version)

                    # 构建结果
                    result = self._build_result(package_name, processed_version, aur_version)
                    self.logger.info(f"成功提取版本号: {processed_version}")
                    return result

            # 如果路径提取失败，尝试从其他常见路径提取版本号
            alt_paths = ['version', 'latest_version', 'data.version', 'data.latest_version']
            for alt_path in alt_paths:
                try:
                    temp_version = data
                    for key in alt_path.split('.'):
                        temp_version = temp_version[key]
                    processed_version = str(temp_version).strip()
                    if aur_version and self.version_processor:
                        processed_version = self.version_processor.normalize_version(processed_version)

                    result = self._build_result(package_name, processed_version, aur_version)
                    self.logger.info(f"从备用路径 {alt_path} 提取到版本号: {processed_version}")
                    return result
                except (KeyError, TypeError):
                    continue

            # 如果备用路径也失败，尝试从整个JSON数据中搜索版本号
            version = self._extract_version_from_string(str(data))
            if version:
                processed_version = str(version).strip()
                if aur_version and self.version_processor:
                    processed_version = self.version_processor.normalize_version(processed_version)

                result = self._build_result(package_name, processed_version, aur_version)
                self.logger.info(f"成功从字符串中提取版本号: {processed_version}")
                return result

            self.logger.warning(f"在JSON响应中未找到版本路径: {version_extract_key}")
            return {
                "name": package_name,
                "success": False,
                "version": None,
                "upstream_version": None,
                "message": f"未找到版本路径: {version_extract_key}",
                "update_date": None
            }

        except Exception as e:
            self.logger.error(f"检查JSON API版本时出错: {str(e)}")
            return {
                "name": package_name,
                "success": False,
                "version": None,
                "upstream_version": None,
                "message": f"检查出错: {str(e)}",
                "update_date": None
            }

    async def _fetch_json_data(self, url):
        """获取和解析JSON数据"""
        ssl_context = ssl.create_default_context()
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate"
        }

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url, headers=headers, timeout=aiohttp.ClientTimeout(total=30), ssl=ssl_context
                    ) as response:
                        if response.status != 200:
                            raise aiohttp.ClientError(f"HTTP状态码错误: {response.status}")

                        text = await response.text()
                        data = json.loads(text)

                        if not isinstance(data, dict):
                            raise ValueError("API响应不是有效的JSON对象")

                        if 'code' in data and str(data['code']) not in ('200', '0'):
                            raise ValueError(f"API返回错误代码: {data.get('message', '未知错误')}")

                        return data
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"请求失败，第{attempt + 1}次重试: {str(e)}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    self.logger.error(f"请求发生错误: {str(e)}")
                    return None
        return None

    def _build_result(self, package_name, processed_version, aur_version):
        """
        构建统一的结果字典

        Args:
            package_name: 包名
            processed_version: 处理后的版本号
            aur_version: AUR参考版本

        Returns:
            dict: 统一格式的结果字典
        """
        return {
            "name": package_name,
            "success": True,
            "version": processed_version,
            "upstream_version": processed_version,
            "message": "版本检查成功",
            "update_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "aur_reference": aur_version
        }

    def _extract_version_from_string(self, text):
        """
        从字符串中提取版本号

        Args:
            text: 输入字符串

        Returns:
            提取的版本号或None
        """
        if not text:
            return None

        # 使用从main_checker传递的version_pattern提取版本号
        if hasattr(self, 'package_config') and self.package_config.get('version_pattern'):
            version_pattern = self.package_config['version_pattern']
            # 将version_pattern转换为正则表达式
            pattern = version_pattern.replace('.', r'\.').replace('x', r'\d+')
            match = re.search(pattern, text)
            if match:
                version = match.group()
                self.logger.info(f"使用version_pattern提取到版本号: {version}")
                return version

        # 如果version_pattern未定义或未匹配到，尝试默认的版本号格式
        version_match = re.search(r'(?:v|V)?(\d+(?:\.\d+)+)', text)
        if version_match:
            version = version_match.group(1)
            self.logger.debug(f"从字符串中提取到版本号: {version}")
            return version

        # 如果仍未找到，尝试从URL中提取版本号
        url_match = re.search(r'(?:v|V)?(\d+(?:\.\d+)+)', url if hasattr(self, 'url') else '')
        if url_match:
            version = url_match.group(1)
            self.logger.debug(f"从URL中提取到版本号: {version}")
            return version

        self.logger.warning(f"无法从文本或URL中提取版本号: {text}")
        return None

    def _extract_by_path(self, data, path):
        """
        通用的路径提取方法，支持点分隔路径和数组索引

        Args:
            data: 输入的嵌套字典或列表
            path: 点分隔的路径字符串（支持数组索引，如 `data.versions.0` 或 `versions[0].version`）

        Returns:
            提取的值或None
        """
        if not path or not isinstance(path, str) or not data:
            return None

        try:
            parts = path.split('.')
            current = data

            for part in parts:
                if current is None:
                    self.logger.debug(f"路径解析中断: current is None at part '{part}'")
                    return None

                # 处理数组索引（如 `versions[0]`）
                if '[' in part and ']' in part:
                    array_name = part.split('[')[0]
                    try:
                        index = int(part.split('[')[1].split(']')[0])
                    except ValueError:
                        self.logger.debug(f"数组索引解析失败: part '{part}'")
                        return None

                    if (array_name in current and
                        isinstance(current[array_name], list) and
                        index >= 0 and
                        len(current[array_name]) > index):
                        current = current[array_name][index]
                    else:
                        self.logger.debug(f"数组索引越界或无效: array_name='{array_name}', index={index}")
                        return None
                # 处理数字索引（如 `data.versions.0`）
                elif part.isdigit():
                    if not isinstance(current, list):
                        self.logger.debug(f"需要列表类型但得到 {type(current)}")
                        return None

                    index = int(part)
                    if index < 0 or index >= len(current):
                        self.logger.debug(f"数组索引越界: index={index}, len={len(current)}")
                        return None
                    current = current[index]
                # 处理字典键
                elif isinstance(current, dict):
                    if part not in current:
                        self.logger.debug(f"键 '{part}' 在当前字典中不存在")
                        return None
                    current = current[part]
                else:
                    self.logger.debug(f"路径解析失败: 无法处理类型 {type(current)} 的 '{part}'")
                    return None

            # 处理最终结果
            if current is None:
                self.logger.debug(f"最终解析结果为None")
                return None
            if isinstance(current, (int, float, str)):
                return str(current)
            if isinstance(current, (dict, list)):
                self.logger.debug(f"路径解析失败: 最终结果为复杂类型 {type(current)}")
                return None

            return None
        except Exception as e:
            self.logger.debug(f"路径提取出错: {str(e)}")
            return None
