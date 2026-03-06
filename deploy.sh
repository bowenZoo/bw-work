#!/bin/bash
set -e

REMOTE="bw-dify"
REMOTE_DIR="/home/ubuntu/bw-work"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== bw-work Deploy to $REMOTE ==="

# ─── E2E 测试门控 ──────────────────────────────────────────────────────────────
# 跳过：SKIP_TESTS=1 ./deploy.sh
if [ "${SKIP_TESTS}" != "1" ]; then
  echo ""
  echo "[0/4] 运行 E2E 测试（跳过请用 SKIP_TESTS=1）..."

  # 检查本地前后端是否已启动
  if ! curl -sf http://localhost:18000/api/health > /dev/null 2>&1 && \
     ! curl -sf http://localhost:18000/docs > /dev/null 2>&1; then
    echo "  警告：后端（18000）未响应，跳过 E2E 测试"
    echo "  提示：运行 /restart 后再部署，或用 SKIP_TESTS=1 ./deploy.sh 强制跳过"
  elif ! curl -sf http://localhost:18001 > /dev/null 2>&1; then
    echo "  警告：前端（18001）未响应，跳过 E2E 测试"
    echo "  提示：运行 /restart 后再部署，或用 SKIP_TESTS=1 ./deploy.sh 强制跳过"
  else
    cd "$PROJECT_DIR/frontend"
    if pnpm test:e2e --reporter=list; then
      echo "  E2E 测试全部通过"
    else
      echo ""
      echo "  E2E 测试失败！部署已中止。"
      echo "  查看报告：cd frontend && pnpm test:e2e:report"
      echo "  强制部署：SKIP_TESTS=1 ./deploy.sh"
      exit 1
    fi
    cd "$PROJECT_DIR"
  fi
fi
# ──────────────────────────────────────────────────────────────────────────────

# 1. Sync project files (exclude runtime/generated dirs)
echo "[1/4] Syncing files to $REMOTE:$REMOTE_DIR ..."
rsync -avz --delete \
  --exclude 'node_modules' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '.mypy_cache' \
  --exclude 'backend/data' \
  --exclude '.git' \
  --exclude '.claude' \
  --exclude '.bwf' \
  --exclude '*.pyc' \
  --exclude 'frontend/dist' \
  --exclude 'github' \
  --exclude 'docs' \
  --exclude 'backend/tests' \
  --exclude '.DS_Store' \
  --exclude '.ruff_cache' \
  "$PROJECT_DIR/" "$REMOTE:$REMOTE_DIR/"

# 2. Ensure data directory exists on remote and sync config data
echo "[2/4] Syncing data (admin.db, config)..."
ssh "$REMOTE" "mkdir -p $REMOTE_DIR/backend/data/projects $REMOTE_DIR/backend/data/chroma"

# Copy admin.db (contains LLM API keys) — only if not yet on remote
ssh "$REMOTE" "mkdir -p $REMOTE_DIR/data/admin"
ssh "$REMOTE" "test -f $REMOTE_DIR/data/admin/admin.db" 2>/dev/null || {
  echo "  First deploy: copying admin.db (contains API key config)..."
  scp "$PROJECT_DIR/data/admin/admin.db" "$REMOTE:$REMOTE_DIR/data/admin/admin.db"
}

# 3. Copy .env if not exists on remote
echo "[3/4] Ensuring .env exists on remote..."
ssh "$REMOTE" "test -f $REMOTE_DIR/backend/.env" 2>/dev/null || {
  echo "  Copying local backend/.env to remote..."
  scp "$PROJECT_DIR/backend/.env" "$REMOTE:$REMOTE_DIR/backend/.env"
}

# 4. Build and start on remote
echo "[4/4] Building and starting Docker containers..."
ssh "$REMOTE" "cd $REMOTE_DIR && sudo docker compose up -d --build"

echo ""
echo "=== Deploy complete ==="
echo "Frontend: http://118.89.16.95:18001"
echo "Backend:  http://118.89.16.95:18000"
echo ""
echo "Useful commands:"
echo "  ssh $REMOTE 'cd $REMOTE_DIR && docker compose logs -f'        # View logs"
echo "  ssh $REMOTE 'cd $REMOTE_DIR && docker compose logs -f backend' # Backend logs"
echo "  ssh $REMOTE 'cd $REMOTE_DIR && docker compose restart'         # Restart"
echo "  ssh $REMOTE 'cd $REMOTE_DIR && docker compose down'            # Stop"
