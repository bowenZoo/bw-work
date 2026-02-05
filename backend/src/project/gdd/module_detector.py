"""Module detection using LLM analysis."""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Optional

from src.project.models import GDDModule, ParsedGDD, ParsedText

logger = logging.getLogger(__name__)

# Prompt version for cache invalidation
PROMPT_VERSION = "1.0.0"


class ModuleDetector:
    """Detects functional modules in GDD documents using LLM.

    Uses OpenAI/Claude API to analyze GDD content and identify
    functional modules that should be discussed.
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        model: str = "gpt-4",
    ):
        """Initialize the module detector.

        Args:
            cache_dir: Directory for caching detection results.
            model: LLM model to use for detection.
        """
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.model = model
        self._prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Load the prompt template from file."""
        prompt_path = Path(__file__).parent / "prompts" / "module_detection.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        # Fallback prompt if file not found
        return """
Analyze this game design document and identify functional modules.
Output JSON with: title, overview, and modules array.
Each module needs: id, name, description, source_section, keywords, dependencies, estimated_rounds.

Document:
{content}
"""

    def _get_cache_key(self, content_hash: str) -> str:
        """Generate cache key from content hash and prompt version.

        Args:
            content_hash: Hash of the GDD content.

        Returns:
            Cache key string.
        """
        combined = f"{content_hash}:{PROMPT_VERSION}:{self.model}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _get_cached(self, cache_key: str) -> Optional[ParsedGDD]:
        """Try to get cached detection result.

        Args:
            cache_key: Cache key to look up.

        Returns:
            ParsedGDD if found in cache, None otherwise.
        """
        if not self.cache_dir:
            return None

        cache_path = self.cache_dir / f"modules_{cache_key}.json"
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._parse_result(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def _save_cache(self, cache_key: str, result: dict) -> None:
        """Save detection result to cache.

        Args:
            cache_key: Cache key.
            result: Detection result dictionary.
        """
        if not self.cache_dir:
            return

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self.cache_dir / f"modules_{cache_key}.json"

        temp_path = cache_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        temp_path.replace(cache_path)

    def _format_sections(self, sections: list) -> str:
        """Format sections for the prompt.

        Args:
            sections: List of Section objects.

        Returns:
            Formatted section string.
        """
        if not sections:
            return "(No section structure detected)"

        lines = []
        for s in sections:
            indent = "  " * (s.level - 1)
            lines.append(f"{indent}- [{s.level}] {s.title}")
        return "\n".join(lines)

    def _build_prompt(self, parsed_text: ParsedText) -> str:
        """Build the LLM prompt from parsed text.

        Args:
            parsed_text: Parsed GDD content.

        Returns:
            Formatted prompt string.
        """
        sections_str = self._format_sections(parsed_text.sections)

        # Truncate content if too long (keep first 50k chars)
        content = parsed_text.content
        if len(content) > 50000:
            content = content[:50000] + "\n\n... (content truncated)"

        return self._prompt_template.format(
            title=parsed_text.title,
            sections=sections_str,
            content=content,
        )

    def _parse_result(self, data: dict) -> ParsedGDD:
        """Parse LLM response into ParsedGDD.

        Args:
            data: Dictionary from LLM response.

        Returns:
            ParsedGDD object.
        """
        modules = []
        for m in data.get("modules", []):
            module = GDDModule(
                id=m.get("id", "unknown"),
                name=m.get("name", "Unknown Module"),
                description=m.get("description", ""),
                source_section=m.get("source_section", ""),
                keywords=m.get("keywords", []),
                dependencies=m.get("dependencies", []),
                estimated_rounds=m.get("estimated_rounds", 3),
            )
            modules.append(module)

        return ParsedGDD(
            title=data.get("title", "Untitled"),
            overview=data.get("overview", ""),
            modules=modules,
            raw_content="",  # Don't store full content in result
        )

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response text.

        Handles cases where JSON is wrapped in markdown code blocks.

        Args:
            text: Raw LLM response text.

        Returns:
            Parsed JSON dictionary.

        Raises:
            ValueError: If JSON extraction fails.
        """
        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Try the whole text
            json_str = text.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try to find JSON object boundaries
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Failed to parse JSON from LLM response: {e}")

    async def detect_async(
        self,
        parsed_text: ParsedText,
        content_hash: str,
    ) -> ParsedGDD:
        """Detect modules asynchronously using LLM.

        Args:
            parsed_text: Parsed GDD content.
            content_hash: Hash of the original content for caching.

        Returns:
            ParsedGDD with detected modules.
        """
        # Check cache
        cache_key = self._get_cache_key(content_hash)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info(f"Using cached module detection result (key={cache_key})")
            return cached

        # Build prompt
        prompt = self._build_prompt(parsed_text)

        # Call LLM
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI()

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a game design expert. Analyze documents and output JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
            )

            result_text = response.choices[0].message.content or ""

        except ImportError:
            raise RuntimeError("openai package is required for module detection")
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise RuntimeError(f"Module detection failed: {e}")

        # Parse result
        try:
            result_data = self._extract_json(result_text)
            parsed_gdd = self._parse_result(result_data)

            # Save to cache
            self._save_cache(cache_key, result_data)

            logger.info(f"Detected {len(parsed_gdd.modules)} modules")
            return parsed_gdd

        except ValueError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise RuntimeError(f"Failed to parse module detection result: {e}")

    def detect_sync(
        self,
        parsed_text: ParsedText,
        content_hash: str,
    ) -> ParsedGDD:
        """Detect modules synchronously using LLM.

        Args:
            parsed_text: Parsed GDD content.
            content_hash: Hash of the original content for caching.

        Returns:
            ParsedGDD with detected modules.
        """
        # Check cache
        cache_key = self._get_cache_key(content_hash)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info(f"Using cached module detection result (key={cache_key})")
            return cached

        # Build prompt
        prompt = self._build_prompt(parsed_text)

        # Call LLM
        try:
            from openai import OpenAI

            client = OpenAI()

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a game design expert. Analyze documents and output JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
            )

            result_text = response.choices[0].message.content or ""

        except ImportError:
            raise RuntimeError("openai package is required for module detection")
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise RuntimeError(f"Module detection failed: {e}")

        # Parse result
        try:
            result_data = self._extract_json(result_text)
            parsed_gdd = self._parse_result(result_data)

            # Save to cache
            self._save_cache(cache_key, result_data)

            logger.info(f"Detected {len(parsed_gdd.modules)} modules")
            return parsed_gdd

        except ValueError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise RuntimeError(f"Failed to parse module detection result: {e}")

    def suggest_order(self, modules: list[GDDModule]) -> list[str]:
        """Suggest discussion order based on module dependencies.

        Performs topological sort to ensure dependencies are discussed first.

        Args:
            modules: List of detected modules.

        Returns:
            List of module IDs in suggested order.
        """
        # Build dependency graph
        module_ids = {m.id for m in modules}
        graph = {m.id: [] for m in modules}
        in_degree = {m.id: 0 for m in modules}

        for m in modules:
            for dep in m.dependencies:
                if dep in module_ids:
                    graph[dep].append(m.id)
                    in_degree[m.id] += 1

        # Kahn's algorithm for topological sort
        queue = [mid for mid, degree in in_degree.items() if degree == 0]
        order = []

        while queue:
            # Sort by estimated_rounds (discuss simpler modules first)
            queue.sort(key=lambda x: next((m.estimated_rounds for m in modules if m.id == x), 5))
            current = queue.pop(0)
            order.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Handle cycles (add remaining modules)
        remaining = [mid for mid in module_ids if mid not in order]
        if remaining:
            logger.warning(f"Dependency cycle detected, adding remaining modules: {remaining}")
            order.extend(remaining)

        return order

    def validate_order(self, modules: list[GDDModule], order: list[str]) -> tuple[bool, list[str]]:
        """Validate that the given order respects dependencies.

        Args:
            modules: List of detected modules.
            order: Proposed discussion order.

        Returns:
            Tuple of (is_valid, list of violated dependency descriptions).
        """
        module_ids = {m.id for m in modules}
        module_map = {m.id: m for m in modules}

        # Track which modules have been "discussed"
        discussed = set()
        violations = []

        for mid in order:
            if mid not in module_ids:
                continue

            module = module_map[mid]
            for dep in module.dependencies:
                if dep in module_ids and dep not in discussed:
                    violations.append(
                        f"'{module.name}' depends on '{module_map[dep].name}' which comes later"
                    )

            discussed.add(mid)

        return len(violations) == 0, violations
