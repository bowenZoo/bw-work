"""Shared tools for crew agents.

This module provides tools that can be used by agents in discussions
to request image generation and other services.
"""

import asyncio
import logging
from typing import Any

from crewai.tools import tool

logger = logging.getLogger(__name__)


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
