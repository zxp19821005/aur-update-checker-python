from setuptools import setup, find_packages
import os

# 动态读取 requirements.txt
install_requires = []
if os.path.exists("requirements.txt"):
    with open("requirements.txt") as f:
        install_requires = f.read().splitlines()

setup(
    name="aur-update-checker-python",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "aur-update-checker-python = aur_update_checker_python.main:main",
        ],
    },
    data_files=[
        ('share/aur-update-checker-python', ['config.template.json']),  # 使用相对路径
        ('share/applications', ['aur-update-checker-python.desktop']),
    ],
    install_requires=install_requires,
)