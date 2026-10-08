"""Project an experiment's instruction surface without changing controller code."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

VARIANTS = ("current", "lean", "minimal")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sections(text: str) -> list[tuple[str, str]]:
    starts = list(re.finditer(r"(?m)^## (.+)$", text))
    return [(match.group(1), text[match.start():starts[index + 1].start() if index + 1 < len(starts) else len(text)])
            for index, match in enumerate(starts)]


def project(text: str, variant: str) -> str:
    if variant not in VARIANTS:
        raise ValueError("instruction_variant must be current, lean or minimal")
    if variant == "current":
        return text
    if variant == "lean":
        selected = []
        for number, tokens in (("1.", ()), ("3.", ()), ("4.", ()), (None, ("完成",))):
            found = [body for title, body in sections(text)
                     if (title.startswith(number) if number else all(token in title for token in tokens))]
            if len(found) != 1:
                raise ValueError("lean projection needs unambiguous routing, controller, invariants and completion sections")
            selected.append(found[0].strip())
        retained = "\n\n".join(selected)
        if not all(token in retained for token in ("avereth-prose-packet/v2", "protected atoms", "allowed_writes", "OUTPUT.QA_REQUIRED")):
            raise ValueError("lean projection cannot locate the complete current hard contract; use current for this source version")
        return "# Avereth instruction experiment\n\n" + retained + (
            "\n\n领域细则按当前 plan 的 reference_requests 章节读取。选题在检查材料或编译 packet 前读取 "
            "references/topic-selection-protocol.md；build 按 references/engine/manuscript-compiler.md 与 "
            "references/academic-prose.md 运行；Commonplace 开启时读取 references/commonplace-writing.md。\n")
    return """# Avereth minimal instruction experiment

Direct handles bounded answers and surface edits preserving title, claims, scope,
evidence and deliverable identity; no paper workspace or doctor is needed.
Workspace handles research, substantive changes and final deliverables. Use the
supplied controller with doctor, status and plan, then its earliest incomplete stage,
reference_requests and allowed_writes. Existing gates and hash-bound receipts own
scientific state and completion. Never bypass them or introduce another state source.

Never fabricate sources, execution, results, reviews, consent or completion. Source
metadata is candidate-only until lawful content verification. Preserve source identity,
numbers, negative findings and inference limits from canonical literature, design
and execution artifacts. Before design or body prose obtain the user's exact question,
motivation, scope, working title and title authority confirmation. Publishing, sending,
payments and scope changes require existing user authorization.

Body facts use only the validated current ProsePacket and protected atoms. Keep workflow
state and reviewer concerns out of Writer inputs. Commonplace adds only a bound language
packet; it cannot authorize facts or citations. Apply current compiler, fidelity,
borrowing and review contracts through the controller's references. Isolated outputs
need distinct actual contexts; declared provenance is never host-signed provenance.

For topic selection read references/topic-selection-protocol.md before inspecting
materials or compiling packets. Continue authorized reversible work to its endpoint
or a real checkpoint. Report missing evidence or access truthfully. Final output must
follow its audit receipt, actual page inspection and transactional output gate;
OUTPUT.QA_REQUIRED alone is not completion. Do not repeat an unchanged failed action.
"""


def apply_variant(bundle: Path, variant: str) -> dict:
    skill = bundle / "skills/cnki-paper/SKILL.md"
    source = skill.read_bytes().decode("utf-8")
    rendered = project(source, variant)
    if rendered != source:
        skill.write_text(rendered, encoding="utf-8")
    return {"variant": variant, "path": "skills/cnki-paper/SKILL.md", "source_sha256": digest(source),
            "effective_sha256": hashlib.sha256(skill.read_bytes()).hexdigest(),
            "source_bytes": len(source.encode("utf-8")), "effective_bytes": len(skill.read_bytes()),
            "measurement_scope": "instruction file bytes; not actual reads or model tokens",
            "controller_modified": False, "permission_profile_modified": False}
