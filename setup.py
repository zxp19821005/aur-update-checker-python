from setuptools import setup, find_packages
import os

# 动态读取 requirements.txt
install_requires = []
if os.path.exists("requirements.txt"):
    with open("requirements.txt") as f:
        install_requires = f.read().splitlines()

# 数据文件配置
data_files = [
    ('share/applications', ['aur-update-checker-python.desktop']),
    ('share/pixmaps', ['src/assets/aur-update-checker-python.png']),
]

setup(
    name="aur-update-checker-python",
    version="1.0.1",
    packages=find_packages(),
    package_dir={"": "."},
    entry_points={
        "console_scripts": [
            "aur-update-checker-python = src.main:main",
        ],
    },
    install_requires=install_requires,
    data_files=data_files,
    package_data={
        "src": ["assets/*"],  # 包含 src/assets 目录下的所有文件
    },
    include_package_data=True,  # 确保 MANIFEST.in 中的文件也被包含
)
