"""Read-only compatibility and explicit, reversible workspace migration."""

from .workspace_migration import acquisition_handoff_issues, apply, plan, rollback

__all__ = ["acquisition_handoff_issues", "apply", "plan", "rollback"]
