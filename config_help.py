#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置帮助脚本，用于显示配置文件的使用说明
"""
import os
import json
import argparse
import sys

def print_config_help():
    """打印配置帮助信息"""
    print("AUR Update Checker 配置帮助")
    print("=" * 50)
    print("\n配置文件路径设置方式：")
    print("  1. 环境变量: AUR_UPDATE_CHECKER_CONFIG=/path/to/config.json")
    print("  2. 命令行参数: --config /path/to/config.json 或 -c /path/to/config.json")
    print("  3. 默认路径: ~/.config/aur-update-checker-python/config.json")
    
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "config.template.json")
    
    # 检查模板文件是否存在
    if os.path.exists(template_path):
        print("\n配置模板文件位置:")
        print(f"  {template_path}")
        
        # 读取并显示模板文件内容
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = json.load(f)
            
            print("\n配置选项说明:")
            # 过滤掉注释项
            real_config = {k: v for k, v in template.items() if not k.startswith('#')}
            
            # 显示主要配置项
            for section, options in real_config.items():
                print(f"\n  {section}:")
                if isinstance(options, dict):
                    for key, value in options.items():
                        if isinstance(value, dict):
                            print(f"    {key}: {...}")
                        else:
                            print(f"    {key}: {value}")
                else:
                    print(f"    {options}")
            
            print("\n详细配置请参考配置模板文件。")
        except Exception as e:
            print(f"\n读取配置模板文件出错: {str(e)}")
    else:
        print("\n配置模板文件不存在，请运行主程序生成默认配置。")
    
    print("\n使用示例:")
    print("  AUR_UPDATE_CHECKER_CONFIG=/path/to/config.json python main.py")
    print("  python main.py --config /path/to/config.json")

if __name__ == "__main__":
    print_config_help()