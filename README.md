# AUR Update Checker (Python版)

![AUR Update Checker](assets/icon.png)

A personal project, mainly used to check if there are updates available upstream for the software packages I maintain. All the code was completed with the help of an AI programming assistant.

一个个人项目，主要用于检查我维护的软件包的上游是否存在更新。所有代码都是通过AI编程助手完成的。

使用到的AI编程助手包括：
- [CodeGeeX](https://codegeex.cn/)
- [FittenCode](https://www.fittencode.cn/)
- [CodeBuddy](https://codebuddy.ai/)

项目图标由[豆包](https://www.doubao.com/)生成。

[![Build and Package](https://github.com/zxp19821005/aur-update-checker-python/actions/workflows/build.yml/badge.svg)](https://github.com/zxp19821005/aur-update-checker-python/actions/workflows/build.yml)

## 功能特点

- **多源检查**：同时检查 AUR 软件包和上游源的最新版本
- **丰富的上游源支持**：
  - GitHub Releases/Tags
  - GitLab Releases/Tags
  - Gitee Releases/Tags
  - NPM 包
  - PyPI 包
  - 通用 JSON API
  - 网页内容解析
  - 重定向链接解析
- **友好的用户界面**：
  - 简洁直观的单页面设计
  - 系统托盘支持
  - 深色/浅色主题切换
  - 可自定义的表格显示
- **高级功能**：
  - 批量检查和更新
  - 定时自动检查
  - 版本更新通知
  - 详细的日志记录
  - 代理设置支持
  - 本地数据库缓存

## 技术架构

AUR Update Checker 采用了现代化的架构设计：

- **前端**：PySide6 (Qt for Python) 提供跨平台桌面应用支持
- **后端**：
  - Python 3.x 作为主要编程语言
  - SQLite 作为本地数据库存储
  - Requests 处理 HTTP 请求
  - Playwright 处理复杂网页交互
  - BeautifulSoup4 + lxml 解析 HTML/XML
  - Loguru 提供高级日志管理
- **架构模式**：
  - 依赖注入设计模式
  - 异步编程模型
  - 模块化组件设计

## 安装方法

### 从 AUR 安装 (推荐)

```bash
# 使用 paru (推荐)
paru -S aur-update-checker-python

# 或使用 yay
yay -S aur-update-checker-python
```

### 使用 pipx 安装

```bash
# 安装 pipx (如果尚未安装)
python -m pip install --user pipx
python -m pipx ensurepath

# 安装应用
pipx install aur-update-checker-python

# 运行应用
aur-update-checker-python
```

### 从源码安装 (开发者)

```bash
# 克隆仓库
git clone https://github.com/zxp19821005/aur-update-checker-python.git
cd aur-update-checker-python

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行应用
python src/main.py
```

### 运行环境要求

基础依赖：

```bash
# Arch Linux 系统
sudo pacman -S python pyside6 python-beautifulsoup4 python-requests python-lxml python-playwright

# 其他 Linux 发行版
pip install PySide6 requests beautifulsoup4 lxml playwright
```

**注意**：打包后的可执行文件默认使用系统安装的 PySide6 和 playwright 库，而不是将它们打包到可执行文件中。这样可以减小可执行文件的大小，但要求系统中必须安装这些依赖。

如果在运行时遇到 `ModuleNotFoundError: No module named 'PySide6'` 错误，请确保已安装 PySide6：

```bash
# 检查 PySide6 是否已安装
pacman -Q pyside6

# 如果未安装，则安装 PySide6
sudo pacman -S pyside6
```

## 使用方法

### 基本使用

1. **添加软件包**：点击右下角的 "+" 按钮，输入 AUR 软件包名称
2. **检查版本**：
   - 单个软件包：点击软件包行中的 "检查 AUR" 或 "检查上游" 按钮
   - 批量检查：选中多个软件包，然后使用顶部的批量操作按钮
3. **查看结果**：软件包状态会自动更新，显示最新版本和检查时间
4. **过滤软件包**：使用搜索框和过滤选项快速定位软件包
5. **查看日志**：切换到 "日志" 标签页查看详细操作记录

### 命令行选项

```bash
python main.py [选项]
```

可用选项：
- `--config`, `-c`: 指定配置文件路径
- `--log-level`, `-l`: 设置日志级别 (debug, info, warning, error, critical)
- `--version`, `-v`: 显示版本信息

## 配置

### 配置文件位置

配置文件默认位于 `~/.config/aur-update-checker-python/config.json`，可以通过以下方式指定：

1. **环境变量**：设置 `AUR_UPDATE_CHECKER_CONFIG` 环境变量
   ```bash
   AUR_UPDATE_CHECKER_CONFIG=/path/to/config.json ./main.py
   ```

2. **命令行参数**：使用 `--config` 或 `-c` 参数
   ```bash
   ./main.py --config /path/to/config.json
   ```

### 主要配置选项

配置文件采用 JSON 格式，包含以下主要部分：

- **database**: 数据库设置（路径、备份数量）
- **logging**: 日志设置（级别、文件路径、控制台输出）
- **aur**: AUR 源设置（基础 URL、超时时间）
- **upstream**: 上游源通用设置（超时、用户代理、缓存时间）
- **github/gitee/gitlab**: 代码托管平台设置（API URL、令牌）
- **npm/pypi**: 包管理器设置
- **system**: 系统设置（临时目录、并发检查数）
- **scheduler**: 调度器设置（启用状态、检查间隔）
- **ui**: 界面设置（主题、字体大小、托盘图标）

详细配置选项请参考项目中的 `config.template.json` 文件。

## 高级功能

### 虚拟环境中使用

如果您在 Python 虚拟环境中使用打包后的可执行文件，需要确保虚拟环境中也安装了所需的依赖：

```bash
# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install PySide6 requests beautifulsoup4 lxml playwright

# 运行程序
./dist/aur-update-checker-python
```

或者，您可以修改 package.py 文件，取消 `--nofollow-import-to=PySide6` 和 `--nofollow-import-to=playwright` 选项，将这些依赖打包到可执行文件中：

```python
# 将这些行注释掉
# "--nofollow-import-to=PySide6",  # 排除 PySide6 依赖
# "--nofollow-import-to=playwright",  # 排除 playwright 依赖

# 添加这些行
"--plugin-enable=pyside6",
"--include-qt-plugins=platforms",
"--include-package-data=playwright",
```

### 定时检查

启用定时检查功能后，应用会按照设定的时间间隔自动检查更新：

1. 在 "设置" 标签页中启用定时检查
2. 设置 AUR 和上游源的检查间隔时间
3. 可选择是否在启动时自动检查
4. 可启用或禁用更新通知

### 代理设置

支持通过环境变量或配置文件设置 HTTP/HTTPS/SOCKS 代理：

```json
"network": {
  "proxy": {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890",
    "socks5": "socks5://127.0.0.1:1080"
  }
}
```

### 自定义上游源

可以为每个软件包单独配置上游源检查方式：

1. 右键点击软件包，选择 "编辑上游源"
2. 选择检查器类型（GitHub/GitLab/NPM/PyPI/Web等）
3. 填写相应的仓库信息或 URL 模式
4. 保存设置后，系统将使用自定义方式检查该软件包

## 开发指南

### 项目结构

```
aur-update-checker-python/
├── assets/                 # 图标和资源文件
├── docs/                   # 开发文档
├── src/                    # 源代码
│   ├── modules/            # 核心功能模块
│   │   ├── checkers/       # 各类检查器实现
│   │   └── ...
│   └── ui/                 # 用户界面组件
│       ├── logs_tab/       # 日志标签页
│       ├── main_window/    # 主窗口
│       └── settings_tab/   # 设置标签页
├── .github/                # GitHub Actions 工作流
├── main.py                 # 程序入口
├── package.py              # 打包脚本
├── deploy.py               # 部署脚本
└── requirements.txt        # 依赖列表
```

### 核心设计模式

项目采用了多种设计模式和最佳实践：

1. **依赖注入**：通过 `DependencyContainer` 实现组件解耦
2. **工厂模式**：用于创建不同类型的检查器
3. **策略模式**：实现不同的版本检查策略
4. **观察者模式**：用于 UI 更新和事件通知
5. **异步编程**：使用 asyncio 和 qasync 处理并发任务

详细开发指南请参考 `docs/` 目录下的文档：
- `dependency_injection_guide.md`: 依赖注入使用指南
- `error_handling_guide.md`: 错误处理指南
- `http_client_guide.md`: HTTP 客户端使用指南
- `thread_safety_guide.md`: 线程安全指南

## 贡献指南

欢迎提交 Pull Requests 或 Issues 来帮助改进这个项目。

### 贡献步骤

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开一个 Pull Request

### 代码规范

- 遵循 PEP 8 Python 代码风格
- 使用类型注解增强代码可读性
- 为新功能编写单元测试
- 保持文档和注释的更新

## 故障排除

### 常见问题

1. **ModuleNotFoundError: No module named 'PySide6'**
   - 原因：打包的可执行文件依赖系统安装的 PySide6
   - 解决方法：`sudo pacman -S pyside6` 或在虚拟环境中 `pip install PySide6`

2. **ModuleNotFoundError: No module named 'playwright'**
   - 原因：打包的可执行文件依赖系统安装的 playwright
   - 解决方法：`sudo pacman -S python-playwright` 或在虚拟环境中 `pip install playwright`

3. **缺少共享库错误（如 libicudata.so.66）**
   - 原因：playwright 依赖的系统库缺失
   - 解决方法：修改 package.py，取消注释 `--include-package-data=playwright` 选项，重新打包

4. **无法找到 Qt 平台插件**
   - 原因：Qt 平台插件未包含在可执行文件中
   - 解决方法：修改 package.py，添加 `--plugin-enable=pyside6` 和 `--include-qt-plugins=platforms` 选项，重新打包

### 调试技巧

如果遇到其他问题，可以尝试以下调试方法：

```bash
# 启用调试日志
./dist/aur-update-checker-python --log-level debug

# 使用 strace 跟踪系统调用
strace -f ./dist/aur-update-checker-python

# 检查动态链接库依赖
ldd ./dist/aur-update-checker-python
```

## 许可证

本项目采用 MIT 许可证 - 详情请参见 [LICENSE](LICENSE) 文件

## 致谢

- [PySide6](https://wiki.qt.io/Qt_for_Python) - Qt for Python
- [Requests](https://requests.readthedocs.io/) - 人性化的 HTTP 客户端
- [Playwright](https://playwright.dev/) - 现代浏览器自动化工具
- [Loguru](https://github.com/Delgan/loguru) - Python 日志库
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) - HTML/XML 解析库
- [SQLite](https://www.sqlite.org/) - 轻量级数据库引擎

---

**AUR Update Checker** © 2023-2024 Z.ai. 保留所有权利。