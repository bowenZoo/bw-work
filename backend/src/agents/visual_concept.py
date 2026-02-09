"""Visual Concept Agent - 视觉概念设计师角色.

This agent participates in design discussions from a visual perspective
and can generate concept images to help visualize design ideas.
"""

import asyncio
import logging
from typing import Any

from crewai.tools import tool

from src.agents.base import BaseAgent
from src.image.service import ImageService, get_image_service
from src.image.style_manager import StyleManager, get_style_manager

logger = logging.getLogger(__name__)


class VisualConceptAgent(BaseAgent):
    """Visual Concept Designer agent.

    This agent has two modes of operation:
    1. Team member mode: Participates in discussions, providing visual perspective
    2. Service mode: Called by other agents to generate concept images

    The agent can:
    - Suggest visual styles and approaches
    - Generate concept images based on descriptions
    - Provide feedback on visual design decisions
    """

    role_name = "visual_concept"

    def __init__(
        self,
        llm: Any | None = None,
        config_overrides: dict | None = None,
        image_service: ImageService | None = None,
        style_manager: StyleManager | None = None,
        project_id: str = "",
    ) -> None:
        """Initialize the Visual Concept Agent.

        Args:
            llm: Optional LLM instance.
            config_overrides: Optional dict to override role config values.
            image_service: Image generation service instance.
            style_manager: Style manager instance.
            project_id: Current project ID for image storage.
        """
        super().__init__(llm, config_overrides=config_overrides)
        self._image_service = image_service
        self._style_manager = style_manager
        self._project_id = project_id

    @property
    def image_service(self) -> ImageService:
        """Get the image service instance."""
        if self._image_service is None:
            self._image_service = get_image_service()
        return self._image_service

    @property
    def style_manager(self) -> StyleManager:
        """Get the style manager instance."""
        if self._style_manager is None:
            self._style_manager = get_style_manager()
        return self._style_manager

    def set_project_id(self, project_id: str) -> None:
        """Set the current project ID.

        Args:
            project_id: Project identifier for image storage.
        """
        self._project_id = project_id

    def get_tools(self) -> list[Any]:
        """Get tools available to the Visual Concept Agent.

        Returns:
            List of tool functions for image generation and visual suggestions.
        """
        return [
            self._create_generate_image_tool(),
            self._create_suggest_visual_tool(),
            self._create_list_styles_tool(),
        ]

    def _create_generate_image_tool(self) -> Any:
        """Create the generate_image tool.

        Returns:
            Tool function for image generation.
        """
        image_service = self.image_service
        project_id = self._project_id

        @tool("generate_image")
        def generate_image(
            description: str,
            style: str = "concept_character",
        ) -> str:
            """Generate a concept image based on a text description.

            Use this tool when you need to create a visual representation
            of a design concept being discussed. The image will be stored
            and accessible via the returned URL.

            Args:
                description: Detailed text description of the image to generate.
                            Include visual elements, composition, mood, etc.
                style: Style template to use. Options include:
                       - concept_character: For character designs
                       - concept_scene: For environment/scene designs
                       - concept_item: For item/prop designs
                       - ui_icon: For UI icons
                       - storyboard: For storyboard frames
                       - realistic: For photorealistic images

            Returns:
                A message with the image URL if successful, or an error message.
            """
            if not project_id:
                return "Error: No project context. Cannot generate image without project ID."

            try:
                # Run async function in sync context
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an async context, create a new task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(
                            asyncio.run,
                            image_service.generate(
                                description=description,
                                project_id=project_id,
                                style_id=style,
                                agent="visual_concept",
                            )
                        )
                        result = future.result()
                else:
                    result = loop.run_until_complete(
                        image_service.generate(
                            description=description,
                            project_id=project_id,
                            style_id=style,
                            agent="visual_concept",
                        )
                    )

                if result.success:
                    if result.is_async:
                        return (
                            f"Image generation started (ID: {result.image_id}). "
                            f"The image is being generated and will be available shortly."
                        )
                    return (
                        f"Image generated successfully!\n"
                        f"URL: {result.image_url}\n"
                        f"Style: {result.style_id}\n"
                        f"Size: {result.width}x{result.height}"
                    )
                else:
                    return f"Image generation failed: {result.error}"

            except Exception as e:
                logger.exception("Error in generate_image tool")
                return f"Error generating image: {str(e)}"

        return generate_image

    def _create_suggest_visual_tool(self) -> Any:
        """Create the suggest_visual tool.

        Returns:
            Tool function for visual suggestions.
        """
        style_manager = self.style_manager

        @tool("suggest_visual")
        def suggest_visual(topic: str, category: str = "general") -> str:
            """Provide visual design suggestions for a topic.

            Use this tool to get recommendations on visual approach,
            style, composition, and color schemes for a design topic.

            Args:
                topic: The design topic or concept to provide suggestions for.
                category: Category of the topic. Options include:
                          - character: Character-related designs
                          - environment: Scene/environment designs
                          - ui: User interface elements
                          - item: Items, weapons, props
                          - general: General design topics

            Returns:
                Visual design suggestions and recommendations.
            """
            # Map category to style recommendations
            category_styles = {
                "character": ["concept_character", "storyboard"],
                "environment": ["concept_scene", "realistic"],
                "ui": ["ui_icon"],
                "item": ["concept_item"],
                "general": ["concept_character", "concept_scene"],
            }

            recommended_styles = category_styles.get(category, category_styles["general"])

            # Get style details
            style_info = []
            for style_id in recommended_styles:
                try:
                    style = style_manager.get_style(style_id)
                    style_info.append(f"- {style.name} ({style_id}): {style.description}")
                except Exception:
                    pass

            suggestions = [
                f"Visual suggestions for '{topic}':",
                "",
                "Recommended styles:",
            ]
            suggestions.extend(style_info)

            suggestions.extend([
                "",
                "Key visual considerations:",
                f"- For {category} designs, focus on clarity and readability",
                "- Consider the target platform and display size",
                "- Maintain consistency with existing visual language",
                "- Use color to convey mood and function",
                "",
                "To generate a concept image, use the generate_image tool with a detailed description.",
            ])

            return "\n".join(suggestions)

        return suggest_visual

    def _create_list_styles_tool(self) -> Any:
        """Create the list_styles tool.

        Returns:
            Tool function for listing available styles.
        """
        style_manager = self.style_manager

        @tool("list_image_styles")
        def list_image_styles() -> str:
            """List all available image generation styles.

            Use this tool to see what style templates are available
            for image generation.

            Returns:
                A formatted list of available styles with descriptions.
            """
            styles = style_manager.get_all_styles()
            lines = ["Available image generation styles:", ""]

            for style in styles:
                lines.append(f"- {style.id}: {style.name}")
                if style.description:
                    lines.append(f"  {style.description}")

            return "\n".join(lines)

        return list_image_styles


# Convenience function for creating the agent with image generation context
def create_visual_concept_agent(
    project_id: str,
    llm: Any | None = None,
    image_service: ImageService | None = None,
) -> VisualConceptAgent:
    """Create a Visual Concept Agent with project context.

    Args:
        project_id: Project identifier for image storage.
        llm: Optional LLM instance.
        image_service: Optional image service instance.

    Returns:
        Configured VisualConceptAgent instance.
    """
    return VisualConceptAgent(
        llm=llm,
        image_service=image_service,
        project_id=project_id,
    )
