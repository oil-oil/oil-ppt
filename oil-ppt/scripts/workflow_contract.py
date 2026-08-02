"""Closed action vocabulary for the HTML-first workflow."""
from __future__ import annotations

STATUS_NEXT_ACTIONS = frozenset({
    "edit_outline", "ask_user_to_confirm_outline",
    "author_slides", "edit_slide", "fix_media", "run_command",
    "ask_user_to_confirm_preview", "complete",
})
BATCH_NEXT_ACTIONS = STATUS_NEXT_ACTIONS


def validate_next_step(next_step: object, *, allowed_actions: frozenset[str], source: str) -> None:
    if not isinstance(next_step, dict):
        raise SystemExit(f"{source} contract violation: next must be an object.")
    action = next_step.get("action")
    if not isinstance(action, str) or action not in allowed_actions:
        raise SystemExit(f"{source} contract violation: unsupported next.action {action!r}.")
    if action == "author_slides":
        for field in ("brief", "slide_add_usage", "command_when_ready"):
            if not isinstance(next_step.get(field), str) or not next_step[field].strip():
                raise SystemExit(f"{source} contract violation: author_slides requires non-empty {field}.")


def validate_status_payload(payload: dict) -> dict:
    validate_next_step(payload.get("next"), allowed_actions=STATUS_NEXT_ACTIONS, source="status")
    return payload


def validate_batch_payload(payload: dict) -> dict:
    projects = payload.get("projects")
    if not isinstance(projects, list):
        raise SystemExit("batch contract violation: projects must be a list.")
    for index, item in enumerate(projects):
        if not isinstance(item, dict):
            raise SystemExit(f"batch contract violation: projects[{index}] must be an object.")
        validate_next_step(item.get("next"), allowed_actions=STATUS_NEXT_ACTIONS, source=f"batch.projects[{index}]")
    validate_next_step(payload.get("next"), allowed_actions=BATCH_NEXT_ACTIONS, source="batch")
    return payload
