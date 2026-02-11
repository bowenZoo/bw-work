---
name: deploy
description: 部署项目到 bw-dify 服务器。同步代码、重建 Docker 镜像、验证服务状态。
allowed-tools: Bash
context: fork
---

# /deploy - 部署到 bw-dify 服务器

<command-name>deploy</command-name>

## 功能

一键部署 bw-work 项目到 bw-dify 远程服务器（118.89.16.95），包括：

1. 通过 rsync 同步项目代码（排除运行时目录）
2. 重新构建并启动 Docker Compose 容器（前后端）
3. 验证服务启动状态
4. 输出服务访问地址

## 服务器信息

- SSH Host: `bw-dify`（已在 ~/.ssh/config 中配置）
- 远端路径: `/home/ubuntu/bw-work`
- 前端地址: `http://118.89.16.95:18001`
- 后端地址: `http://118.89.16.95:18000`

## 重要：前端是多阶段构建

前端 Dockerfile 采用多阶段构建：先用 Node 执行 `vite build`，再将产物复制到 nginx 镜像。
因此**必须使用 `--build` 重新构建镜像**，源码改动才会生效。单纯 `restart` 只会重启旧镜像。

## 执行步骤

### Step 1: 同步代码

使用 rsync 同步项目文件到远程服务器，排除运行时和生成目录：

```bash
PROJECT_DIR="/Users/bowen/workspace/claude/bw-work"
REMOTE="bw-dify"
REMOTE_DIR="/home/ubuntu/bw-work"

echo "=== [1/3] 同步代码到 $REMOTE ==="
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
```

### Step 2: 重新构建并启动容器

默认使用 `--build` 重新构建镜像，确保代码改动生效：

```bash
echo "=== [2/3] 重新构建并启动容器 ==="
ssh bw-dify "cd /home/ubuntu/bw-work && sudo docker compose up -d --build"
```

### Step 3: 验证服务状态

等待几秒后检查容器状态和后端日志：

```bash
echo "=== [3/3] 验证服务状态 ==="
sleep 5
ssh bw-dify "cd /home/ubuntu/bw-work && sudo docker compose ps && echo '---' && sudo docker compose logs --tail=3 backend 2>&1 | tail -5"
```

预期看到 bw-backend 和 bw-frontend 两个容器状态为 Up，后端日志包含 `Application startup complete`。

### 输出结果

向用户报告部署结果，包含访问地址：
- Frontend: http://118.89.16.95:18001
- Backend:  http://118.89.16.95:18000

## 可选参数

如果用户指定 `/deploy --fast`，则在 Step 2 中改用 `sudo docker compose restart` 只重启容器不重新构建（仅适用于后端 Python 代码改动，因为后端通过 volume 映射或 COPY 直接生效；前端改动必须重新构建）。
