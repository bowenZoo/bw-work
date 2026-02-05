"""Output generation module for design documents and summaries."""

__all__ = ["DesignDocGenerator", "ProjectSummaryGenerator"]


def __getattr__(name: str):
    if name == "DesignDocGenerator":
        from src.project.output.design_doc import DesignDocGenerator
        return DesignDocGenerator
    elif name == "ProjectSummaryGenerator":
        from src.project.output.summary import ProjectSummaryGenerator
        return ProjectSummaryGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
