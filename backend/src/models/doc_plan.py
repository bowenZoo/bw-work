from dataclasses import dataclass, field


@dataclass
class SectionPlan:
    id: str           # "s1", "s2", ...
    title: str        # "战斗系统概述"
    description: str   # 简要说明该章节要讨论什么
    status: str = "pending"  # "pending" | "in_progress" | "completed"


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
                        {"id": s.id, "title": s.title, "description": s.description, "status": s.status}
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
            sections = [SectionPlan(**s) for s in f.get("sections", [])]
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
        for f in self.files:
            for s in f.sections:
                if s.status == "pending":
                    return f, s
        return None, None

    def all_sections_completed(self) -> bool:
        return all(s.status == "completed" for f in self.files for s in f.sections)
