#!/usr/bin/env python3
"""
AUR更新检查器打包脚本
用于将Python项目打包成可执行程序

注意：
1. 此版本已修改为排除系统已安装的 PySide6 和 playwright 依赖
2. 如果遇到 playwright 依赖问题（如缺少 libicudata.so.66 等），
   可以尝试取消 "--include-package-data=playwright" 的注释，
   或者在系统中安装缺失的依赖库
"""

import os
import sys
import subprocess
import glob
import argparse
import shutil
from pathlib import Path

def find_main_file():
    """查找主Python文件"""
    # 首先检查当前目录下的main.py
    if os.path.exists("main.py"):
        return "main.py"

    # 然后检查src目录下的main.py
    src_file = os.path.join("src", "main.py")
    if os.path.exists(src_file):
        return src_file

    return None

def find_icon_file():
    """查找图标文件"""
    # 先找assets目录中的png文件
    icons = glob.glob("assets/*.png") + glob.glob("*/assets/*.png")
    if icons:
        return icons[0]

    # 再找任意png文件
    icons = glob.glob("*.png") + glob.glob("*/*.png")
    if icons:
        return icons[0]

    return None

def main():
    # 检查 Nuitka 是否已安装
    try:
        import nuitka
        print(f"Nuitka 版本: {nuitka.__version__}")
    except ImportError:
        print("错误: Nuitka 未安装，尝试安装...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "nuitka"])
            print("Nuitka 安装成功")
        except Exception as e:
            print(f"Nuitka 安装失败: {e}")
            return 1
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="AUR更新检查器打包脚本")
    parser.add_argument("--main", help="主Python文件路径")
    parser.add_argument("--icon", help="图标文件路径")
    parser.add_argument("--jobs", type=int, help="并行编译的任务数量，默认使用所有CPU核心")
    parser.add_argument("--lto", action="store_true", help="启用链接时优化，可能提高性能但增加编译时间")
    parser.add_argument("--cache", action="store_true", help="启用编译缓存，加速重复编译")
    parser.add_argument("--optimization", type=int, choices=[0, 1, 2, 3], default=2,
                        help="优化级别：0=无优化，1=基本优化，2=默认优化，3=最高优化")
    parser.add_argument("--debug", action="store_true", help="包含调试信息，方便排查问题")
    args = parser.parse_args()

    # 自动查找主文件
    main_file = args.main if args.main else find_main_file()
    if not main_file:
        print("错误：无法找到主Python文件，请使用--main参数指定")
        return 1

    print(f"找到主脚本: {main_file}")

    # 查找图标
    if args.icon:
        icon_file = args.icon
        print(f"使用指定图标: {icon_file}")
        icon_arg = f"--linux-icon={icon_file}"
    else:
        icon_file = find_icon_file()
        if icon_file:
            print(f"找到图标: {icon_file}")
            icon_arg = f"--linux-icon={icon_file}"
        else:
            print("未找到图标，将使用默认图标")
            icon_arg = ""

    # 创建输出目录
    os.makedirs("dist", exist_ok=True)
    
    # 清理之前的构建文件
    for old_dir in ["dist/main.dist", "dist/main.build"]:
        if os.path.exists(old_dir):
            shutil.rmtree(old_dir)
            print(f"已删除旧的构建目录: {old_dir}")

    # 设置环境变量
    env = os.environ.copy()
    
    # 注意：系统已安装 playwright，但可能存在依赖问题
    # 如果打包后程序无法正常运行，可能需要安装缺失的依赖：
    # libicudata.so.66, libicui18n.so.66, libicuuc.so.66, libxml2.so.2, libwebp.so.6, libffi.so.7
    print("警告：使用系统安装的 playwright，请确保所有依赖已安装")
    
    # 原 playwright 下载配置已注释
    # env["PLAYWRIGHT_DOWNLOAD_HOST"] = "https://npmmirror.com/mirrors/playwright"
    # if shutil.which("axel"):
    #     print("检测到axel，将使用axel加速下载")
    #     env["PLAYWRIGHT_DOWNLOAD_COMMAND"] = "axel -a -n 10 -o {output} {url}"

    # 构建Nuitka命令
    # 获取CPU核心数，用于并行编译
    import multiprocessing
    cpu_count = args.jobs if args.jobs else multiprocessing.cpu_count()
    print(f"将使用 {cpu_count} 个并行任务进行编译")

    cmd = [
        "python", "-m", "nuitka",
        "--standalone",  # 始终使用文件夹形式打包
        "--follow-imports",  # 确保所有导入的模块都被包含
        # inspect是模块不是包，不能使用--include-package-data
        # dis是模块不是包，不能使用--include-package-data
        "--include-module=opcode",  # 确保包含opcode模块及其依赖
        "--include-package=inspect",  # 确保包含inspect包
        "--include-package=dis",  # 确保包含dis包
        "--include-module=_opcode",  # 确保包含_opcode模块
        # numpy插件已被弃用，不再启用
        "--prefer-source-code",  # 优先使用源代码而不是编译后的.so文件
        
        # 系统已安装 PySide6 和 playwright，排除相关依赖
        # "--plugin-enable=pyside6",
        # "--include-qt-plugins=platforms",
        
        # 排除系统已安装的依赖
        "--nofollow-import-to=PySide6",  # 排除 PySide6 依赖
        "--nofollow-import-to=playwright",  # 排除 playwright 依赖
        
        # 如果遇到 playwright 依赖问题，可以尝试取消下面这行的注释
        # "--include-package-data=playwright",  # 强制包含 playwright 数据文件
        "--assume-yes-for-downloads",
        "--show-memory",
        "--show-progress",
        # anti-bloat插件已默认启用，不需要显式启用
        "--python-flag=no_site",  # 避免加载site-packages中的模块
        "--python-flag=isolated",  # 隔离环境，避免受系统Python环境影响
        f"--jobs={cpu_count}"  # 使用指定数量的CPU核心进行并行编译
    ]

    print("创建文件夹形式的可执行程序...")

    # 添加资源文件
    cmd.extend([
        "--include-data-dir=assets=assets",
        "--include-data-dir=src=src",
        "--include-data-files=*.py=./"  # 确保所有Python文件都被包含
    ])

    if icon_arg:
        cmd.append(icon_arg)

    # 如果用户选择启用LTO，则添加LTO选项
    if args.lto:
        print("启用链接时优化(LTO)，这可能会增加编译时间但提高最终性能")
        cmd.append("--lto=yes")

    # 如果用户选择启用缓存，则添加缓存选项
    if args.cache:
        print("启用编译缓存，这将加速重复编译")
    else:
        # 不使用缓存时，禁用所有缓存
        cmd.append("--disable-cache=all")

    # 设置优化级别
    opt_level = args.optimization
    print(f"使用优化级别: {opt_level}")

    # 检查是否安装了clang
    if shutil.which("clang"):
        print("检测到clang编译器，将使用clang进行编译")
        cmd.append("--clang")  # 使用clang编译器，通常比gcc更快

    # 设置Python优化级别
    # Python 3.13不再支持-O2优化标志
    if opt_level > 0 and sys.version_info < (3, 13):
        cmd.append(f"--python-flag=-O{opt_level}")

    # 如果启用调试模式
    if args.debug:
        print("启用调试模式，将包含调试信息")
        cmd.append("--debug")
        cmd.append("--unstripped")  # 不剥离符号表，方便调试

    cmd.extend([
        "--output-dir=dist",
        "--include-data-files=*.json=.",  # 包含所有JSON配置文件
        main_file
    ])

    # 执行Nuitka打包
    print("开始打包...")
    print(f"执行命令: {' '.join(cmd)}")

    try:
        # 显示完整命令
        print("完整打包命令:")
        print(" ".join(cmd))
        
        # 执行打包命令
        result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        
        # 显示命令输出
        print("命令输出:")
        print(result.stdout)
        if result.stderr:
            print("命令错误:")
            print(result.stderr)

        # 检查是否生成了main.dist目录
        main_dist_dir = Path("dist/main.dist")
        if main_dist_dir.exists() and main_dist_dir.is_dir():
            print("检测到main.dist目录，将其内容移动到dist目录...")
            
            # 将main.dist目录中的所有内容移动到dist目录
            for item in main_dist_dir.glob("*"):
                target_path = Path("dist") / item.name
                if target_path.exists():
                    if target_path.is_dir():
                        shutil.rmtree(target_path)
                    else:
                        target_path.unlink()
                
                if item.is_dir():
                    shutil.copytree(item, target_path)
                    shutil.rmtree(item)
                else:
                    shutil.copy2(item, target_path)
                    item.unlink()
            
            # 删除空的main.dist目录
            shutil.rmtree(main_dist_dir)
            print("已将main.dist目录内容移动到dist目录")

        # 重命名输出文件
        script_base = os.path.splitext(os.path.basename(main_file))[0]

        # 查找Nuitka标准输出目录结构中的可执行文件
        binary = next((p for p in Path("dist").glob("aur-update-checker-python*")
                     if p.is_file() and os.access(p, os.X_OK)), None)
        if not binary:
            binary = next((p for p in Path("dist").rglob("*.bin")
                         if p.is_file() and os.access(p, os.X_OK)), None)
            if not binary:
                binary = next((p for p in Path("dist").glob(f"{script_base}*")
                             if p.is_file() and os.access(p, os.X_OK) and not str(p).startswith("dist/lib/")), None)
                if not binary:
                    # 尝试查找main可执行文件
                    binary = next((p for p in Path("dist").rglob("main")
                                 if p.is_file() and os.access(p, os.X_OK)), None)
                    if not binary:
                        binary = next((p for p in Path("dist").rglob("main.bin")
                                     if p.is_file() and os.access(p, os.X_OK)), None)

        if binary:
            target = Path("dist/aur-update-checker-python")
            if target.exists():
                target.unlink()
            binary.rename(target)
            print(f"可执行程序已创建: {target}")

            # 后处理：复制必要的模块文件到dist目录
            print("正在进行后处理，确保所有必要的模块文件都可用...")
            
            # 创建路径配置文件，确保程序能够找到正确的子目录
            config_path = Path("dist/path_config.py")
            with open(config_path, "w") as f:
                f.write("""
import os
import sys

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 将当前目录添加到系统路径
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 将lib目录添加到系统路径
lib_dir = os.path.join(current_dir, "lib")
if os.path.exists(lib_dir) and lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

# 将其他可能的模块目录添加到系统路径
for subdir in ["src", "assets", "modules"]:
    subdir_path = os.path.join(current_dir, subdir)
    if os.path.exists(subdir_path) and subdir_path not in sys.path:
        sys.path.insert(0, subdir_path)
""")
            print(f"已创建路径配置文件: {config_path}")
            
            # 确保dist目录中包含所有必要的模块
            for module_dir in ["lib", "src", "assets", "modules"]:
                module_path = Path(f"dist/{module_dir}")
                if not module_path.exists() and Path(module_dir).exists():
                    shutil.copytree(module_dir, module_path)
                    print(f"已复制目录 {module_dir} 到 dist/{module_dir}")




        else:
            print("警告：无法找到编译后的可执行文件，请检查dist目录")

        # 删除所有临时文件
        print("正在清理临时文件...")
        temp_dirs = [".nuitka", "__pycache__"]
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                print(f"已删除临时目录: {temp_dir}")
        
        # 删除临时编译文件，但保留dist目录中的文件
        for temp_file in glob.glob("*.build") + glob.glob("*.dist") + glob.glob("*.o") + glob.glob("*.c"):
            if os.path.exists(temp_file) and not temp_file.startswith("dist/"):
                os.remove(temp_file)
                print(f"已删除临时文件: {temp_file}")
                
        # 清理dist目录中的临时文件
        print("正在清理dist目录中的临时文件...")
        dist_temp_patterns = ["*.pyi", "*.pyc", "*.pyo", "*.pyd", "__pycache__"]
        for pattern in dist_temp_patterns:
            for temp_file in Path("dist").rglob(pattern):
                if temp_file.is_file():
                    temp_file.unlink()
                    print(f"已删除dist目录中的临时文件: {temp_file}")
                elif temp_file.is_dir():
                    shutil.rmtree(temp_file)
                    print(f"已删除dist目录中的临时目录: {temp_file}")
                    
        # 确保dist目录中的文件权限正确
        for file_path in Path("dist").rglob("*"):
            if file_path.is_file():
                # 设置可执行权限
                if file_path.suffix in ["", ".sh", ".py"] and not os.access(file_path, os.X_OK):
                    os.chmod(file_path, 0o755)
                    print(f"已设置可执行权限: {file_path}")
                # 设置普通文件权限
                else:
                    os.chmod(file_path, 0o644)
                    
        # 确保主程序有执行权限
        main_program = Path("dist/aur-update-checker-python")
        if main_program.exists() and not os.access(main_program, os.X_OK):
            os.chmod(main_program, 0o755)
            print(f"已设置主程序可执行权限: {main_program}")

        print("打包完成！")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"打包失败: {e}")
        return 1
    except Exception as e:
        print(f"出现错误: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
