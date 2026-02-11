from dataclasses import dataclass, field


@dataclass
class SectionPlan:
    id: str           # "s1", "s2", ...
    title: str        # "战斗系统概述"
    description: str   # 简要说明该章节要讨论什么
    status: str = "pending"  # "pending" | "in_progress" | "completed"
    related_agenda_items: list[str] = field(default_factory=list)  # 关联的 agenda item IDs
    revision_count: int = 0  # 被回溯修订的次数
    reopened_reason: str | None = None  # 重开原因


@dataclass
class FilePlan:
    filename: str      # "战斗系统设计.md"
    title: str         # "战斗系统设计方案"
    sections: list[SectionPlan] = field(default_factory=list)


@dataclass
class DocPlan:
    discussion_id: str
    topic: str
    files: list[FilePlan] = field(default_factory=list)
    current_section_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "discussion_id": self.discussion_id,
            "topic": self.topic,
            "files": [
                {
                    "filename": f.filename,
                    "title": f.title,
                    "sections": [
                        {
                            "id": s.id,
                            "title": s.title,
                            "description": s.description,
                            "status": s.status,
                            "related_agenda_items": s.related_agenda_items,
                            "revision_count": s.revision_count,
                            "reopened_reason": s.reopened_reason,
                        }
                        for s in f.sections
                    ],
                }
                for f in self.files
            ],
            "current_section_id": self.current_section_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DocPlan":
        files = []
        for f in data.get("files", []):
            sections = []
            for s in f.get("sections", []):
                sections.append(SectionPlan(
                    id=s["id"],
                    title=s["title"],
                    description=s["description"],
                    status=s.get("status", "pending"),
                    related_agenda_items=s.get("related_agenda_items", []),
                    revision_count=s.get("revision_count", 0),
                    reopened_reason=s.get("reopened_reason"),
                ))
            files.append(FilePlan(filename=f["filename"], title=f["title"], sections=sections))
        return cls(
            discussion_id=data["discussion_id"],
            topic=data["topic"],
            files=files,
            current_section_id=data.get("current_section_id"),
        )

    def get_section(self, section_id: str) -> tuple["FilePlan | None", "SectionPlan | None"]:
        for f in self.files:
            for s in f.sections:
                if s.id == section_id:
                    return f, s
        return None, None

    def get_next_pending_section(self) -> tuple["FilePlan | None", "SectionPlan | None"]:
        # 优先返回 in_progress 的章节（上轮未完成，需继续讨论）
        for f in self.files:
            for s in f.sections:
                if s.status == "in_progress":
                    return f, s
        # 其次返回 pending 的章节
        for f in self.files:
            for s in f.sections:
                if s.status == "pending":
                    return f, s
        return None, None

    def all_sections_completed(self) -> bool:
        return all(s.status == "completed" for f in self.files for s in f.sections)

    def split_section(self, section_id: str, new_sections: list["SectionPlan"]) -> bool:
        """将一个未完成的章节拆分为多个子章节。"""
        for f in self.files:
            for i, s in enumerate(f.sections):
                if s.id == section_id:
                    if s.status == "completed":
                        return False
                    f.sections[i:i + 1] = new_sections
                    return True
        return False

    def merge_sections(self, section_ids: list[str], merged: "SectionPlan") -> bool:
        """将同一文件内的多个未完成章节合并为一个。"""
        # 找到所有 section 所在的文件，确保在同一个文件内
        target_file: FilePlan | None = None
        indices: list[int] = []
        for f in self.files:
            found_indices = []
            for i, s in enumerate(f.sections):
                if s.id in section_ids:
                    if s.status == "completed":
                        return False
                    found_indices.append(i)
            if found_indices:
                if target_file is not None:
                    return False  # section 分布在不同文件中
                target_file = f
                indices = found_indices
        if target_file is None or len(indices) != len(section_ids):
            return False
        # 在最小索引位置插入合并后的 section，删除原有的
        indices.sort()
        insert_pos = indices[0]
        for offset, idx in enumerate(indices):
            del target_file.sections[idx - offset]
        target_file.sections.insert(insert_pos, merged)
        return True

    def add_section(self, file_index: int, section: "SectionPlan", after_section_id: str | None = None) -> bool:
        """在指定文件的指定位置插入新章节。"""
        if file_index < 0 or file_index >= len(self.files):
            return False
        # ID conflict check
        for f in self.files:
            for s in f.sections:
                if s.id == section.id:
                    return False
        f = self.files[file_index]
        if after_section_id is None:
            f.sections.insert(0, section)
            return True
        for i, s in enumerate(f.sections):
            if s.id == after_section_id:
                f.sections.insert(i + 1, section)
                return True
        return False

    def add_file(self, file_plan: "FilePlan") -> bool:
        """追加新文件到计划中。返回 False 如果文件名冲突。"""
        for f in self.files:
            if f.filename == file_plan.filename:
                return False
        self.files.append(file_plan)
        return True

    def reopen_section(self, section_id: str, reason: str) -> bool:
        """将已完成的章节重新打开。"""
        for f in self.files:
            for s in f.sections:
                if s.id == section_id:
                    if s.status != "completed":
                        return False
                    s.status = "pending"
                    s.reopened_reason = reason
                    s.revision_count += 1
                    return True
        return False

    def get_completed_sections(self) -> list[tuple["FilePlan", "SectionPlan"]]:
        """获取所有已完成的章节。"""
        result = []
        for f in self.files:
            for s in f.sections:
                if s.status == "completed":
                    result.append((f, s))
        return result

    def get_reopened_sections(self) -> list[tuple["FilePlan", "SectionPlan"]]:
        """获取所有被重新打开过的章节。"""
        result = []
        for f in self.files:
            for s in f.sections:
                if s.reopened_reason is not None:
                    result.append((f, s))
        return result

    def remove_section(self, section_id: str) -> tuple[bool, str | None]:
        """删除章节。如果文件变空也一并删除。返回 (success, filename)。"""
        for f in self.files:
            for i, s in enumerate(f.sections):
                if s.id == section_id:
                    filename = f.filename
                    del f.sections[i]
                    if not f.sections:
                        self.files.remove(f)
                    return True, filename
        return False, None

    def remove_file(self, filename: str) -> bool:
        """删除整个文件。"""
        for i, f in enumerate(self.files):
            if f.filename == filename:
                del self.files[i]
                return True
        return False

    def replace_plan(self, new_files: list["FilePlan"]) -> list["FilePlan"]:
        """整体替换文件结构，保留 discussion_id/topic。返回旧 files 供参考。"""
        old_files = self.files
        self.files = new_files
        self.current_section_id = None
        return old_files
