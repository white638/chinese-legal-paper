"""Typed results shared by the local workflow engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    artifact: str | None = None
    severity: str = "error"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }
        if self.artifact:
            payload["artifact"] = self.artifact
        return payload


@dataclass(frozen=True)
class GateResult:
    stage: str
    status: GateStatus
    findings: tuple[Finding, ...] = ()
    generated: tuple[str, ...] = ()
    semantic_digest: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in {GateStatus.PASS, GateStatus.NOT_APPLICABLE}

    @classmethod
    def pass_(
        cls,
        stage: str,
        *,
        generated: Iterable[str] = (),
        semantic_digest: str | None = None,
    ) -> "GateResult":
        return cls(
            stage=stage,
            status=GateStatus.PASS,
            generated=tuple(generated),
            semantic_digest=semantic_digest,
        )

    @classmethod
    def fail(cls, stage: str, findings: Iterable[Finding]) -> "GateResult":
        return cls(stage=stage, status=GateStatus.FAIL, findings=tuple(findings))

    @classmethod
    def blocked(cls, stage: str, findings: Iterable[Finding]) -> "GateResult":
        return cls(stage=stage, status=GateStatus.BLOCKED, findings=tuple(findings))

    @classmethod
    def not_applicable(cls, stage: str, message: str = "") -> "GateResult":
        findings = (Finding("STAGE.NOT_APPLICABLE", message, severity="info"),) if message else ()
        return cls(stage=stage, status=GateStatus.NOT_APPLICABLE, findings=findings)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status.value,
            "findings": [finding.as_dict() for finding in self.findings],
            "generated": list(self.generated),
            "semantic_digest": self.semantic_digest,
        }


@dataclass(frozen=True)
class ArtifactSpec:
    """One required artifact, or one-of alternatives when ``alternatives`` is set."""

    path: str
    alternatives: tuple[str, ...] = ()
    meaningful: bool = True
    report_must_pass: bool = False
    description: str = ""

    @property
    def candidates(self) -> tuple[str, ...]:
        return (self.path, *self.alternatives)


@dataclass
class WorkflowStatus:
    next_stage: str = "intake"
    is_complete: bool = False
    stages: dict[str, GateResult] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "next_stage": self.next_stage,
            "is_complete": self.is_complete,
            "stages": {key: value.as_dict() for key, value in self.stages.items()},
            "findings": [finding.as_dict() for finding in self.findings],
        }
