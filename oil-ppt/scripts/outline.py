"""Outline is deliberately a human-authored Markdown reference only."""
from __future__ import annotations

import hashlib
from pathlib import Path


def outline_path(project: Path) -> Path:
    return project / "outline.md"


def read_outline(project: Path) -> str:
    return outline_path(project).read_text(encoding="utf-8")


def outline_digest(project: Path) -> str:
    return hashlib.sha256(outline_path(project).read_bytes()).hexdigest()
