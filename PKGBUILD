# Maintainer: Z.ai <support@z.ai>
pkgname=aur-update-checker
pkgver=1.0.1
pkgrel=1
pkgdesc="AUR和上游版本检查工具"
arch=('x86_64')
url="https://github.com/yourusername/aur-update-checker"
license=('GPL')
depends=(
  'python'
  'pyside6'
  'python-beautifulsoup4'
  'python-requests'
  'python-lxml'
  'python-playwright'
  'axel'
)
makedepends=(
  'python-nuitka'
  'python-pip'
  'python-setuptools'
)
source=("$pkgname::git+file://$PWD")
sha256sums=('SKIP')

prepare() {
  cd "$pkgname"
  # 创建Python虚拟环境
  python -m venv --system-site-packages venv
  source venv/bin/activate
  # 安装项目依赖
  pip install -r requirements.txt
  # 确保安装 Nuitka
  pip install nuitka
}

build() {
  cd "$pkgname"
  source venv/bin/activate

  # 确认 Nuitka 已安装
  if ! python -c "import nuitka" &>/dev/null; then
    echo "错误: Nuitka 未正确安装，尝试重新安装..."
    pip install --upgrade nuitka
  fi

  # 显示 Nuitka 版本
  python -c "import nuitka; print(f'使用 Nuitka 版本: {nuitka.__version__}')" || echo "警告: 无法获取 Nuitka 版本"

  # 使用package.py打包脚本编译
  python package.py

  # 检查编译是否成功
  if [ ! -f "dist/aur-update-checker-python" ]; then
    echo "警告: 编译可能未成功完成，尝试使用备用方法..."
    # 备用编译方法
    python -m nuitka --standalone --follow-imports main.py --output-dir=dist
  fi
}

package() {
  cd "$pkgname"

  # 创建主程序目录
  install -d "$pkgdir/usr/lib/$pkgname"
  install -d "$pkgdir/usr/bin"
  install -d "$pkgdir/usr/share/applications"
  install -d "$pkgdir/usr/share/icons/hicolor/256x256/apps"

  # 复制编译后的文件
  cp -r dist/* "$pkgdir/usr/lib/$pkgname/"

  # 创建启动脚本
  cat > "$pkgdir/usr/bin/$pkgname" << EOF
#!/bin/bash
export PLAYWRIGHT_BROWSERS_PATH="/usr/lib/$pkgname/.cache/ms-playwright"
exec /usr/lib/$pkgname/aur-update-checker "$@"
EOF

  chmod +x "$pkgdir/usr/bin/$pkgname"

  # 创建桌面文件
  cat > "$pkgdir/usr/share/applications/$pkgname.desktop" << EOF
[Desktop Entry]
Type=Application
Name=AUR更新检查器
Comment=检查AUR包和上游版本更新
Exec=$pkgname
Icon=$pkgname
Terminal=false
Categories=System;
Keywords=AUR;Package;Update;Check;
EOF

  # 查找并复制图标
  ICON_PATH=$(find . -name "*.png" -path "*assets*" 2>/dev/null || find . -name "*.png" 2>/dev/null || echo "")
  if [ -n "$ICON_PATH" ]; then
    install -Dm644 "$ICON_PATH" "$pkgdir/usr/share/icons/hicolor/256x256/apps/$pkgname.png"
  fi
}
