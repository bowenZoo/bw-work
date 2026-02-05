"""
决策追踪器

记录设计讨论中的决策，并写入 decisions.md 文件。
"""

import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from src.memory.base import Decision, MemoryStore


class DecisionTracker(MemoryStore[Decision]):
    """
    决策追踪器

    将决策记录保存到 Markdown 文件，便于阅读和版本控制。
    """

    def __init__(self, data_dir: str = "data/projects"):
        """
        初始化决策追踪器

        Args:
            data_dir: 数据目录路径
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._decisions_cache: dict[str, Decision] = {}
        self._project_cache: dict[str, list[Decision]] = {}
        self._file_mtimes: dict[str, float] = {}
        self._decision_project: dict[str, str] = {}

    def _get_decisions_file(self, project_id: str) -> Path:
        """获取决策文件路径"""
        project_dir = self.data_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir / "decisions.md"

    def _format_decision(self, decision: Decision) -> str:
        """格式化单个决策为 Markdown"""
        return f"""### {decision.title}

- **ID**: {decision.id}
- **讨论**: {decision.discussion_id}
- **决策者**: {decision.made_by}
- **时间**: {decision.created_at.strftime("%Y-%m-%d %H:%M")}

**内容**:
{decision.description}

**原因**:
{decision.rationale}

---
"""

    def _parse_decisions_file(self, project_id: str) -> list[Decision]:
        """解析决策文件"""
        file_path = self._get_decisions_file(project_id)

        if not file_path.exists():
            return []

        mtime = file_path.stat().st_mtime
        cached = self._project_cache.get(project_id)
        if cached is not None and self._file_mtimes.get(project_id) == mtime:
            return cached

        content = file_path.read_text(encoding="utf-8")
        decisions = []

        # Clear previous cache for this project
        for decision_id, pid in list(self._decision_project.items()):
            if pid == project_id:
                self._decisions_cache.pop(decision_id, None)
                self._decision_project.pop(decision_id, None)

        # 匹配每个决策块
        pattern = r"### (.+?)\n\n- \*\*ID\*\*: (.+?)\n- \*\*讨论\*\*: (.+?)\n- \*\*决策者\*\*: (.+?)\n- \*\*时间\*\*: (.+?)\n\n\*\*内容\*\*:\n(.*?)\n\n\*\*原因\*\*:\n(.*?)\n\n---"
        matches = re.findall(pattern, content, re.DOTALL)

        for match in matches:
            title, decision_id, discussion_id, made_by, time_str, description, rationale = match
            try:
                created_at = datetime.strptime(time_str.strip(), "%Y-%m-%d %H:%M")
            except ValueError:
                created_at = datetime.now()

            decision = Decision(
                id=decision_id.strip(),
                discussion_id=discussion_id.strip(),
                title=title.strip(),
                description=description.strip(),
                rationale=rationale.strip(),
                made_by=made_by.strip(),
                created_at=created_at,
            )
            decisions.append(decision)
            self._decisions_cache[decision.id] = decision
            self._decision_project[decision.id] = project_id

        self._project_cache[project_id] = decisions
        self._file_mtimes[project_id] = mtime

        return decisions

    def save(self, decision: Decision, project_id: str | None = None) -> str:
        """
        保存决策

        Args:
            decision: 决策对象
            project_id: 项目 ID（如果不在 decision 中指定）

        Returns:
            决策 ID
        """
        # 确保有 ID
        if not decision.id:
            decision.id = str(uuid4())

        # 从 discussion_id 推断 project_id（如果需要）
        if project_id is None:
            # 尝试从缓存中查找
            # 如果找不到，使用 "default" 项目
            project_id = "default"

        file_path = self._get_decisions_file(project_id)

        # 读取现有内容
        if file_path.exists():
            existing_content = file_path.read_text(encoding="utf-8")
        else:
            existing_content = f"# 设计决策记录\n\n> 项目: {project_id}\n\n"

        # 追加新决策
        new_content = existing_content + self._format_decision(decision)
        file_path.write_text(new_content, encoding="utf-8")

        # 更新缓存
        self._decisions_cache[decision.id] = decision
        self._decision_project[decision.id] = project_id
        self._project_cache.pop(project_id, None)
        self._file_mtimes.pop(project_id, None)

        return decision.id

    def load(self, decision_id: str, project_id: str | None = None) -> Decision | None:
        """
        加载决策

        Args:
            decision_id: 决策 ID
            project_id: 项目 ID（可选，如果指定则只在该项目中查找）

        Returns:
            决策对象，不存在时返回 None
        """
        # 先从缓存查找
        if decision_id in self._decisions_cache:
            return self._decisions_cache[decision_id]

        # 如果指定了项目，只在该项目中查找
        if project_id:
            self._parse_decisions_file(project_id)
            return self._decisions_cache.get(decision_id)

        # 否则扫描所有项目
        for project_dir in self.data_dir.iterdir():
            if project_dir.is_dir():
                self._parse_decisions_file(project_dir.name)

        return self._decisions_cache.get(decision_id)

    def search(self, query: str, limit: int = 10, project_id: str | None = None) -> list[Decision]:
        """
        搜索决策

        Args:
            query: 搜索关键词
            limit: 返回结果数量限制
            project_id: 项目 ID（可选）

        Returns:
            匹配的决策列表
        """
        results = []

        # 确定搜索范围
        if project_id:
            project_ids = [project_id]
        else:
            project_ids = [d.name for d in self.data_dir.iterdir() if d.is_dir()]

        for pid in project_ids:
            decisions = self._parse_decisions_file(pid)
            for decision in decisions:
                if (
                    query.lower() in decision.title.lower()
                    or query.lower() in decision.description.lower()
                    or query.lower() in decision.rationale.lower()
                ):
                    results.append(decision)
                    if len(results) >= limit:
                        return results

        return results

    def delete(self, decision_id: str, project_id: str | None = None) -> bool:
        """
        删除决策

        注意：由于使用 Markdown 文件存储，删除操作会重写整个文件。

        Args:
            decision_id: 决策 ID
            project_id: 项目 ID

        Returns:
            是否成功删除
        """
        # 找到决策所在的项目
        if project_id is None:
            decision = self.load(decision_id)
            if decision is None:
                return False
            # 扫描所有项目找到包含该决策的文件
            for project_dir in self.data_dir.iterdir():
                if project_dir.is_dir():
                    decisions = self._parse_decisions_file(project_dir.name)
                    if any(d.id == decision_id for d in decisions):
                        project_id = project_dir.name
                        break

        if project_id is None:
            return False

        # 重新解析并过滤
        decisions = self._parse_decisions_file(project_id)
        remaining = [d for d in decisions if d.id != decision_id]

        if len(remaining) == len(decisions):
            return False

        # 重写文件
        file_path = self._get_decisions_file(project_id)
        content = f"# 设计决策记录\n\n> 项目: {project_id}\n\n"
        for decision in remaining:
            content += self._format_decision(decision)

        file_path.write_text(content, encoding="utf-8")

        # 更新缓存
        if decision_id in self._decisions_cache:
            del self._decisions_cache[decision_id]
        if decision_id in self._decision_project:
            del self._decision_project[decision_id]
        self._project_cache.pop(project_id, None)
        self._file_mtimes.pop(project_id, None)

        return True

    def list_all(self, offset: int = 0, limit: int = 100, project_id: str | None = None) -> list[Decision]:
        """
        列出所有决策

        Args:
            offset: 起始位置
            limit: 返回数量限制
            project_id: 项目 ID（可选）

        Returns:
            决策列表
        """
        results = []

        # 确定搜索范围
        if project_id:
            project_ids = [project_id]
        else:
            project_ids = [d.name for d in self.data_dir.iterdir() if d.is_dir()]

        for pid in project_ids:
            decisions = self._parse_decisions_file(pid)
            results.extend(decisions)

        # 按时间倒序排序
        results.sort(key=lambda d: d.created_at, reverse=True)

        # 应用分页
        return results[offset : offset + limit]

    def list_by_discussion(self, discussion_id: str, project_id: str | None = None) -> list[Decision]:
        """
        列出讨论相关的所有决策

        Args:
            discussion_id: 讨论 ID
            project_id: 项目 ID（可选）

        Returns:
            决策列表
        """
        all_decisions = self.list_all(project_id=project_id)
        return [d for d in all_decisions if d.discussion_id == discussion_id]

    def __repr__(self) -> str:
        """字符串表示"""
        return f"DecisionTracker(data_dir='{self.data_dir}')"
