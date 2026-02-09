---
name: restart
description: 重启前后端服务。自动检测并关闭已有进程，清理僵尸讨论，再启动。
allowed-tools: Bash
context: fork
---

# /restart - 重启前后端服务

<command-name>restart</command-name>

## 功能

一键重启 bw-work 项目的前后端服务，包括：

1. 检测并关闭已占用 18000 / 18001 端口的进程
2. 清理僵尸讨论（running 状态但无后台任务）
3. 启动后端 (FastAPI, port 18000)
4. 启动前端 (Vite, port 18001)
5. 验证启动成功

## 执行步骤

### Step 1: 关闭已有进程

```bash
# 检查并关闭后端 (18000)
BACKEND_PID=$(lsof -t -i :18000 2>/dev/null)
if [ -n "$BACKEND_PID" ]; then
  echo "Stopping backend (PID: $BACKEND_PID)..."
  kill $BACKEND_PID 2>/dev/null
fi

# 检查并关闭前端 (18001)
FRONTEND_PID=$(lsof -t -i :18001 2>/dev/null)
if [ -n "$FRONTEND_PID" ]; then
  echo "Stopping frontend (PID: $FRONTEND_PID)..."
  kill $FRONTEND_PID 2>/dev/null
fi

sleep 1

# 确认端口已释放
REMAINING=$(lsof -i :18000 -i :18001 2>/dev/null | grep LISTEN)
if [ -n "$REMAINING" ]; then
  echo "Force killing remaining processes..."
  kill -9 $(lsof -t -i :18000 -i :18001) 2>/dev/null
  sleep 1
fi
```

### Step 2: 清理僵尸讨论

```bash
cd /Users/bowen/workspace/claude/bw-work/backend
.venv/bin/python -c "
import json
from pathlib import Path
from datetime import datetime

state_dir = Path('data/projects/.discussion_state')
if state_dir.exists():
    for path in state_dir.glob('*.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('status') == 'running':
            data['status'] = 'failed'
            data['error'] = '服务器重启，讨论中断'
            data['completed_at'] = datetime.utcnow().isoformat()
            path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            print(f'Cleaned zombie: {data[\"id\"][:12]}... ({data[\"topic\"]})')
"
```

### Step 3: 启动后端

在后台启动后端服务：

```bash
cd /Users/bowen/workspace/claude/bw-work/backend
.venv/bin/python -m uvicorn src.api.main:app --reload --port 18000 &
```

### Step 4: 启动前端

在后台启动前端服务：

```bash
cd /Users/bowen/workspace/claude/bw-work/frontend
npx vite --port 18001 &
```

### Step 5: 验证

等待 4 秒后检查两个端口是否都在监听：

```bash
sleep 4
lsof -i :18000 -i :18001 2>/dev/null | grep LISTEN
```

预期看到 18000 (Python) 和 18001 (node) 两个 LISTEN 记录。

向用户报告启动结果。
