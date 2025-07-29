#!/bin/bash
# 依赖更新脚本
# 此脚本用于定期检查并更新项目依赖

echo "开始检查并更新依赖..."

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 备份当前requirements.txt
cp requirements.txt requirements.txt.bak

# 更新所有依赖到最新版本
echo "检查过时的依赖..."
# 创建临时Python脚本来避免引号问题
cat > /tmp/check_outdated.py << 'EOL'
import json
import sys

try:
    outdated = json.load(sys.stdin)
    if not outdated:
        print("所有依赖都是最新的")
    for package in outdated:
        print(f"发现过时的依赖: {package['name']} (当前: {package['version']}, 最新: {package['latest_version']})")
except Exception as e:
    print(f"检查过时依赖时出错: {e}")
EOL

pip list --outdated --format=json | python /tmp/check_outdated.py
rm /tmp/check_outdated.py

read -p "是否更新所有依赖到最新版本？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 询问版本匹配类型
    read -p "使用灵活版本匹配(>=)还是精确版本匹配(==)？(f/e) [默认:e] " -n 1 -r VERSION_TYPE
    echo
    USE_FLEXIBLE="False"
    if [[ $VERSION_TYPE =~ ^[Ff]$ ]]; then
        echo "将使用灵活版本匹配(>=)..."
        USE_FLEXIBLE="True"
    else
        echo "将使用精确版本匹配(==)..."
    fi

    echo "更新依赖中..."
    pip install -r requirements.txt --upgrade

    # 生成新的requirements.txt
    pip freeze > requirements.txt.new

    # 保留注释并更新版本号
    cat > /tmp/update_requirements.py << 'EOL'
import re
import sys

# 是否使用灵活版本将通过命令行参数传入
use_flexible_versions = sys.argv[1].lower() == 'true'

with open('requirements.txt', 'r') as old, open('requirements.txt.new', 'r') as new, open('requirements.txt.updated', 'w') as out:
    old_lines = old.readlines()
    new_packages = {}

    # 解析新版本的依赖
    for line in new.readlines():
        if '==' in line:
            name, version = line.strip().split('==')
            new_packages[name.lower()] = version

    # 更新旧文件中的版本号，保留注释
    for line in old_lines:
        if line.strip() and not line.strip().startswith('#'):
            package_line = line.strip()
            package_name = re.split('[>=<]', package_line)[0].strip().lower()
            if package_name in new_packages:
                # 保留格式，但更新版本号
                version_prefix = '=='  # 默认使用精确版本匹配
                if use_flexible_versions:
                    version_prefix = '>='
                updated_line = re.sub(r'[>=<][^#\s]+', version_prefix + new_packages[package_name], line)
                out.write(updated_line)
            else:
                out.write(line)
        else:
            out.write(line)
EOL

    python /tmp/update_requirements.py "$USE_FLEXIBLE"
    rm /tmp/update_requirements.py

    # 替换原文件
    if [ -f requirements.txt.updated ]; then
        mv requirements.txt.updated requirements.txt
        rm requirements.txt.new
        echo "依赖已更新到最新版本！"
    fi
else
    echo "依赖更新已取消。"
fi

# 检查安全漏洞
echo "检查依赖中的安全漏洞..."
# 调用security_scan.sh进行安全检查
if [ -f "./security_scan.sh" ]; then
    bash ./security_scan.sh
else
    echo "警告: 未找到security_scan.sh，无法执行安全检查"
fi

# 清理
echo "清理临时文件..."
if [ -f "requirements.txt.bak" ]; then
    read -p "是否保留备份文件requirements.txt.bak？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        rm requirements.txt.bak
    fi
fi

echo "依赖检查和更新已完成！"
deactivate