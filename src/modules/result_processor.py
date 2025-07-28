# -*- coding: utf-8 -*-
"""
版本检查结果处理模块，负责处理和格式化版本检查结果
"""
from datetime import datetime

class VersionResultProcessor:
    """处理版本检查结果的类"""

    def __init__(self, logger):
        """初始化结果处理器

        Args:
            logger: 日志模块实例
        """
        self.logger = logger
        self.logger.debug("版本结果处理器初始化")

    def process_aur_result(self, result):
        """处理AUR检查结果

        Args:
            result: 原始AUR检查结果

        Returns:
            dict: 处理后的结果
        """
        if not result:
            return None

        processed_result = {
            "name": result.get("name"),
            "aur_version": result.get("version"),
            "check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 添加最后修改日期（如果有）
        if "last_modified" in result:
            try:
                # 通常格式为 2023-01-15T12:30:45Z
                processed_result["last_modified"] = result["last_modified"].split("T")[0]
            except Exception:
                processed_result["last_modified"] = ""

        return processed_result

    def process_upstream_result(self, result):
        """处理上游版本检查结果

        Args:
            result: 原始上游检查结果

        Returns:
            dict: 处理后的结果，或None如果处理失败
        """
        if not result:
            return None

        # 首先确定有版本信息
        version = None
        if "version" in result:
            version = result["version"]
        elif "upstream_version" in result:
            version = result["upstream_version"]

        if not version:
            self.logger.warning(f"检查器返回的结果缺少版本信息: {result}")
            return result  # 返回原始结果以便记录

        # 确定检查时间
        check_time = result.get("check_time") or result.get("update_date")
        if not check_time:
            check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建处理后的结果
        processed_result = {
            "name": result.get("name"),
            "upstream_version": version,
            "check_time": check_time,
            "success": True
        }

        # 添加消息（如果有）
        if "message" in result:
            processed_result["message"] = result["message"]

        return processed_result

    def format_result_for_ui(self, result, result_type="aur"):
        """将结果格式化为UI友好格式

        Args:
            result: 处理后的结果
            result_type: 结果类型，'aur'或'upstream'

        Returns:
            dict: UI友好的结果格式
        """
        if not result:
            return None

        ui_result = {
            "name": result.get("name"),
            "success": result.get("success", True),
            "check_time": result.get("check_time", "")
        }

        # 根据类型添加特定字段
        if result_type == "aur":
            ui_result["version"] = result.get("aur_version")
            ui_result["last_modified"] = result.get("last_modified", "")
        else:
            ui_result["version"] = result.get("upstream_version")

        # 添加消息（如果有）
        if "message" in result:
            ui_result["message"] = result["message"]

        return ui_result

    def summarize_results(self, results, result_type="aur"):
        """汇总处理结果

        Args:
            results: 结果列表
            result_type: 结果类型

        Returns:
            dict: 汇总信息
        """
        if not results:
            return {"total": 0, "success": 0, "failed": 0, "results": []}

        success_count = 0
        failed_count = 0
        formatted_results = []

        for result in results:
            formatted = self.format_result_for_ui(result, result_type)
            if formatted:
                formatted_results.append(formatted)
                if formatted.get("success", False):
                    success_count += 1
                else:
                    failed_count += 1

        return {
            "total": len(results),
            "success": success_count,
            "failed": failed_count,
            "results": formatted_results
        }
