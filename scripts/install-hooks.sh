#!/bin/sh
# 安装 git hooks（在项目根目录运行）
REPO=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
SRC="$REPO/scripts/hooks"
DST="$REPO/.git/hooks"

install_hook() {
  name=$1
  src="$SRC/$name"
  dst="$DST/$name"
  if [ ! -f "$src" ]; then
    echo "[install-hooks] ⚠️  $src 不存在，跳过"
    return
  fi
  cp "$src" "$dst"
  chmod +x "$dst"
  echo "[install-hooks] ✅ $name 已安装"
}

install_hook post-commit
echo "[install-hooks] 完成。运行 'pnpm gen:changelog' 立即生成一次公告。"
