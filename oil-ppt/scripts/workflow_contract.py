#!/usr/bin/env python3
"""Closed next-action contracts for public status and batch envelopes."""
from __future__ import annotations


STATUS_NEXT_ACTIONS = frozenset({
    "ask_user_to_confirm_outline",
    "ask_user_to_confirm_preview",
    "ask_user_to_confirm_text_only",
    "choose_project_directory",
    "complete",
    "edit_outline",
    "fix_media",
    "run_command",
    "start_editor",
    "wait_for_editor",
    "write_visual_plan",
})
BATCH_NEXT_ACTIONS = STATUS_NEXT_ACTIONS | {"ask_user_to_confirm_previews"}


def validate_next_step(next_step: object, *, allowed_actions: frozenset[str], source: str) -> None:
    """Fail before exposing a next step outside the program-owned action vocabulary."""
    if not isinstance(next_step, dict):
        raise SystemExit(f"{source} contract violation: next must be an object.")
    action = next_step.get("action")
    if not isinstance(action, str) or not action:
        raise SystemExit(f"{source} contract violation: next.action must be a non-empty string.")
    if action not in allowed_actions:
        allowed = ", ".join(sorted(allowed_actions))
        raise SystemExit(
            f"{source} contract violation: unsupported next.action {action!r}. "
            f"Allowed actions: {allowed}."
        )


def validate_status_payload(payload: dict) -> dict:
    validate_next_step(
        payload.get("next"),
        allowed_actions=STATUS_NEXT_ACTIONS,
        source="status",
    )
    return payload


def validate_batch_payload(payload: dict) -> dict:
    projects = payload.get("projects")
    if not isinstance(projects, list):
        raise SystemExit("batch contract violation: projects must be a list.")
    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            raise SystemExit(f"batch contract violation: projects[{index}] must be an object.")
        validate_next_step(
            project.get("next"),
            allowed_actions=STATUS_NEXT_ACTIONS,
            source=f"batch.projects[{index}]",
        )
    validate_next_step(
        payload.get("next"),
        allowed_actions=BATCH_NEXT_ACTIONS,
        source="batch",
    )
    return payload
