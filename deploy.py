#!/usr/bin/env python3
"""
AUR更新检查器部署脚本
用于简化打包过程 - 仅打包为文件夹形式
"""
import os
import sys
import subprocess

# 版本信息
VERSION = "1.0.0"
YEAR = "2023-2024"
AUTHOR = "AUR Update Checker Team"

def main():
    """主函数"""
    # 基本命令 - 默认打包为文件夹形式
    # 默认使用默认优化级别(2)，启用链接时优化，启用编译缓存，不进行调试
    cmd = [
        "python", 
        "package.py",
        "--optimization", "2",  # 默认优化级别
        "--lto",                # 启用链接时优化
        "--cache"               # 启用编译缓存
    ]
    
    # 自动检测CPU核心数并使用所有可用核心
    import multiprocessing
    cpu_count = multiprocessing.cpu_count()
    cmd.extend(["--jobs", str(cpu_count)])
    
    print(f"使用 {cpu_count} 个CPU核心进行并行编译")
    print(f"启用链接时优化(LTO)和编译缓存，使用默认优化级别")
    
    # 执行打包命令
    print(f"执行命令: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    print("打包完成！文件夹形式的可执行程序已生成在dist目录中")
    return 0

if __name__ == "__main__":
    sys.exit(main())