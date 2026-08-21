"""Shared rules for deciding which Live2D folders appear in the UI."""


def is_discoverable_live2d_dir(name: str) -> bool:
    """Hide dot-directories and common backup-directory naming conventions."""
    normalized = str(name or "").strip().lower()
    if not normalized or normalized.startswith("."):
        return False
    return ".bak." not in normalized and not normalized.endswith((".bak", "~"))
