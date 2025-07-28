#!/bin/bash
# AUR更新检查器打包脚本

set -e  # 遇到错误立即退出

# 解析命令行参数
ONEFILE_MODE=0
MAIN_PY=""

for arg in "$@"; do
  if [[ "$arg" == "--onefile" ]]; then
    ONEFILE_MODE=1
  elif [[ "$arg" == *.py && -f "$arg" ]]; then
    MAIN_PY="$arg"
  fi
done

# 如果没有指定主Python文件，尝试自动查找
if [ -z "$MAIN_PY" ]; then
  echo "正在分析项目结构..."
  find . -name "*.py" | grep -v "venv/" | grep -v "./build.sh" | sort

  # 尝试查找主脚本
  if [ -f "run.py" ]; then
    MAIN_PY="run.py"
  elif [ -f "main.py" ]; then
    MAIN_PY="main.py"
  elif [ -f "app.py" ]; then
    MAIN_PY="app.py"
  elif [ -f "src/main.py" ]; then
    MAIN_PY="src/main.py"
  else
    # 如果上述都不存在，尝试在项目根目录查找.py文件
    MAIN_PY=$(find . -maxdepth 1 -name "*.py" -not -path "*/\.*" | head -n 1)

    # 如果还没找到，尝试在src目录查找
    if [ -z "$MAIN_PY" ]; then
      MAIN_PY=$(find src -name "*.py" -not -path "*/\.*" | head -n 1 2>/dev/null)
    fi
  fi
fi

# 确认找到了主Python文件
if [ -z "$MAIN_PY" ] || [ ! -f "$MAIN_PY" ]; then
  echo "错误：无法找到主Python文件。请手动指定："
  echo "用法: $0 [--onefile] path/to/main.py"
  exit 1
fi

echo "找到主脚本: $MAIN_PY"

# 检查图标位置
ICON_PATH=$(find . -name "*.png" -path "*assets*" 2>/dev/null || find . -name "*.png" 2>/dev/null || echo "")
if [ -n "$ICON_PATH" ]; then
  ICON_ARG="--linux-icon=$ICON_PATH"
  echo "找到图标: $ICON_PATH"
else
  ICON_ARG=""
  echo "未找到图标，将使用默认图标"
fi

# 创建输出目录
mkdir -p dist

# 设置环境变量，使用国内镜像
export PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright"

# 检查是否有axel
if command -v axel &> /dev/null; then
  echo "检测到axel，将使用axel加速下载"
  export PLAYWRIGHT_DOWNLOAD_COMMAND="axel -a -n 10 -o {output} {url}"
fi

# 构建单文件还是文件夹
if [ $ONEFILE_MODE -eq 1 ]; then
  echo "创建单文件可执行程序..."
  NUITKA_ARGS="--onefile --onefile-cache-mode=cached"
else
  echo "创建独立文件夹可执行程序..."
  NUITKA_ARGS="--standalone"
fi

# 执行Nuitka打包
echo "开始打包..."
python -m nuitka   $NUITKA_ARGS   --plugin-enable=pyqt6   --include-qt-plugins=platforms   --assume-yes-for-downloads   --show-memory   --show-progress   $ICON_ARG   --output-dir=dist   "$MAIN_PY"

# 重命名输出文件
if [ $ONEFILE_MODE -eq 1 ]; then
  BINARY=$(find dist -type f -executable -name "*.bin" 2>/dev/null | head -n 1)
else
  # 获取主脚本的基本名称（不含路径和扩展名）
  SCRIPT_BASE=$(basename "$MAIN_PY" .py)
  BINARY=$(find dist -type f -executable -name "$SCRIPT_BASE*" -not -path "*/lib/*" 2>/dev/null | head -n 1)
fi

if [ -n "$BINARY" ]; then
  mv "$BINARY" dist/aur-update-checker
  echo "可执行程序已创建: dist/aur-update-checker"
else
  echo "警告：无法找到编译后的可执行文件，请检查dist目录"
fi

echo "打包完成！"
