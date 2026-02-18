"""Shared tools for crew agents.

This module provides tools that can be used by agents in discussions
to request image generation, web search, and other services.
"""

import ast
import asyncio
import logging
import math
import threading
from functools import wraps
from pathlib import Path
from typing import Any

from crewai.tools import tool

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Tool execution context (thread-local) for status broadcasting
# ------------------------------------------------------------------

_tool_context = threading.local()


def set_tool_context(discussion_id: str, agent_role: str) -> None:
    """Set the current tool execution context (called by DiscussionCrew before agent runs).

    Args:
        discussion_id: Current discussion ID.
        agent_role: Current agent's role name.
    """
    _tool_context.discussion_id = discussion_id
    _tool_context.agent_role = agent_role


def clear_tool_context() -> None:
    """Clear the tool execution context."""
    _tool_context.discussion_id = None
    _tool_context.agent_role = None


def _broadcast_tool_status(tool_label: str) -> None:
    """Broadcast a tool usage status via WebSocket (best-effort)."""
    did = getattr(_tool_context, "discussion_id", None)
    role = getattr(_tool_context, "agent_role", None)
    if not did or not role:
        return
    try:
        from src.api.websocket.events import AgentStatus, create_status_event
        from src.api.websocket.manager import broadcast_sync

        event = create_status_event(
            discussion_id=did,
            agent_id=role,
            agent_role=role,
            status=AgentStatus.THINKING,
            content=tool_label,
        )
        broadcast_sync(event.to_dict(), discussion_id=did)
    except Exception:
        pass  # best-effort, never block the tool


# ------------------------------------------------------------------
# Web Search Tool (DuckDuckGo, no API key required)
# ------------------------------------------------------------------

_web_search_tool = None


def get_web_search_tool():
    """Get (or create) the singleton web search tool instance."""
    global _web_search_tool
    if _web_search_tool is None:
        _web_search_tool = _create_web_search_tool()
    return _web_search_tool


def _create_web_search_tool():
    """Create the DuckDuckGo web search tool."""

    @tool("web_search")
    def web_search(query: str) -> str:
        """Search the web for information about game design, industry data, or any topic.

        Use this tool when you need to verify facts, look up game mechanics from
        other games, find industry data, or research any topic you're not sure about.

        Args:
            query: The search query. Be specific for better results.
                   Example: "原神抽卡系统保底机制" or "gacha pity system design"

        Returns:
            Search results with titles, snippets and URLs.
        """
        _broadcast_tool_status(f"正在联网搜索「{query[:30]}」...")
        try:
            from duckduckgo_search import DDGS

            results = DDGS().text(
                query,
                region="cn-zh",
                safesearch="moderate",
                max_results=5,
            )

            if not results:
                return f"No results found for: {query}"

            lines = [f"Search results for: {query}\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}")
                lines.append(f"   {r['body']}")
                lines.append(f"   URL: {r['href']}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            logger.warning("Web search failed for query '%s': %s", query, e)
            return f"Search failed: {str(e)}. Please continue without search results."

    return web_search


def create_request_image_tool(
    image_service: Any,
    project_id: str,
) -> Any:
    """Create a request_image tool for agents to request concept images.

    This tool allows any agent in a discussion to request the Visual Concept
    Agent (or the image service directly) to generate a concept image.

    Args:
        image_service: The ImageService instance.
        project_id: Current project ID for image storage.

    Returns:
        The tool function.
    """

    @tool("request_image")
    def request_image(
        description: str,
        style: str = "concept_character",
    ) -> str:
        """Request generation of a concept image.

        Use this tool when you want to visualize a design concept being discussed.
        The image will be generated asynchronously and made available to the team.

        Args:
            description: Detailed text description of what to visualize.
                        Be specific about visual elements, composition, and mood.
            style: Style template to use. Common options:
                   - concept_character: For character designs
                   - concept_scene: For environment/scene designs
                   - concept_item: For item/prop designs
                   - ui_icon: For UI elements

        Returns:
            A message indicating whether the image request was submitted.
        """
        if not project_id:
            return "Cannot request image: no project context available."

        try:
            # Run async function in sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        image_service.generate(
                            description=description,
                            project_id=project_id,
                            style_id=style,
                            agent="crew_request",
                        )
                    )
                    result = future.result()
            else:
                result = loop.run_until_complete(
                    image_service.generate(
                        description=description,
                        project_id=project_id,
                        style_id=style,
                        agent="crew_request",
                    )
                )

            if result.success:
                if result.is_async:
                    return (
                        f"Image generation requested (ID: {result.image_id}). "
                        f"The visual concept team is working on it."
                    )
                return (
                    f"Image generated: {result.image_url}\n"
                    f"Size: {result.width}x{result.height}"
                )
            else:
                return f"Image request failed: {result.error}"

        except Exception as e:
            logger.exception("Error in request_image tool")
            return f"Failed to request image: {str(e)}"

    return request_image


def create_list_available_styles_tool(style_manager: Any) -> Any:
    """Create a tool to list available image styles.

    Args:
        style_manager: The StyleManager instance.

    Returns:
        The tool function.
    """

    @tool("list_available_styles")
    def list_available_styles() -> str:
        """List available image generation styles.

        Use this tool to see what visual styles are available for image generation.

        Returns:
            A formatted list of available styles.
        """
        try:
            styles = style_manager.get_all_styles()
            lines = ["Available image styles:"]
            for style in styles:
                lines.append(f"- {style.id}: {style.name}")
                if style.description:
                    lines.append(f"  {style.description}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing styles: {str(e)}"

    return list_available_styles


# ------------------------------------------------------------------
# Memory Search Tool (context-aware, requires DiscussionMemory)
# ------------------------------------------------------------------


def create_memory_search_tool(
    memory: Any,  # DiscussionMemory instance
    project_id: str,
) -> Any:
    """Create a memory search tool for agents to search past discussions.

    Args:
        memory: The DiscussionMemory instance.
        project_id: Current project ID for scoping searches.
    """

    @tool("memory_search")
    def memory_search(query: str) -> str:
        """搜索历史讨论记录和决策。

        用于查找之前讨论过的设计决策、达成的共识、未解决的问题。
        确保当前讨论与历史决策保持一致。

        Args:
            query: 搜索关键词。示例："抽卡系统", "战斗公式", "经济平衡"

        Returns:
            匹配的历史讨论摘要和关键决策。
        """
        _broadcast_tool_status(f"正在搜索历史讨论「{query[:20]}」...")
        try:
            results = memory.search(query, limit=5)
            if not results:
                return f"未找到与「{query}」相关的历史讨论。"

            lines = [f"与「{query}」相关的历史讨论：\n"]
            for i, disc in enumerate(results, 1):
                lines.append(f"{i}. 主题: {disc.topic}")
                lines.append(f"   时间: {disc.created_at.strftime('%Y-%m-%d')}")
                if disc.summary:
                    summary = disc.summary[:200] + "..." if len(disc.summary) > 200 else disc.summary
                    lines.append(f"   摘要: {summary}")
                lines.append(f"   消息数: {len(disc.messages)}")
                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            logger.warning("Memory search failed for '%s': %s", query, e)
            return f"搜索失败: {str(e)}"

    return memory_search


# ------------------------------------------------------------------
# Read Project Doc Tool (context-aware, requires project_id)
# ------------------------------------------------------------------


def create_read_project_doc_tool(project_id: str) -> Any:
    """Create a tool to read project design documents.

    Args:
        project_id: Current project ID.
    """
    from pathlib import Path

    @tool("read_project_doc")
    def read_project_doc(action: str, filename: str = "") -> str:
        """读取当前项目的设计文档。

        用于了解项目已有的设计决策和文档内容，避免重复讨论或与已有设计矛盾。

        Args:
            action: 操作类型。"list" 列出所有文档, "read" 读取指定文档
            filename: 当 action="read" 时，要读取的文件名

        Returns:
            文档列表或文档内容。
        """
        _broadcast_tool_status(f"正在读取项目文档...")
        project_dir = Path("data/projects") / project_id

        if action == "list":
            if not project_dir.exists():
                return "当前项目暂无设计文档。"

            md_files = sorted(project_dir.rglob("*.md"))
            if not md_files:
                return "当前项目暂无设计文档。"

            lines = ["项目文档列表：\n"]
            for f in md_files:
                rel = f.relative_to(project_dir)
                size = f.stat().st_size
                lines.append(f"- {rel} ({size} bytes)")
            return "\n".join(lines)

        elif action == "read":
            if not filename:
                return "请指定要读取的文件名。使用 action='list' 查看可用文档。"

            # 安全检查：防止路径穿越
            target = (project_dir / filename).resolve()
            if not str(target).startswith(str(project_dir.resolve())):
                return "无效的文件路径。"

            if not target.exists():
                return f"文档 {filename} 不存在。使用 action='list' 查看可用文档。"

            content = target.read_text(encoding="utf-8")
            if len(content) > 3000:
                content = content[:3000] + f"\n\n... (截断，共 {len(content)} 字符)"

            return f"=== {filename} ===\n\n{content}"

        else:
            return "未知操作。支持: list, read"

    return read_project_doc


# ------------------------------------------------------------------
# Request Vote Tool (context-aware, requires discussion_id + broadcast)
# ------------------------------------------------------------------


def create_request_vote_tool(
    discussion_id: str,
    ws_manager: Any,  # GlobalConnectionManager
) -> Any:
    """Create a vote request tool for the lead planner.

    Args:
        discussion_id: Current discussion ID.
        ws_manager: WebSocket manager for broadcasting.
    """
    from src.api.websocket.manager import broadcast_sync

    @tool("request_vote")
    def request_vote(question: str, options: str) -> str:
        """发起团队投票，收集各成员对关键分歧点的明确立场。

        当讨论出现重大分歧、需要做出关键设计决策时使用。
        投票将广播给所有观看者，各团队成员应在后续发言中表明立场。

        Args:
            question: 投票问题。示例："战斗系统应采用回合制还是即时制？"
            options: 投票选项，用分号分隔。示例："回合制;即时制;混合制"

        Returns:
            投票已发起的确认信息。
        """
        _broadcast_tool_status("正在发起投票...")
        from datetime import datetime, timezone

        option_list = [o.strip() for o in options.split(";") if o.strip()]
        if len(option_list) < 2:
            return "投票至少需要2个选项。"
        if len(option_list) > 6:
            return "投票选项不能超过6个。"

        vote_id = f"vote-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        vote_event = {
            "type": "vote",
            "data": {
                "discussion_id": discussion_id,
                "vote_id": vote_id,
                "question": question,
                "options": [
                    {"id": f"opt-{i}", "label": opt}
                    for i, opt in enumerate(option_list)
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        # Use broadcast_sync to bridge from sync CrewAI thread to async WebSocket
        try:
            broadcast_sync(vote_event, discussion_id=discussion_id, lobby_event=True)
        except Exception as e:
            logger.warning("Failed to broadcast vote: %s", e)

        option_text = "\n".join(
            f"  {chr(65 + i)}. {opt}" for i, opt in enumerate(option_list)
        )
        return (
            f"投票已发起 (ID: {vote_id})\n"
            f"问题: {question}\n"
            f"选项:\n{option_text}\n\n"
            f"请各位团队成员在回复中明确表达你的选择和理由。"
        )

    return request_vote


# ------------------------------------------------------------------
# Calculator Tool (context-free, safe math evaluation)
# ------------------------------------------------------------------

_calculator_tool = None


def get_calculator_tool():
    """Get (or create) the singleton calculator tool instance."""
    global _calculator_tool
    if _calculator_tool is None:
        _calculator_tool = _create_calculator_tool()
    return _calculator_tool


# AST node types allowed in calculator expressions
_CALC_ALLOWED_NODES = (
    ast.Module,
    ast.Expr,
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Num,  # Python 3.7 compat
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Attribute,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.IfExp,
    ast.Tuple,
    ast.List,
)

# Whitelist of allowed math functions and constants
_CALC_SAFE_NAMES = {
    "abs", "round", "min", "max", "sum", "len",
    "int", "float", "bool",
    "True", "False",
}

_CALC_MATH_NAMES = {
    name for name in dir(math)
    if not name.startswith("_")
}


def _validate_calc_ast(node: ast.AST) -> None:
    """Recursively validate that an AST only contains allowed nodes."""
    if not isinstance(node, _CALC_ALLOWED_NODES):
        raise ValueError(f"不允许的表达式类型: {type(node).__name__}")

    if isinstance(node, ast.Name):
        if node.id not in _CALC_SAFE_NAMES and node.id != "math":
            raise ValueError(f"不允许的名称: {node.id}")

    if isinstance(node, ast.Attribute):
        if not (isinstance(node.value, ast.Name) and node.value.id == "math"):
            raise ValueError(f"只允许 math.xxx 形式的属性访问")
        if node.attr not in _CALC_MATH_NAMES:
            raise ValueError(f"math 模块中不存在: {node.attr}")

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id not in _CALC_SAFE_NAMES:
                raise ValueError(f"不允许的函数: {node.func.id}")

    for child in ast.iter_child_nodes(node):
        _validate_calc_ast(child)


def _create_calculator_tool():
    """Create the safe math calculator tool."""

    safe_globals = {"__builtins__": {}, "math": math}
    safe_locals = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "len": len, "int": int, "float": float, "bool": bool,
        "True": True, "False": False,
    }

    @tool("calculator")
    def calculator(expression: str) -> str:
        """安全计算数学表达式。支持基本运算和 math 模块函数。

        用于验证数值设计：成长曲线、DPS计算、经济循环、概率分析等。

        Args:
            expression: 数学表达式。示例：
                - "1.5 ** 50" (成长曲线)
                - "math.log2(1024)" (对数计算)
                - "0.15 * 2.5" (暴击期望)
                - "100000 * 0.03 * 50" (收入预估)
                - "sum([100 * 1.05**i for i in range(10)])" -- 不支持，请拆分为简单表达式

        Returns:
            计算结果或错误信息。
        """
        _broadcast_tool_status("正在计算...")
        if not expression or not expression.strip():
            return "错误: 请提供数学表达式。"

        expression = expression.strip()

        if len(expression) > 500:
            return "错误: 表达式过长（最大500字符）。"

        # Block dangerous keywords
        dangerous = {"import", "exec", "eval", "open", "compile", "__", "getattr", "setattr", "delattr", "globals", "locals"}
        expr_lower = expression.lower()
        for kw in dangerous:
            if kw in expr_lower:
                return f"错误: 表达式中不允许使用 '{kw}'。"

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as e:
            return f"语法错误: {e}"

        try:
            _validate_calc_ast(tree)
        except ValueError as e:
            return f"安全检查失败: {e}"

        try:
            code = compile(tree, "<calculator>", "eval")
            result = eval(code, safe_globals, safe_locals)  # noqa: S307
            return str(result)
        except ZeroDivisionError:
            return "错误: 除以零。"
        except OverflowError:
            return "错误: 结果溢出，数值过大。"
        except Exception as e:
            return f"计算错误: {e}"

    return calculator


# ------------------------------------------------------------------
# Table Tool (context-free, markdown table generator)
# ------------------------------------------------------------------

_table_tool = None


def get_table_tool():
    """Get (or create) the singleton table tool instance."""
    global _table_tool
    if _table_tool is None:
        _table_tool = _create_table_tool()
    return _table_tool


def _create_table_tool():
    """Create the markdown table generator tool."""

    @tool("create_table")
    def create_table(headers: str, rows: str) -> str:
        """创建格式化的 Markdown 对比表格。

        用于方案对比、数值对比、功能对比等场景。

        Args:
            headers: 表头，用逗号分隔。示例："方案,优势,劣势,风险"
            rows: 表格行，每行用分号分隔，列用逗号分隔。
                  示例："方案A,低成本,功能少,中;方案B,功能全,成本高,低"

        Returns:
            格式化的 Markdown 表格。
        """
        _broadcast_tool_status("正在生成表格...")
        if not headers or not headers.strip():
            return "错误: 请提供表头（用逗号分隔）。"

        header_list = [h.strip() for h in headers.split(",")]
        col_count = len(header_list)

        if col_count == 0:
            return "错误: 表头不能为空。"

        if not rows or not rows.strip():
            # Only headers, no rows
            header_line = "| " + " | ".join(header_list) + " |"
            sep_line = "| " + " | ".join("---" for _ in header_list) + " |"
            return f"{header_line}\n{sep_line}"

        row_list = [r.strip() for r in rows.split(";") if r.strip()]

        # Build table
        lines = []
        header_line = "| " + " | ".join(header_list) + " |"
        sep_line = "| " + " | ".join("---" for _ in header_list) + " |"
        lines.append(header_line)
        lines.append(sep_line)

        for row_str in row_list:
            cols = [c.strip() for c in row_str.split(",")]
            # Pad or truncate to match header count
            while len(cols) < col_count:
                cols.append("")
            cols = cols[:col_count]
            lines.append("| " + " | ".join(cols) + " |")

        return "\n".join(lines)

    return create_table


# ------------------------------------------------------------------
# Game Industry Data Tool (context-free, YAML knowledge base)
# ------------------------------------------------------------------

_industry_data_tool = None


def get_industry_data_tool():
    """Get (or create) the singleton game industry data tool instance."""
    global _industry_data_tool
    if _industry_data_tool is None:
        _industry_data_tool = _create_industry_data_tool()
    return _industry_data_tool


def _create_industry_data_tool():
    """Create the game industry data lookup tool."""
    import yaml

    knowledge_path = Path(__file__).parent.parent / "config" / "knowledge" / "game_industry.yaml"
    try:
        with open(knowledge_path, encoding="utf-8") as f:
            knowledge_base = yaml.safe_load(f)
    except Exception as e:
        logger.error("Failed to load game industry knowledge base: %s", e)
        knowledge_base = {"categories": []}

    @tool("game_industry_data")
    def game_industry_data(query: str) -> str:
        """查询游戏行业参考数据和基准值。

        提供付费指标、留存率、抽卡机制、战斗数值、经济系统、运营数据等行业基准。
        比联网搜索更快更可靠，数据经过整理验证。

        Args:
            query: 查询关键词。示例："付费率", "留存", "抽卡保底", "DPS公式", "经济通胀"

        Returns:
            匹配的行业参考数据。
        """
        _broadcast_tool_status(f"正在查询行业数据「{query[:20]}」...")
        if not query or not query.strip():
            return "错误: 请提供查询关键词。"

        query = query.strip().lower()
        categories = knowledge_base.get("categories", [])

        matched = []
        for cat in categories:
            keywords = [kw.lower() for kw in cat.get("keywords", [])]
            cat_name = cat.get("name", "").lower()

            # Check if query matches any keyword or category name
            score = 0
            for kw in keywords:
                if query in kw or kw in query:
                    score += 2
            if query in cat_name or cat_name in query:
                score += 1
            # Also check individual Chinese characters for keyword matching
            for char in query:
                if '\u4e00' <= char <= '\u9fff' and any(char in kw for kw in keywords):
                    score += 0.5

            if score > 0:
                matched.append((score, cat))

        if not matched:
            # Fallback: search in entry titles and data
            for cat in categories:
                for entry in cat.get("entries", []):
                    title = entry.get("title", "").lower()
                    data = entry.get("data", "").lower()
                    if query in title or query in data:
                        matched.append((1, cat))
                        break

        if not matched:
            cat_names = [c.get("name", "") for c in categories]
            return f"未找到与「{query}」相关的行业数据。\n可查询的类别: {', '.join(cat_names)}"

        # Sort by relevance score (descending), deduplicate
        matched.sort(key=lambda x: x[0], reverse=True)
        seen_names = set()
        lines = [f"「{query}」相关的行业参考数据：\n"]

        for _score, cat in matched:
            name = cat.get("name", "")
            if name in seen_names:
                continue
            seen_names.add(name)

            lines.append(f"## {name}")
            for entry in cat.get("entries", []):
                lines.append(f"**{entry['title']}**")
                lines.append(f"  {entry['data']}")
            lines.append("")

        return "\n".join(lines)

    return game_industry_data
