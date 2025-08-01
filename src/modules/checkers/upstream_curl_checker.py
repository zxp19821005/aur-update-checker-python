# -*- coding: utf-8 -*-
import asyncio
import re
import os
import subprocess
import tempfile
from datetime import datetime
from contextlib import contextmanager
from .base_checker import BaseChecker
from ..version_processor import VersionProcessor

class UpstreamCurlChecker(BaseChecker):
    """使用curl获取上游版本信息的检查器"""
    
    # 版本模式常量
    SIZE_PATTERNS = [
        r'(\d+\.\d+)\s*[KMG]B', 
        r'(\d+\.\d+)\s*(KB|MB|GB)',
        r'title="(\d+\.\d+)\s*[KMG]B"'
    ]
    
    DIRECT_VERSION_PATTERNS = [
        r'[^0-9]*(\d+\.\d+\.\d+\.\d+[A-Za-z0-9._-]+){}',
        r'{}"([0-9.]+)"',
        r'{}"([0-9.]+)"[,\s]',
        r'{}([0-9.]+)[,\s]',
        r'{}([0-9.]+)'
    ]
    
    TEST_VERSION_PATTERNS = [
        r'(\d+\.\d+\.\d+(?:-(?:alpha|beta|rc|dev|preview|pre|snapshot|nightly|test)(?:\.\d+)?)?)',
        r'(\d+\.\d+\.\d+[a-zA-Z]\d*)',
        r'(\d+\.\d+\.\d+\.\d+)',
        r'(\d+\.\d+\.\d+)',
        r'(\d+\.\d+)'
    ]
    
    STABLE_VERSION_PATTERNS = [
        r'[^0-9]*(\d+\.\d+\.\d+\.\d+[A-Za-z0-9._-]+)_amd64\.deb',
        r'[^0-9]*(\d+\.\d+\.\d+[A-Za-z0-9._-]+)(?!(?:alpha|beta|rc|dev))_amd64\.deb',
        r'[^0-9](\d+\.\d+\d*(?:\.\d+)*)(?![a-zA-Z])',
        r'(\d+\.\d+\.\d+)(?![a-zA-Z-])',
        r'(\d+\.\d+\.\d+\.\d+)(?![a-zA-Z-])',
        r'(\d+\.\d+)(?![a-zA-Z-])'
    ]
    
    COMMON_VERSION_PATTERNS = [
        r'[Ll]atest(?:\s+[Vv]ersion)?(?:\s+is)?(?:\s*[:-])?\s*(?:v)?(\d+\.\d+(?:\.\d+)?)',
        r'当前(?:版本|版本号)(?:\s*[:-])?\s*(?:v)?(\d+\.\d+(?:\.\d+)?)',
        r'[Vv]ersion\s+(?:v)?(\d+\.\d+(?:\.\d+)?)',
        r'[Vv](\d+\.\d+(?:\.\d+)?)',
        r'(\d+\.\d+(?:\.\d+)?)'
    ]

    def __init__(self, logger, config=None, main_checker=None):
        super().__init__(logger)
        self.logger.debug("curl上游检查器初始化")
        self.config = config
        self.main_checker = main_checker
        self.package_config = None
        self.version_processor = VersionProcessor(logger, self.package_config)

    @contextmanager
    def _temp_curl_file(self, url):
        """临时文件上下文管理器"""
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
            
            yield temp_path
        finally:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except:
                pass

    def _get_file_sizes(self, context):
        """从上下文中提取文件大小"""
        file_sizes = []
        for pattern in self.SIZE_PATTERNS:
            size_matches = re.findall(pattern, context)
            if size_matches:
                file_sizes.extend([m[0] if isinstance(m, tuple) else m for m in size_matches])
        return file_sizes

    def _generate_key_variants(self, key, context):
        """生成关键字变体列表"""
        variants = [key]
        escaped_key = re.escape(key)
        if key not in context:
            # 引号变体
            for quote in ['"', "'"]:
                variants.extend([
                    f'{quote}{key}{quote}',
                    f'{key}{quote}',
                    f'{quote}{key}'
                ])
            # 空格变体
            variants.extend([
                f' {key}',
                f'{key} '
            ])
        # 使用原始key和转义后的key进行匹配
        return [v for v in variants if re.search(re.escape(v), context)]

    def _extract_direct_version(self, text, key, file_sizes):
        """尝试直接从关键字后提取版本"""
        for pattern_template in self.DIRECT_VERSION_PATTERNS:
            try:
                # 安全地替换模式中的 {} 占位符
                pattern = pattern_template.replace('{}', re.escape(key))
                match = re.search(pattern, text)
                if match:
                    version = match.group(1).rstrip('.')
                    if version not in file_sizes:
                        self.logger.debug(f"直接提取到版本: {version} (使用模式: {pattern})")
                        return version
            except Exception as e:
                self.logger.debug(f"模式匹配出错: {str(e)}, 模式: {pattern_template}")
                continue
        return None

    def _extract_with_patterns(self, text, patterns, file_sizes, check_test_versions=False):
        """使用模式列表提取版本"""
        version_candidates = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if not check_test_versions:
                    dev_keywords = ['dev', 'alpha', 'beta', 'rc', 'snapshot', 'nightly', 'preview', 'test']
                    if any(keyword in text.lower() for keyword in dev_keywords):
                        continue
                
                match = match.rstrip('.')
                # 验证版本号格式是否合理（至少包含一个点号分隔符）
                if '.' in match and match not in file_sizes and match not in version_candidates:
                    # 确保版本号不是被错误拆分的部分版本号
                    # 检查是否存在类似 "2.6.37" 被拆分为 "6.37" 的情况
                    is_partial_version = False
                    for existing_version in version_candidates:
                        if match in existing_version and len(match) < len(existing_version):
                            is_partial_version = True
                            break
                        # 检查文本中是否存在更完整的版本号包含当前匹配
                        for potential_full_version in re.findall(r'\d+\.\d+\.\d+', text):
                            if match in potential_full_version and match != potential_full_version:
                                is_partial_version = True
                                break
                    
                    if not is_partial_version:
                        version_candidates.append(match)
        return version_candidates

    def extract_version_from_context(self, context, version_extract_key, check_test_versions=False, aur_version=None):
        """从上下文中提取版本号"""
        try:
            self.logger.debug(f"开始提取版本，提取键: '{version_extract_key}'")
            file_sizes = self._get_file_sizes(context)

            if version_extract_key:
                version_candidates = []
                for key in self._generate_key_variants(version_extract_key, context):
                    positions = [m.start() for m in re.finditer(re.escape(key), context)]
                    
                    for pos in positions:
                        start = max(0, pos - 100)
                        end = min(len(context), pos + len(key) + 100)
                        surrounding_text = context[start:end]
                        
                        # 尝试直接提取
                        direct_version = self._extract_direct_version(surrounding_text, key, file_sizes)
                        if direct_version:
                            version_candidates.append(direct_version)
                            continue
                            
                        # 使用模式提取
                        patterns = self.TEST_VERSION_PATTERNS if check_test_versions else self.STABLE_VERSION_PATTERNS
                        extracted_versions = self._extract_with_patterns(surrounding_text, patterns, file_sizes, check_test_versions)
                        version_candidates.extend(extracted_versions)

                # 过滤和验证版本候选列表
                filtered_candidates = self._filter_version_candidates(version_candidates, aur_version)
                
                if filtered_candidates:
                    self.logger.debug(f"比较版本: {filtered_candidates}")
                    # 使用版本处理器获取最新版本
                    latest = self.version_processor.get_latest_version(filtered_candidates)
                    if latest:
                        self.logger.info(f"从关键字上下文中提取到最新版本: {latest}")
                        return latest
                    return filtered_candidates[0] if filtered_candidates else None
            else:
                # 全文提取
                patterns = self.COMMON_VERSION_PATTERNS
                version_candidates = self._extract_with_patterns(context, patterns, file_sizes)
                
                # 过滤和验证版本候选列表
                filtered_candidates = self._filter_version_candidates(version_candidates, aur_version)
                
                if filtered_candidates:
                    self.logger.debug(f"比较版本: {filtered_candidates}")
                    latest = self.version_processor.get_latest_version(filtered_candidates)
                    if latest:
                        self.logger.info(f"从全文提取到最新版本: {latest}")
                        return latest
                    return filtered_candidates[0] if filtered_candidates else None

        except Exception as e:
            self.logger.warning(f"从上下文提取版本号时出错: {str(e)}")
        
        return None
        
    def _filter_version_candidates(self, version_candidates, aur_version=None):
        """过滤和验证版本候选列表"""
        if not version_candidates:
            return []
            
        # 移除可能是部分版本号的候选项
        filtered_candidates = []
        for version in version_candidates:
            # 检查是否是其他版本的子串
            is_substring = False
            for other_version in version_candidates:
                # 如果当前版本是其他版本的子串，且不是完全相同
                if version != other_version and version in other_version:
                    # 检查是否是数字边界的子串（例如 "6.37" 是 "2.6.37" 的子串，但不是边界对齐的）
                    version_parts = version.split('.')
                    other_parts = other_version.split('.')
                    
                    # 检查是否是尾部对齐的子串
                    if len(version_parts) <= len(other_parts) and \
                       version_parts == other_parts[-len(version_parts):]:
                        is_substring = True
                        break
                        
                    # 检查是否是头部对齐的子串
                    if len(version_parts) <= len(other_parts) and \
                       version_parts == other_parts[:len(version_parts)]:
                        is_substring = True
                        break
                        
                    # 检查是否是中间对齐的子串（如 "6.37" 在 "2.6.37.0" 中）
                    for i in range(len(other_parts) - len(version_parts) + 1):
                        if version_parts == other_parts[i:i+len(version_parts)]:
                            is_substring = True
                            break
            
            # 额外验证版本号格式是否符合AUR版本格式
            if aur_version:
                aur_parts = aur_version.split('.')
                version_parts = version.split('.')
                
                # 如果AUR版本和候选版本的段数差异过大，则过滤掉
                if abs(len(aur_parts) - len(version_parts)) > 1:
                    continue
                
            if not is_substring:
                filtered_candidates.append(version)
                
        return filtered_candidates

    async def check_version(self, package_name, url, version_pattern_regex=None, **kwargs):
        """检查上游版本"""
        self.logger.debug(f"使用curl检查器检查软件包 {package_name} 的版本")
        
        version_extract_key = kwargs.get("version_extract_key")
        check_test_versions = kwargs.get("check_test_versions", False)
        aur_version = kwargs.get("aur_version")
        version_pattern = kwargs.get("version_pattern")

        try:
            with self._temp_curl_file(url) as temp_path:
                # 执行curl命令
                process = await asyncio.create_subprocess_exec(
                    "curl", "-L", "-s", "-o", temp_path, url
                )
                await process.communicate()

                if process.returncode != 0:
                    return self._error_result(package_name, "Curl命令执行失败")

                # 读取内容
                with open(temp_path, "r", errors="ignore") as f:
                    content = f.read()

                # 优先使用传入的正则
                if version_pattern_regex:
                    try:
                        match = re.compile(version_pattern_regex).search(content)
                        if match:
                            version = match.group(1) if match.groups() else match.group(0)
                            if self._validate_version(version, aur_version, version_pattern):
                                return self._success_result(package_name, version, "成功使用传入模式提取版本")
                    except Exception:
                        pass

                # 使用提取函数
                version = self.extract_version_from_context(
                    content, version_extract_key or "", check_test_versions, aur_version
                )

                # 额外验证提取的版本号格式
                if version:
                    # 检查版本号是否符合预期格式
                    if not self._is_valid_version_format(version, aur_version):
                        self.logger.warning(f"提取的版本号 {version} 格式可能不正确，与AUR版本 {aur_version} 格式不一致")
                        
                        # 尝试在内容中查找更完整的版本号
                        full_version_pattern = r'\d+\.\d+\.\d+'
                        full_versions = re.findall(full_version_pattern, content)
                        for full_ver in full_versions:
                            if version in full_ver and full_ver != version:
                                self.logger.info(f"找到更完整的版本号: {full_ver}，替换原版本号: {version}")
                                version = full_ver
                                break
                    
                    # 验证版本
                    if self._validate_version(version, aur_version, version_pattern):
                        return self._success_result(package_name, version, "成功提取版本")
                    else:
                        # 即使验证失败也返回成功结果，但添加说明
                        return self._success_result(package_name, version, "提取的版本与AUR版本格式不匹配")
                
                # 尝试从URL提取
                if aur_version:
                    exact_match = re.search(
                        f"(?:^|[^0-9])({re.escape(aur_version)})(?:[^0-9]|$)", url
                    )
                    if exact_match:
                        return self._success_result(
                            package_name, 
                            exact_match.group(1),
                            "从URL中提取到与AUR版本匹配的版本号"
                        )

                return self._error_result(package_name, "无法提取版本")

        except Exception as e:
            return self._error_result(package_name, str(e))
            
    def _is_valid_version_format(self, version, aur_version):
        """验证版本号格式是否与AUR版本格式一致"""
        if not aur_version:
            return True
            
        # 计算版本号中的点号数量
        aur_dots = aur_version.count('.')
        version_dots = version.count('.')
        
        # 如果点号数量差异过大，可能是格式不一致
        if abs(aur_dots - version_dots) > 1:
            return False
            
        # 检查版本号部分数量
        aur_parts = aur_version.split('.')
        version_parts = version.split('.')
        
        # 如果部分数量差异过大，可能是格式不一致
        if abs(len(aur_parts) - len(version_parts)) > 1:
            return False
            
        return True

    def _validate_version(self, version, aur_version, version_pattern):
        """验证版本合理性"""
        if aur_version and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
            return self.main_checker._is_version_similar(version, version_pattern)
        return True

    def _success_result(self, package_name, version, message):
        """成功结果格式"""
        return {
            "name": package_name,
            "success": True,
            "version": version,
            "date": datetime.now().isoformat(),
            "message": message
        }

    def _error_result(self, package_name, message):
        """错误结果格式"""
        return {
            "name": package_name,
            "success": False,
            "message": message
        }
