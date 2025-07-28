#!/bin/bash
# 依赖安全检查脚本
# 此脚本用于定期检查项目依赖中的安全漏洞
# 进入脚本所在目录
cd "$(dirname "$0")"

source venv/bin/activate

echo "正在执行依赖安全检查..."

# 检查是否安装了pip-audit
if ! command -v pip-audit &> /dev/null; then
    echo "安装 pip-audit 依赖检查工具..."
    pip install pip-audit
fi

echo "使用 pip-audit 检查依赖安全漏洞..."
pip-audit -r requirements.txt

# 作为备选方案，也可以使用pip自带的检查功能
echo -e "\n额外使用pip检查过时包..."
pip list --outdated

echo "检查完成。如有安全问题，请及时更新相应依赖。"

