#!/bin/bash
set -e

REMOTE="bw-dify"
REMOTE_DIR="/home/ubuntu/bw-work"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== bw-work Deploy to $REMOTE ==="

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
