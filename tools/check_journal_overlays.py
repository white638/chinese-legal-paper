#!/usr/bin/env python3
"""Keep journal packs as overlays over the core empirical method contracts."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKS_RELATIVE = Path("skills/journal-fit/packs")
VENUE_REGISTRY_RELATIVE = Path("skills/journal-fit/references/venue-overlay-registry.json")
JOURNAL_SKILL_RELATIVE = Path("skills/journal-fit/SKILL.md")
METHOD_REGISTRY_RELATIVE = Path(
    "skills/empirical-research/references/method-adapter-registry.json"
)
METHOD_CONTRACT_LOADER_RELATIVE = Path(
    "skills/empirical-research/scripts/method_contract_loader.py"
)
CORE_METHOD_REQUIREMENTS_RELATIVE = Path(
    "skills/empirical-research/references/method-adapters.md"
)
OVERLAY_FILENAME = "journal-overlay.json"
OVERLAY_SCHEMA = "avereth-journal-method-overlay/v1"

ALLOWED_OVERLAY_KEYS = {
    "schema_version",
    "journal",
    "core_method_contract_ref",
    "reporting",
    "transparency",
    "presentation",
    "submission",
    "sources",
}
def _shared_reserved_method_keys() -> set[str]:
    path = ROOT / METHOD_CONTRACT_LOADER_RELATIVE
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "RESERVED_SUPPLEMENTAL_KEYS"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, set) and all(isinstance(item, str) for item in value):
                return value
    raise RuntimeError("method_contract_loader.py lacks literal RESERVED_SUPPLEMENTAL_KEYS")


CORE_METHOD_AUTHORITY_KEYS = _shared_reserved_method_keys()
RESERVED_METHOD_KEYS = CORE_METHOD_AUTHORITY_KEYS | {
    "workflow_stages",
    "stages",
    "receipts",
    "completion_semantics",
    "next_stage",
    "completed_stage",
    "status",
    "gate",
    "receipt",
    "method_override",
    "execution_engine",
}
FORBIDDEN_DIRECTORY_NAMES = {"schemas", "validators"}
FORBIDDEN_CODE_NAME = re.compile(
    r"(?:validator|validate|method[_-]?contract|method[_-]?registry|claim[_-]?capabilit|inference[_-]?ceiling)",
    re.IGNORECASE,
)
STRUCTURED_DEFINITION = re.compile(
    r"^\s*[\"']?("
    + "|".join(
        sorted((re.escape(item) for item in RESERVED_METHOD_KEYS), key=len, reverse=True)
    )
    + r")[\"']?\s*[:=]",
    re.MULTILINE,
)
DIRECT_ENGINE = re.compile(
    r"Execution bridge|StatsPAI|Stata MCP|detect_design|as_handle\s*=\s*true|audit_result\s*\(",
    re.IGNORECASE,
)
APSR_CONTROL_RISK = re.compile(
    r"\borchestrator\b|【Next】|Execution bridge|StatsPAI|Stata MCP|detect_design|"
    r"as_handle\s*=\s*true|audit_result\s*\(",
    re.IGNORECASE,
)
CORE_REQUIREMENT_ID = re.compile(r"\bCORE\.[A-Z][A-Z0-9_.]+\b")
METHOD_TOOL_CATALOG_SIGNAL = re.compile(
    r"Callaway|Sun.?Abraham|Goodman.?Bacon|boottest|Driscoll|PPML|randomization inference|"
    r"wild-cluster|rdrobust|MatchIt|WeightIt|process tracing|GBTM|trajectory|Cox|multilevel|HLM",
    re.IGNORECASE,
)
METHOD_TOOL_CATALOG_BOUNDARY = re.compile(
    r"Tool catalog only|仅为工具目录",
    re.IGNORECASE,
)
VENUE_METHOD_AUTHORITY_PATTERNS = (
    (
        "venue-selected estimator",
        re.compile(
            r"(?:must|should|need to|use|uses|re-?estimate|refit|pick|choose|switch to)"
            r"[\s\S]{0,100}(?:heterogeneity-robust|modern staggered|staggered-adoption)"
            r"[\s\S]{0,40}estimator",
            re.IGNORECASE,
        ),
    ),
    (
        "venue TWFE validity rule",
        re.compile(
            r"\bnaive\s+(?:two-way fixed effects|TWFE)\b|"
            r"(?:avoid|outdated|invalid|fatal|not|不能|不得|不回应)[\s\S]{0,45}\bTWFE\b|"
            r"\bTWFE\b[\s\S]{0,80}(?:fatal|reject|no longer accepts|must|cannot|不能|不得|不回应)",
            re.IGNORECASE,
        ),
    ),
    (
        "venue clustering rule",
        re.compile(
            r"cluster(?:ing)?\s+(?:at|below)\s+(?:the\s+)?(?:level\s+of\s+)?"
            r"(?:treatment\s+)?assignment|clustering\s+at\s+the\s+(?:right|wrong|correct)\s+level|"
            r"correct\s+treatment\s+of\s+clustering|proper\s+clustering",
            re.IGNORECASE,
        ),
    ),
    (
        "venue multiplicity or randomization procedure",
        re.compile(
            r"(?:correct|adjust)\s+for\s+multiple\s+(?:comparisons|hypotheses)|"
            r"randomization\s+inference\s+for\s+experiments|"
            r"randomization\s+inference\s*,?\s+not|\bMHT-adjusted\b",
            re.IGNORECASE,
        ),
    ),
    (
        "venue universal measurement threshold",
        re.compile(r"\bAvePP\s*(?:>=|≥|>)\s*0?\.\d+", re.IGNORECASE),
    ),
    (
        "venue current-standard method rule",
        re.compile(
            r"(?:modern\s+estimators?\s+and\s+(?:correct\s+)?inference\s+(?:are|is)\s+baseline|"
            r"inference\s+(?:must\s+use|must\s+match|must\s+be|meets)\s+current\s+standards|"
            r"modern\s+estimators?\s+and\s+correct\s+inference\s+are\s+baseline)",
            re.IGNORECASE,
        ),
    ),
    (
        "venue-selected estimator from outcome",
        re.compile(
            r"(?:use\s+the\s+outcome\s+to\s+pick\s+the\s+estimator|"
            r"estimator\s+choice\s+keyed\s+to\s+the\s+.*outcome)",
            re.IGNORECASE,
        ),
    ),
    (
        "venue-mandated DID repair",
        re.compile(
            r"(?:必须用[\s\S]{0,100}(?:Callaway|Sun.?Abraham)|"
            r"双向固定效应\s*DID\s*必须[\s\S]{0,100}不能只放\s*TWFE|"
            r"(?:交错|多期|分期)\s*DID[\s\S]{0,80}(?:必须|必上|应当|需要)"
            r"[\s\S]{0,90}(?:事件研究|安慰剂|Bacon|\bCS\b|\bSA\b|异质性稳健)|"
            r"识别按本刊红线做满|方法规范底线)",
            re.IGNORECASE,
        ),
    ),
    (
        "venue experiment-design rule",
        re.compile(
            r"preregister\s+(?:the\s+)?design(?:\s+and\s+primary\s+analyses)?|"
            r"(?:report|conduct|perform)\s+(?:an?\s+)?(?:a-priori\s+)?(?:power|MDE)\b|"
            r"pre-?specify\s+(?:primary\s+outcomes|subgroups)|"
            r"address\s+(?:attention|manipulation)[\s\S]{0,80}(?:attrition|balance)",
            re.IGNORECASE,
        ),
    ),
    (
        "venue qualitative-design rule",
        re.compile(
            r"case(?:/site/participant|/site|\s+or\s+site)?\s+selection[\s\S]{0,45}"
            r"justified\s+by\s+design\s+logic|"
            r"process\s+tracing[\s\S]{0,35}(?:with\s+)?explicit\s+tests|"
            r"案例选择[\s\S]{0,30}(?:明确逻辑|典型|极端|关键|最相似|最不同)|"
            r"过程追踪[\s\S]{0,45}(?:箍式检验|冒烟枪检验)",
            re.IGNORECASE,
        ),
    ),
    (
        "venue measurement-validation rule",
        re.compile(
            r"validate\s+(?:(?:any|the)\s+)?(?:computational\s+)?(?:measure|model|classifier|topic model)"
            r"[\s\S]{0,55}human[- ]labeled\s+samples|"
            r"validate\s+against\s+human[- ]labeled\s+samples",
            re.IGNORECASE,
        ),
    ),
    (
        "venue model-selection rule",
        re.compile(
            r"(?:use|fit|prefer)\s+(?:a\s+)?(?:multilevel|HLM|negative binomial|zero-inflated|"
            r"hurdle|Cox|PPML|panel-corrected|Driscoll.?Kraay)[\s\S]{0,65}"
            r"(?:model|estimator|over|rather than)|"
            r"use\s+(?:fixed effects|hybrid models)\s+to\s+isolate",
            re.IGNORECASE,
        ),
    ),
    (
        "venue meta-analysis procedure rule",
        re.compile(
            r"(?:must|should|need(?:s)?\s+to|require(?:s|d)?\s+to|use|fit|run|apply|perform|"
            r"add|choose|select|prefer)\s+(?:an?\s+|the\s+|several\s+|multiple\s+)?"
            r"(?:mixed[- ]effects\s+meta[- ]regression|random[- ]effects\s+(?:internal\s+)?"
            r"meta[- ]analysis|robust\s+variance\s+estimation|RVE\b|multilevel\s+"
            r"meta[- ]analysis|Egger(?:'s)?(?:\s+regression)?|trim[- ]and[- ]fill|PET[- ]PEESE|"
            r"selection\s+models?)|"
            r"dependent\s+effect\s+sizes[\s\S]{0,80}(?:need|must|require|use)"
            r"[\s\S]{0,55}(?:RVE|robust\s+variance|multilevel)|"
            r"diagnostics?\s+to\s+run|run\s+several\s+(?:complementary\s+)?diagnostics",
            re.IGNORECASE,
        ),
    ),
    (
        "venue coder-staffing rule",
        re.compile(
            r"(?:must|should|need(?:s)?\s+to|require(?:s|d)?\s+to|made\s+by|use|employ)"
            r"[\s\S]{0,35}(?:at\s+least\s+)?(?:two|2|\u2265\s*2)\s+(?:trained\s+|independent\s+)?"
            r"(?:coders|screeners)|"
            r"(?:must|should|need(?:s)?\s+to|require(?:s|d)?\s+to|use|perform)"
            r"[\s\S]{0,25}double[- ]cod(?:e|ing)|"
            r"double[- ]cod(?:e|ing)[\s\S]{0,45}(?:by|with)\s*(?:\u2265|>=)?\s*2",
            re.IGNORECASE,
        ),
    ),
    (
        "venue survey-inference rule",
        re.compile(
            r"(?:must|should|need(?:s)?\s+to|require(?:s|d)?\s+to|use|apply)\s+"
            r"design[- ]based\s+inference|"
            r"weights?[\s\S]{0,35}strata[\s\S]{0,35}clusters?[\s\S]{0,45}"
            r"(?:belong\s+in|applied\s+to|required\s+in)\s+(?:the\s+)?variance|"
            r"(?:ignore|ignoring|omitting)\s+(?:survey\s+)?(?:clustering[\s/]?weighting|"
            r"weights?[\s/]?design)|naive\s+IID[\s\S]{0,45}(?:complex|weighted|clustered)\s+"
            r"(?:sample|survey)",
            re.IGNORECASE,
        ),
    ),
    (
        "venue scale-validation rule",
        re.compile(
            r"(?:must|should|need(?:s)?\s+to|require(?:s|d)?\s+to|use|perform|run|fit)?\s*"
            r"validate\s+(?:the\s+|any\s+)?(?:scales?|measures?|latent\s+constructs?)\b|"
            r"(?:must|should|need(?:s)?\s+to|require(?:s|d)?\s+to|use|perform|run|fit)"
            r"\s+(?:an?\s+)?CFA\b|"
            r"standardize\s+(?:the\s+)?experimental\s+setting",
            re.IGNORECASE,
        ),
    ),
    (
        "venue family/event model rule",
        re.compile(
            r"(?:must|should|need(?:s)?\s+to|require(?:s|d)?\s+to|use|fit|run|apply)"
            r"\s+(?:an?\s+|the\s+)?(?:discrete[- ]time\s+hazard|APIM\b|"
            r"actor[- ]partner\s+interdependence\s+model)|"
            r"dyads?/famil(?:y|ies)[\s\S]{0,45}(?:clustered|modeled)[\s\S]{0,35}"
            r"(?:APIM|multilevel)",
            re.IGNORECASE,
        ),
    ),
    (
        "venue-required synthesis exhibit rule",
        re.compile(
            r"(?:this\s+skill|the\s+venue|the\s+pack|Psychological\s+Bulletin)"
            r"[\s\S]{0,45}(?:requires?|must\s+show|expects?)"
            r"[\s\S]{0,140}(?:random[- ]effects|RVE\b|pooled\s+(?:effect|estimate)|"
            r"prediction\s+interval|Egger|selection\s+model|bias\s+diagnostics?)|"
            r"forest\s+plot[\s\S]{0,80}(?:must|requires?|without)[\s\S]{0,55}"
            r"prediction\s+interval|numbers\s+come\s+from\s+(?:the\s+)?analysis\s+skills",
            re.IGNORECASE,
        ),
    ),
    (
        "venue reviewer-requested method rule",
        re.compile(
            r"(?:reviewer[\s\S]{0,45}(?:asks?|wants?|requests?)|only\s+one\s+bias\s+test)"
            r"[\s\S]{0,90}\b(?:add|run|re-?run|fit|apply)\b[\s\S]{0,55}"
            r"(?:diagnostics?|bias\s+tests?|selection\s+model|moderators?|estimates?)",
            re.IGNORECASE,
        ),
    ),
)
def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _walk_keys(value: Any, pointer: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{pointer}/{key}"
            found.append((key, child))
            found.extend(_walk_keys(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_walk_keys(item, f"{pointer}/{index}"))
    return found


def _registered_core_requirement_ids(repo_root: Path) -> set[str]:
    path = repo_root / CORE_METHOD_REQUIREMENTS_RELATIVE
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return set()
    return set(CORE_REQUIREMENT_ID.findall(text))


def _validate_overlay(path: Path, payload: Any, repo_root: Path) -> list[str]:
    relative = _relative(path, repo_root)
    if not isinstance(payload, dict):
        return [f"{relative}: overlay must be a JSON object"]
    issues: list[str] = []
    unexpected = sorted(set(payload) - ALLOWED_OVERLAY_KEYS)
    if unexpected:
        issues.append(f"{relative}: unsupported overlay keys: {', '.join(unexpected)}")
    required = {"schema_version", "journal", "core_method_contract_ref"}
    missing = sorted(required - set(payload))
    if missing:
        issues.append(f"{relative}: missing overlay keys: {', '.join(missing)}")
    if payload.get("schema_version") != OVERLAY_SCHEMA:
        issues.append(f"{relative}: schema_version must be {OVERLAY_SCHEMA}")
    if not isinstance(payload.get("journal"), str) or not payload.get("journal", "").strip():
        issues.append(f"{relative}: journal must be a non-empty string")

    core_ref = payload.get("core_method_contract_ref")
    if not isinstance(core_ref, dict) or set(core_ref) != {"id", "revision"}:
        issues.append(
            f"{relative}: core_method_contract_ref must contain exactly id and revision"
        )
    else:
        contract_id = core_ref.get("id")
        revision = core_ref.get("revision")
        if not isinstance(contract_id, str) or not contract_id.strip():
            issues.append(f"{relative}: core method contract id must be a non-empty string")
        if not isinstance(revision, str) or not revision.strip():
            issues.append(f"{relative}: core method contract revision must be a non-empty string")
        registry_path = repo_root / METHOD_REGISTRY_RELATIVE
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            issues.append(f"{relative}: cannot load core method registry: {error}")
        else:
            contracts = registry.get("method_contracts") if isinstance(registry, dict) else None
            specification = (
                contracts.get(contract_id)
                if isinstance(contracts, dict) and isinstance(contract_id, str)
                else None
            )
            if not isinstance(specification, dict):
                issues.append(
                    f"{relative}: unregistered core method contract id {contract_id!r}"
                )
            else:
                if specification.get("revision") != revision:
                    issues.append(
                        f"{relative}: core method contract revision mismatch for {contract_id!r}"
                    )
                asset = specification.get("asset")
                target = (
                    repo_root / "skills" / "empirical-research" / str(asset)
                ).resolve()
                empirical_root = (
                    repo_root / "skills" / "empirical-research"
                ).resolve()
                try:
                    target.relative_to(empirical_root)
                except ValueError:
                    issues.append(
                        f"{relative}: registered core method contract asset escapes empirical-research"
                    )
                else:
                    if not target.is_file():
                        issues.append(
                            f"{relative}: registered core method contract asset is missing: {asset}"
                        )

    for key, pointer in _walk_keys(payload):
        if pointer.count("/") > 1 and key in RESERVED_METHOD_KEYS:
            issues.append(f"{relative}: reserved core method key at {pointer}")
    return issues


def _discover_workflows(packs_root: Path, repo_root: Path) -> list[str]:
    return sorted(
        _relative(path, repo_root)
        for path in packs_root.rglob("SKILL.md")
        if path.parent.name.lower().endswith("workflow")
    )


def validate_venue_overlay_registry(repo_root: Path = ROOT) -> list[str]:
    repo_root = repo_root.resolve()
    packs_root = (repo_root / PACKS_RELATIVE).resolve()
    registry_path = repo_root / VENUE_REGISTRY_RELATIVE
    relative = VENUE_REGISTRY_RELATIVE.as_posix()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [f"{relative}: cannot load venue overlay registry: {error}"]
    issues: list[str] = []
    if payload.get("schema_version") != "avereth-venue-overlay-registry/v1":
        issues.append(f"{relative}: unsupported schema_version")
    if payload.get("workspace_control_plane") != "cnki-paper":
        issues.append(f"{relative}: workspace_control_plane must be cnki-paper")
    method_authority = payload.get("method_contract_authority")
    if method_authority != "skills/empirical-research/references/method-adapter-registry.json":
        issues.append(f"{relative}: method_contract_authority must reference the core registry")
    elif not (repo_root / method_authority).is_file():
        issues.append(f"{relative}: missing core method registry")
    registered = payload.get("workflow_overlays")
    if not isinstance(registered, list) or not all(isinstance(item, str) for item in registered):
        issues.append(f"{relative}: workflow_overlays must be a string array")
        registered = []
    discovered = _discover_workflows(packs_root, repo_root) if packs_root.is_dir() else []
    if len(set(registered)) != len(registered):
        issues.append(f"{relative}: duplicate workflow overlay paths")
    if sorted(registered) != discovered:
        missing = sorted(set(discovered) - set(registered))
        stale = sorted(set(registered) - set(discovered))
        if missing:
            issues.append(f"{relative}: unregistered workflow overlays: {', '.join(missing)}")
        if stale:
            issues.append(f"{relative}: stale workflow overlay paths: {', '.join(stale)}")
    expected_forbidden = {
        "next_stage",
        "completed_stage",
        "status",
        "gate",
        "receipt",
        "method_override",
        "execution_engine",
    }
    if set(payload.get("forbidden_workflow_fields") or []) != expected_forbidden:
        issues.append(f"{relative}: forbidden_workflow_fields drifted")
    for workflow in discovered:
        path = repo_root / workflow
        text = path.read_text(encoding="utf-8")
        match = STRUCTURED_DEFINITION.search(text)
        if match and match.group(1) in expected_forbidden:
            issues.append(f"{workflow}: workflow owns forbidden field {match.group(1)}")
        if DIRECT_ENGINE.search(text):
            issues.append(f"{workflow}: venue workflow directly invokes a method engine")
    return issues


def _repository_boundary_issues(repo_root: Path) -> list[str]:
    issues = validate_venue_overlay_registry(repo_root)
    root_skill = repo_root / JOURNAL_SKILL_RELATIVE
    try:
        root_text = root_skill.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        issues.append(f"{JOURNAL_SKILL_RELATIVE.as_posix()}: cannot inspect root skill: {error}")
    else:
        if re.search(r"\bV4\b", root_text):
            issues.append(f"{JOURNAL_SKILL_RELATIVE.as_posix()}: stale V4 control-plane reference")
        if "venue overlay 不拥有工作区状态" not in root_text:
            issues.append(f"{JOURNAL_SKILL_RELATIVE.as_posix()}: missing venue-overlay control boundary")
    apsr_root = repo_root / "skills" / "journal-fit" / "packs" / "apsr"
    if apsr_root.is_dir():
        for path in sorted(apsr_root.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            match = APSR_CONTROL_RISK.search(text)
            if match:
                issues.append(
                    f"{_relative(path, repo_root)}: APSR venue overlay contains control risk {match.group(0)}"
                )
    return issues


def validate_journal_overlays(
    repo_root: Path = ROOT,
    *,
    check_repository_boundaries: bool = True,
) -> list[str]:
    """Return deterministic policy violations for all checked-in journal packs."""

    repo_root = repo_root.resolve()
    packs_root = (repo_root / PACKS_RELATIVE).resolve()
    if not packs_root.is_dir():
        return [f"missing journal packs directory: {PACKS_RELATIVE.as_posix()}"]

    issues: list[str] = []
    registered_core_requirements = _registered_core_requirement_ids(repo_root)
    for directory in sorted((item for item in packs_root.rglob("*") if item.is_dir())):
        if directory.name.lower() in FORBIDDEN_DIRECTORY_NAMES:
            issues.append(
                f"{_relative(directory, repo_root)}: journal packs may not own method {directory.name.lower()}"
            )

    for path in sorted(item for item in packs_root.rglob("*") if item.is_file()):
        relative = _relative(path, repo_root)
        lower_name = path.name.lower()
        if lower_name.endswith(".schema.json"):
            issues.append(f"{relative}: journal pack may not define a method schema")
            continue
        if path.suffix.lower() == ".py" and FORBIDDEN_CODE_NAME.search(path.stem):
            issues.append(f"{relative}: journal pack may not define a method validator or registry")
            continue

        if lower_name == OVERLAY_FILENAME:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                issues.append(f"{relative}: invalid overlay JSON: {error}")
            else:
                issues.extend(_validate_overlay(path, payload, repo_root))
            continue

        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            for key, pointer in _walk_keys(payload):
                if key in RESERVED_METHOD_KEYS:
                    issues.append(f"{relative}: reserved core method key at {pointer}")
        elif path.suffix.lower() in {".md", ".yaml", ".yml", ".toml"}:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                issues.append(f"{relative}: cannot inspect text: {error}")
                continue
            match = STRUCTURED_DEFINITION.search(text)
            if match:
                issues.append(
                    f"{relative}: structured definition of reserved core method key {match.group(1)}"
                )
            engine_match = DIRECT_ENGINE.search(text)
            if engine_match:
                issues.append(
                    f"{relative}: venue content directly invokes a method engine via {engine_match.group(0)}"
                )
            if (
                lower_name == "external_tools.md"
                and METHOD_TOOL_CATALOG_SIGNAL.search(text)
                and not METHOD_TOOL_CATALOG_BOUNDARY.search(text)
            ):
                issues.append(
                    f"{relative}: method-tool catalog lacks an empirical-core selection boundary"
                )
            for label, pattern in VENUE_METHOD_AUTHORITY_PATTERNS:
                authority_match = pattern.search(text)
                if authority_match:
                    excerpt = " ".join(authority_match.group(0).split())[:160]
                    issues.append(
                        f"{relative}: venue content restates core method authority ({label}) via {excerpt}"
                    )
            for requirement_id in sorted(set(CORE_REQUIREMENT_ID.findall(text))):
                if requirement_id not in registered_core_requirements:
                    issues.append(
                        f"{relative}: unknown empirical core requirement reference {requirement_id}"
                    )
    if check_repository_boundaries:
        issues.extend(_repository_boundary_issues(repo_root))
    return sorted(set(issues))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    args = parser.parse_args()
    issues = validate_journal_overlays(args.root)
    encoding = sys.stdout.encoding or "utf-8"

    def console(text: str) -> None:
        print(text.encode(encoding, errors="replace").decode(encoding))

    if issues:
        console("Journal overlay check: FAIL")
        for issue in issues:
            console(f"- {issue}")
        return 1
    console("Journal overlay check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
