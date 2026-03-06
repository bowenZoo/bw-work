"""Stage Session API — 阶段需求访谈讨论室。

每个项目阶段可以创建多个访谈会话，支持多人实时讨论、AI 主持引导，最终生成阶段文档。
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ...admin.database import AdminDatabase
from ...admin.config_store import ConfigStore
from ..routes.auth import get_current_user
from ..websocket.manager import ConnectionManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["session"])

# WebSocket manager dedicated to stage sessions (keyed by session_id)
session_ws_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Stage-type question templates for AI facilitation
# ---------------------------------------------------------------------------

_STAGE_TEMPLATES: dict[str, dict] = {
    "concept": {
        "label": "概念孵化",
        "opening": (
            "大家好！我是本次访谈的 AI 主持人。\n\n"
            "我们今天的目标是明确项目的**核心概念**，包括：\n"
            "- 产品定位与目标用户\n- 核心价值主张\n- 差异化竞争点\n\n"
            "首先请介绍一下这个项目想解决什么问题？"
        ),
        "questions": [
            "目标用户是谁？他们目前面临什么痛点？",
            "与市面上现有产品相比，你们最大的差异化在哪里？",
            "项目的核心价值主张用一句话怎么描述？",
            "预期的商业模式是什么？",
            "成功的标志是什么——3 个月后什么指标达到了算成功？",
        ],
        "doc_template": """# 概念孵化文档

## 项目背景
{background}

## 目标用户
{target_users}

## 核心痛点
{pain_points}

## 核心价值主张
{value_proposition}

## 差异化优势
{differentiation}

## 商业模式
{business_model}

## 成功指标
{success_metrics}

## 讨论结论
{conclusions}
""",
    },
    "core-gameplay": {
        "label": "核心玩法 GDD",
        "opening": (
            "大家好！本次访谈聚焦于**核心玩法设计**。\n\n"
            "我们需要明确：\n"
            "- 玩家的核心体验循环\n- 关键交互机制\n- 乐趣来源\n\n"
            "请描述玩家第一次打开游戏会经历什么？"
        ),
        "questions": [
            "核心体验循环（Core Loop）是什么？玩家每次游玩的主要行为是？",
            "游戏最大的乐趣点在哪里？什么让玩家想要反复游玩？",
            "新手引导如何设计？玩家第一个 10 分钟会经历什么？",
            "竞争/挑战机制是什么？PVP 还是 PVE 还是两者都有？",
            "玩家成长路径是什么？短期/中期/长期目标分别是？",
        ],
        "doc_template": """# 核心玩法 GDD

## 核心体验循环
{core_loop}

## 乐趣来源
{fun_factor}

## 新手引导
{onboarding}

## 竞争与挑战
{competition}

## 玩家成长路径
{progression}

## 关键机制描述
{mechanisms}

## 讨论结论
{conclusions}
""",
    },
    "art-style": {
        "label": "美术风格定义",
        "opening": (
            "本次访谈聚焦于**美术风格**。\n\n"
            "我们需要确定：\n"
            "- 整体视觉风格方向\n- 参考作品\n- 技术约束\n\n"
            "你们希望玩家看到游戏的第一眼是什么感觉？"
        ),
        "questions": [
            "整体美术风格是什么？写实、卡通、像素、低多边形还是其他？",
            "有哪些参考作品（游戏/影视/插画）？",
            "目标平台对美术有哪些技术约束？",
            "主色调和情感基调是什么？",
            "角色风格和场景风格各有什么要求？",
        ],
        "doc_template": """# 美术风格定义文档

## 整体视觉方向
{visual_direction}

## 参考作品
{references}

## 技术约束
{tech_constraints}

## 色彩与情感基调
{color_mood}

## 角色设计规范
{character_style}

## 场景设计规范
{environment_style}

## 讨论结论
{conclusions}
""",
    },
    "tech-prototype": {
        "label": "技术选型 & 原型",
        "opening": (
            "本次访谈聚焦于**技术选型与原型验证**。\n\n"
            "我们需要明确：\n"
            "- 引擎和技术栈选择\n- 关键技术风险\n- 原型验证计划\n\n"
            "项目计划使用什么技术引擎或框架？"
        ),
        "questions": [
            "游戏引擎/框架选择是什么？选择理由？",
            "服务器架构是什么？需要实时联网吗？",
            "最大的技术风险点在哪里？",
            "原型需要验证哪些核心技术可行性？",
            "团队目前的技术储备如何？有哪些技术短板？",
        ],
        "doc_template": """# 技术选型文档

## 技术栈选择
{tech_stack}

## 服务器架构
{server_arch}

## 技术风险
{tech_risks}

## 原型验证计划
{prototype_plan}

## 团队技术能力评估
{team_capability}

## 讨论结论
{conclusions}
""",
    },
    "system-design": {
        "label": "系统设计文档",
        "opening": (
            "本次访谈聚焦于**系统设计**。\n\n"
            "我们需要明确各个游戏系统的设计细节。\n\n"
            "请列举项目中最核心的 3 个游戏系统？"
        ),
        "questions": [
            "各核心系统之间如何交互？",
            "经济系统如何设计？货币、道具、交易？",
            "社交系统有哪些功能？",
            "活动/赛季系统如何规划？",
            "数据存储和存档机制是什么？",
        ],
        "doc_template": """# 系统设计文档

## 核心系统列表
{core_systems}

## 系统交互关系
{system_interactions}

## 经济系统
{economy_system}

## 社交系统
{social_system}

## 活动系统
{event_system}

## 讨论结论
{conclusions}
""",
    },
    "numbers": {
        "label": "数值框架",
        "opening": (
            "本次访谈聚焦于**数值框架设计**。\n\n"
            "我们需要确定核心数值体系。\n\n"
            "游戏中玩家成长的核心数值维度有哪些？"
        ),
        "questions": [
            "战斗数值体系：攻防血的基础公式是什么？",
            "成长曲线：玩家从 1 级到满级的节奏如何规划？",
            "付费点的数值设计：付费与免费的差距控制在什么范围？",
            "资源产出速率：日常任务/活动的资源产出如何平衡？",
            "数值天花板和膨胀策略是什么？",
        ],
        "doc_template": """# 数值框架文档

## 核心数值维度
{core_dimensions}

## 战斗数值体系
{combat_numbers}

## 成长曲线规划
{growth_curve}

## 付费数值设计
{payment_design}

## 资源平衡
{resource_balance}

## 讨论结论
{conclusions}
""",
    },
    "ui-ux": {
        "label": "UI/UX 界面设计",
        "opening": (
            "本次访谈聚焦于 **UI/UX 界面设计**。\n\n"
            "我们需要明确界面设计规范和用户体验标准。\n\n"
            "游戏最核心的 UI 界面有哪些？"
        ),
        "questions": [
            "主界面的信息架构是什么？玩家最常用的入口在哪里？",
            "HUD（战斗界面）需要展示哪些实时信息？",
            "操作方式：触屏手势/摇杆/按键如何设计？",
            "新手引导 UI 如何降低学习曲线？",
            "无障碍设计有哪些考虑？",
        ],
        "doc_template": """# UI/UX 设计文档

## 核心界面列表
{core_ui}

## 主界面信息架构
{ia_design}

## HUD 设计
{hud_design}

## 操作方式
{controls}

## 新手引导 UI
{onboarding_ui}

## 讨论结论
{conclusions}
""",
    },
    "default": {
        "label": "阶段讨论",
        "opening": (
            "大家好！我是本次访谈的 AI 主持人。\n\n"
            "让我们开始这次讨论。请先介绍一下本阶段的核心目标是什么？"
        ),
        "questions": [
            "这个阶段需要解决的最关键问题是什么？",
            "有哪些已知的约束条件或前提假设？",
            "理想的输出成果是什么？",
            "目前有哪些不确定性需要在讨论中明确？",
            "各位有什么想法或建议？",
        ],
        "doc_template": """# 阶段讨论文档

## 阶段目标
{goals}

## 关键问题
{key_issues}

## 约束条件
{constraints}

## 讨论过程
{discussion}

## 结论
{conclusions}
""",
    },
}


def _get_template(template_id: str) -> dict:
    return _STAGE_TEMPLATES.get(template_id, _STAGE_TEMPLATES["default"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    title: str


class SendMessageRequest(BaseModel):
    content: str


class SessionResponse(BaseModel):
    id: str
    project_id: int
    stage_id: str
    title: str
    status: str
    created_by: int
    generated_doc_id: Optional[str] = None
    created_at: str
    updated_at: str
    message_count: int = 0


class MessageResponse(BaseModel):
    id: str
    session_id: str
    user_id: Optional[int] = None
    role: str  # user / ai / system
    content: str
    created_at: str


# ---------------------------------------------------------------------------
# Helper: call LLM
# ---------------------------------------------------------------------------


async def _llm_chat(messages: list[dict]) -> str:
    """Call the configured LLM and return the assistant reply text."""
    try:
        from openai import AsyncOpenAI
        from ...admin.config_store import ConfigStore

        store = ConfigStore()
        api_key = store.get_raw("llm", "openai_api_key") or ""
        base_url = store.get_raw("llm", "openai_base_url") or None
        model = store.get_raw("llm", "openai_model") or "gpt-4"

        if not api_key:
            return "（AI 主持人暂时不可用，请先在后台配置 LLM API Key）"

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=1200,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
        return f"（AI 主持人出现错误：{e}）"


async def _ai_respond(session_id: str, db: AdminDatabase, template_id: str) -> None:
    """Generate AI facilitator response based on conversation history and broadcast via WS."""
    msgs = db.get_session_messages(session_id, limit=50)
    template = _get_template(template_id)

    # Build LLM prompt from history
    system_prompt = (
        f"你是一名专业的产品访谈主持人，正在主持【{template['label']}】阶段的需求访谈。\n"
        "你的职责是：\n"
        "1. 根据参与者的回答，提出有深度的追问\n"
        "2. 适时总结已讨论的要点\n"
        "3. 引导讨论朝着完整的阶段文档所需内容推进\n"
        "4. 保持简洁友好，每次回复不超过 150 字\n"
        "5. 使用中文回复\n\n"
        f"本阶段需要探讨的核心问题包括：\n"
        + "\n".join(f"- {q}" for q in template["questions"])
        + "\n\n当你认为讨论已经充分，可以说：'我们已经收集了足够的信息，现在可以生成阶段文档了。'"
    )

    llm_messages = [{"role": "system", "content": system_prompt}]
    for m in msgs[-20:]:  # last 20 messages for context
        if m["role"] == "ai":
            llm_messages.append({"role": "assistant", "content": m["content"]})
        elif m["role"] == "user":
            llm_messages.append({"role": "user", "content": m["content"]})

    reply = await _llm_chat(llm_messages)

    # Save to DB
    ai_msg = db.add_session_message(session_id, role="ai", content=reply)
    ai_msg["created_at"] = ai_msg.get("created_at", "")

    # Broadcast
    await session_ws_manager.broadcast(session_id, {
        "type": "message",
        "data": {
            "id": ai_msg["id"],
            "session_id": session_id,
            "role": "ai",
            "user_id": None,
            "content": reply,
            "created_at": "",
        },
    })


async def _generate_document_content(session_id: str, db: AdminDatabase, template_id: str) -> str:
    """Use LLM to generate a structured markdown document from session transcript."""
    msgs = db.get_session_messages(session_id)
    template = _get_template(template_id)

    transcript = "\n".join(
        f"[{'AI主持' if m['role'] == 'ai' else '参与者'}] {m['content']}"
        for m in msgs if m["role"] in ("ai", "user")
    )

    system_prompt = (
        f"你是一名专业的文档整理员。根据以下【{template['label']}】阶段的访谈记录，"
        "生成一份结构完整的需求文档。\n"
        "要求：\n"
        "1. 使用 Markdown 格式\n"
        "2. 从访谈中提取关键信息，不要编造\n"
        "3. 结构清晰，包含各个核心章节\n"
        "4. 语言专业简洁\n"
        "5. 如果某个章节讨论不充分，注明'待补充'\n"
    )

    user_prompt = (
        f"以下是访谈记录：\n\n{transcript}\n\n"
        f"请生成【{template['label']}】阶段的需求文档，Markdown 格式："
    )

    return await _llm_chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])


# ---------------------------------------------------------------------------
# REST API endpoints
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/stages/{stage_id}/sessions", response_model=SessionResponse)
async def create_session(
    project_id: str,
    stage_id: str,
    body: CreateSessionRequest,
    user: dict = Depends(get_current_user),
):
    """创建新的阶段访谈会话，并自动发送 AI 开场白。"""
    db = AdminDatabase()
    # Resolve project integer id
    proj_int_id = db.resolve_project_id(project_id)
    # Verify stage belongs to project
    stage = db.get_stage(stage_id)
    if not stage or stage["project_id"] != proj_int_id:
        raise HTTPException(status_code=404, detail="阶段不存在")

    session = db.create_stage_session(
        project_id=proj_int_id,
        stage_id=stage_id,
        title=body.title,
        created_by=user["id"],
    )

    # Count messages
    session["message_count"] = 0

    # Post AI opening message
    template = _get_template(stage["template_id"])
    opening = template["opening"]
    db.add_session_message(session["id"], role="ai", content=opening)
    session["message_count"] = 1

    return _session_resp(session)


@router.get("/projects/{project_id}/stages/{stage_id}/sessions", response_model=list[SessionResponse])
async def list_sessions(
    project_id: str,
    stage_id: str,
    user: dict = Depends(get_current_user),
):
    db = AdminDatabase()
    sessions = db.get_stage_sessions(stage_id)
    result = []
    for s in sessions:
        msgs = db.get_session_messages(s["id"], limit=1000)
        s["message_count"] = len(msgs)
        result.append(_session_resp(s))
    return result


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    db = AdminDatabase()
    session = db.get_stage_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = db.get_session_messages(session_id)
    session["message_count"] = len(msgs)
    return _session_resp(session)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_messages(session_id: str, user: dict = Depends(get_current_user)):
    db = AdminDatabase()
    session = db.get_stage_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = db.get_session_messages(session_id)
    return [_msg_resp(m) for m in msgs]


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    user: dict = Depends(get_current_user),
):
    """发送用户消息，并触发 AI 主持人异步回复。"""
    db = AdminDatabase()
    session = db.get_stage_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session["status"] == "closed":
        raise HTTPException(status_code=400, detail="会话已关闭")

    # Save user message
    msg = db.add_session_message(session_id, role="user", content=body.content, user_id=user["id"])
    msg["created_at"] = msg.get("created_at", "")

    # Broadcast user message
    await session_ws_manager.broadcast(session_id, {
        "type": "message",
        "data": {
            "id": msg["id"],
            "session_id": session_id,
            "role": "user",
            "user_id": user["id"],
            "username": user.get("username"),
            "display_name": user.get("display_name"),
            "content": body.content,
            "created_at": "",
        },
    })

    # Get stage template_id for AI
    stage = db.get_stage(session["stage_id"])
    template_id = stage["template_id"] if stage else "default"

    # Broadcast AI-is-typing
    await session_ws_manager.broadcast(session_id, {"type": "ai_typing", "data": {}})

    # Trigger AI response asynchronously
    asyncio.create_task(_ai_respond(session_id, db, template_id))

    return _msg_resp(msg)


@router.post("/sessions/{session_id}/generate-doc")
async def generate_document(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """根据访谈内容用 AI 生成阶段需求文档，并关联到当前阶段。"""
    db = AdminDatabase()
    session = db.get_stage_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    stage = db.get_stage(session["stage_id"])
    if not stage:
        raise HTTPException(status_code=404, detail="阶段不存在")

    template = _get_template(stage["template_id"])

    # Notify WS clients doc generation started
    await session_ws_manager.broadcast(session_id, {"type": "generating_doc", "data": {}})

    # Generate
    content = await _generate_document_content(session_id, db, stage["template_id"])

    # Create document in stage
    doc = db.create_document(
        project_id=session["project_id"],
        stage_id=session["stage_id"],
        title=f"{template['label']}——访谈输出文档",
        content=content,
        created_by=user["id"],
    )

    # Link session to document
    db.update_stage_session(session_id, generated_doc_id=doc["id"], status="closed")

    # Broadcast doc ready
    await session_ws_manager.broadcast(session_id, {
        "type": "doc_ready",
        "data": {
            "document_id": doc["id"],
            "title": doc["title"],
            "content": content,
        },
    })

    return {"document_id": doc["id"], "title": doc["title"], "content": content}


@router.post("/sessions/{session_id}/close")
async def close_session(session_id: str, user: dict = Depends(get_current_user)):
    db = AdminDatabase()
    session = db.get_stage_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    db.update_stage_session(session_id, status="closed")
    await session_ws_manager.broadcast(session_id, {"type": "session_closed", "data": {}})
    return {"ok": True}


# ---------------------------------------------------------------------------
# WebSocket endpoint — P1.3
# ---------------------------------------------------------------------------


@router.websocket("/ws/session/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str):
    """实时 WebSocket 通道，用于讨论室消息广播。"""
    db = AdminDatabase()
    session = db.get_stage_session(session_id)
    if not session:
        await websocket.close(code=4004)
        return

    await session_ws_manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    session_ws_manager.update_heartbeat(websocket)
            except Exception:
                pass
    except WebSocketDisconnect:
        session_ws_manager.disconnect(websocket, session_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_resp(s: dict) -> SessionResponse:
    return SessionResponse(
        id=s["id"],
        project_id=s["project_id"],
        stage_id=s["stage_id"],
        title=s["title"],
        status=s["status"],
        created_by=s["created_by"],
        generated_doc_id=s.get("generated_doc_id"),
        created_at=str(s.get("created_at", "")),
        updated_at=str(s.get("updated_at", "")),
        message_count=s.get("message_count", 0),
    )


def _msg_resp(m: dict) -> MessageResponse:
    return MessageResponse(
        id=m["id"],
        session_id=m["session_id"],
        user_id=m.get("user_id"),
        role=m["role"],
        content=m["content"],
        created_at=str(m.get("created_at", "")),
    )
