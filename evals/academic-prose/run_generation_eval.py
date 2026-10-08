#!/usr/bin/env python3
"""Explanation-first prose generation eval with optional live blind review.

The offline path is deterministic. It verifies the writer-safe packet, literal
fidelity, reviewer isolation, an evidence-bounded clarity ledger, and the seven
behavioral cases in the corpus. It does not claim to prove semantic equivalence:
bidirectional semantic fidelity remains an isolated live-review judgment.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SCRIPTS = REPO_ROOT / "skills" / "cnki-paper" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from prose_packet import (  # noqa: E402
    CLARITY_LEDGER_SCHEMA_VERSION,
    ProsePacketError,
    check_clarity,
    compile_prose_packet,
    prose_units,
    validate_draft_fidelity,
)


CORPUS_PATH = HERE / "defensive_corpus.json"
CORPUS_SCHEMA = "avereth-explanation-first-corpus/v2"
OFFLINE_REPORT_SCHEMA = "avereth-explanation-generation-eval/v2"
LIVE_REPORT_SCHEMA = "avereth-explanation-live-blind/v2"

REVIEW_PROCESS_LEAK_RE = re.compile(
    r"(?:审稿人|评审意见|审稿意见|回复信|修改稿|为回应|针对上述意见|"
    r"reviewer|response\s+letter|comment[- ]by[- ]comment)",
    re.IGNORECASE,
)
PATCH_SEAM_RE = re.compile(
    r"(?:(?:最强的?)?(?:质疑|反对意见)(?:认为|是).{0,80}"
    r"(?:这一质疑|尽管|但本文|仍然)|"
    r"(?:需要|有必要)(?:进一步|特别)?(?:说明|澄清).{0,80}"
    r"(?:尽管|但是|但本文|仍))",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:[.,]\d+)*(?:%|％)?")
CITATION_RE = re.compile(r"\\cite\{([^{}]+)\}")


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != CORPUS_SCHEMA:
        raise ValueError(f"unsupported explanation-first corpus schema: {payload.get('schema_version')}")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("explanation-first corpus has no cases")
    seen: set[str] = set()
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"case {index} must be an object")
        case_id = str(case.get("id") or "").strip()
        if not case_id or case_id in seen:
            raise ValueError(f"case {index} needs a unique id")
        seen.add(case_id)
        if case.get("expected") not in {"pass", "reject"}:
            raise ValueError(f"case {case_id} has unsupported expected value")
        if not isinstance(case.get("registered_ids"), list):
            raise ValueError(f"case {case_id} must list registered_ids")
        if not isinstance(case.get("request"), dict):
            raise ValueError(f"case {case_id} must contain a packet request")
    return payload


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def _sentence(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text[-1] in "。！？.!?；;" else text + "。"


def _append_unique(sentences: list[str], value: Any) -> None:
    sentence = _sentence(value)
    if not sentence:
        return
    normalized = _compact(sentence.rstrip("。！？.!?；;"))
    if normalized and any(normalized == _compact(item.rstrip("。！？.!?；;")) for item in sentences):
        return
    sentences.append(sentence)


def _reserved_sources(case: dict[str, Any]) -> tuple[set[int], bool]:
    orders: set[int] = set()
    reserve_warrant = False
    for action in case.get("clarity_plan") or []:
        if not isinstance(action, dict) or str(action.get("action") or "").upper() not in {
            "BRIDGE",
            "DEFINE",
        }:
            continue
        kind = str(action.get("source_kind") or "").lower()
        anchor = str(action.get("source_anchor") or "")
        if kind == "warrant" and anchor == "warrant":
            reserve_warrant = True
        match = re.fullmatch(r"explanation_path:(\d+)", anchor)
        if kind == "explanation_path" and match:
            orders.add(int(match.group(1)))
    return orders, reserve_warrant


def _render_evidence(item: dict[str, Any]) -> str:
    text = str(item.get("text") or "").strip().rstrip("。.!?")
    traces: list[str] = []
    if item.get("locator"):
        traces.append(str(item["locator"]).strip())
    if item.get("citation_key"):
        traces.append(r"\cite{" + str(item["citation_key"]).strip() + "}")
    if traces:
        text += "（" + "；".join(traces) + "）"
    return _sentence(text)


def fixture_writer(packet: dict[str, Any], case: dict[str, Any] | None = None) -> str:
    """Render packet-authorized prose without copying semantic claim wording.

    In semantic mode `plain_core` supplies the affirmative realization. In
    verbatim and legacy modes the exact canonical proposition remains protected.
    Explanation steps reserved for a ledgered BRIDGE/DEFINE are intentionally
    left for the clarity fixture.
    """

    case = case or {}
    claim = packet.get("claim") if isinstance(packet.get("claim"), dict) else {}
    mode = str(claim.get("realization_mode") or "legacy_exact").lower()
    opening = (
        claim.get("canonical_proposition") or claim.get("text")
        if mode in {"verbatim", "legacy_exact"}
        else packet.get("plain_core")
    )
    sentences: list[str] = []
    _append_unique(sentences, opening)

    for item in packet.get("evidence_items", []):
        if isinstance(item, dict):
            _append_unique(sentences, _render_evidence(item))

    reserved_orders, reserve_warrant = _reserved_sources(case)
    for step in sorted(
        (item for item in packet.get("explanation_path", []) if isinstance(item, dict)),
        key=lambda item: int(item.get("step", item.get("order")) or 0),
    ):
        order = int(step.get("step", step.get("order")) or 0)
        function = str(step.get("function") or "").lower()
        if order in reserved_orders or function in {"claim", "evidence", "reader_update"}:
            continue
        if function == "warrant" and reserve_warrant:
            continue
        _append_unique(sentences, step.get("content"))

    for countervoice in packet.get("material_countervoices", []):
        if not isinstance(countervoice, dict):
            continue
        position = str(countervoice.get("position") or "").strip().rstrip("。.!?")
        evidence = str(countervoice.get("discriminating_evidence") or "").strip().rstrip("。.!?")
        if position:
            _append_unique(sentences, position + ("；" + evidence if evidence else ""))

    _append_unique(sentences, packet.get("reader_update"))
    for boundary in packet.get("required_boundaries", []):
        if not isinstance(boundary, dict):
            continue
        statement = str(boundary.get("statement") or "").strip()
        if statement:
            _append_unique(sentences, statement)
    return "".join(sentences)


def _insert_before_reader_update(packet: dict[str, Any], draft: str, addition: str) -> str:
    marker = _sentence(packet.get("reader_update"))
    index = draft.find(marker) if marker else -1
    if index < 0:
        boundary_positions = [
            draft.find(_sentence(item.get("statement")))
            for item in packet.get("required_boundaries", [])
            if isinstance(item, dict) and item.get("statement")
        ]
        valid = [position for position in boundary_positions if position >= 0]
        index = min(valid) if valid else len(draft)
    return draft[:index] + _sentence(addition) + draft[index:]


def fixture_clarity_editor(
    packet: dict[str, Any], writer_draft: str, case: dict[str, Any] | None = None
) -> tuple[str, dict[str, Any]]:
    """Apply only corpus-declared clarity actions and emit a canonical ledger."""

    case = case or {}
    current = writer_draft
    records: list[dict[str, Any]] = []
    claim_id = str((packet.get("claim") or {}).get("id") or "")
    for plan in case.get("clarity_plan") or []:
        if not isinstance(plan, dict):
            continue
        action = str(plan.get("action") or "").upper()
        before = current
        if action in {"BRIDGE", "DEFINE"}:
            current = _insert_before_reader_update(packet, current, str(plan.get("content") or ""))
        elif action == "DELETE":
            current = current.replace(str(plan.get("target") or ""), "", 1)
        elif action == "REPLACE":
            current = current.replace(
                str(plan.get("target") or ""), str(plan.get("replacement") or ""), 1
            )
        elif action == "MOVE":
            target = str(plan.get("target") or "")
            marker = str(plan.get("before") or "")
            if target and marker and target in current and marker in current:
                current = current.replace(target, "", 1)
                current = current.replace(marker, target + marker, 1)
        delta = prose_units(current) - prose_units(before)
        record: dict[str, Any] = {"action": action, "prose_delta": delta}
        if action in {"BRIDGE", "DEFINE"}:
            record.update(
                {
                    "claim_id": claim_id,
                    "source_kind": str(plan.get("source_kind") or ""),
                    "source_anchor": str(plan.get("source_anchor") or ""),
                    "reader_understanding": str(plan.get("reader_understanding") or ""),
                    "no_new_fact": True,
                    "no_new_citation": True,
                    "no_inference_strengthening": True,
                }
            )
        records.append(record)
    return current, {
        "schema_version": CLARITY_LEDGER_SCHEMA_VERSION,
        "scope": str(case.get("clarity_scope") or "paragraph"),
        "actions": records,
    }


def _new_numbers(before: str, after: str) -> set[str]:
    return set(NUMBER_RE.findall(after)) - set(NUMBER_RE.findall(before))


def _new_citations(before: str, after: str) -> set[str]:
    def keys(text: str) -> set[str]:
        return {
            key.strip()
            for group in CITATION_RE.findall(text)
            for key in group.split(",")
            if key.strip()
        }

    return keys(after) - keys(before)


def _substantive_explanation_present(packet: dict[str, Any], candidate: str) -> bool:
    candidates = [
        str(step.get("content") or "")
        for step in packet.get("explanation_path", [])
        if isinstance(step, dict)
        and str(step.get("function") or "").lower() in {"mechanism", "process", "warrant"}
    ]
    return any(_compact(content) in _compact(candidate) for content in candidates if content.strip())


def _contract_issues(
    case: dict[str, Any],
    packet: dict[str, Any],
    writer_draft: str,
    candidate: str,
    clarity_result: Any,
    ledger: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    compact_candidate = _compact(candidate)
    for fragment in case.get("required_text") or []:
        if _compact(fragment) not in compact_candidate:
            issues.append(f"candidate loses required text: {fragment}")
    for fragment in case.get("forbidden_text") or []:
        if _compact(fragment) in compact_candidate:
            issues.append(f"candidate contains forbidden text: {fragment}")
    for marker in case.get("required_polarity_markers") or []:
        if _compact(marker) not in compact_candidate:
            issues.append(f"candidate loses required polarity marker: {marker}")
    scope = str(case.get("required_scope_text") or "")
    if scope and _compact(scope) not in compact_candidate:
        issues.append(f"candidate loses required positive scope: {scope}")

    claim_text = str((packet.get("claim") or {}).get("canonical_proposition") or "")
    if case.get("expect_exact_claim_absent") is True and _compact(claim_text) in compact_candidate:
        issues.append("semantic candidate copied the defensive canonical claim verbatim")
    if case.get("expect_exact_claim_present") is True and _compact(claim_text) not in compact_candidate:
        issues.append("verbatim candidate lost the exact canonical claim")

    if REVIEW_PROCESS_LEAK_RE.search(candidate):
        issues.append("candidate leaks explicit reviewer or revision process language")
    if PATCH_SEAM_RE.search(candidate):
        issues.append("candidate retains a structural reviewer-response patch seam")

    if str((packet.get("claim") or {}).get("realization_mode") or "") == "semantic":
        if not _substantive_explanation_present(packet, candidate):
            issues.append("semantic candidate does not realize a packet mechanism/process/warrant")
        if not packet.get("evidence_items") or not any(
            _compact(item.get("text")) in compact_candidate
            for item in packet.get("evidence_items", [])
            if isinstance(item, dict)
        ):
            issues.append("semantic candidate does not anchor its explanation in selected evidence")

    boundary_id = str(case.get("expected_boundary_id") or "")
    boundary_text = str(case.get("expected_boundary_text") or "")
    if boundary_id:
        matching = [
            item
            for item in packet.get("required_boundaries", [])
            if isinstance(item, dict) and str(item.get("id") or "") == boundary_id
        ]
        if len(matching) != 1:
            issues.append(f"packet does not contain exactly one {boundary_id} boundary")
    if boundary_text:
        if candidate.count(boundary_text) != 1:
            issues.append("full positive-scope boundary must appear exactly once")
        opening = str(packet.get("plain_core") or claim_text)
        if candidate.find(boundary_text) >= 0 and candidate.find(opening) >= 0:
            if candidate.find(boundary_text) < candidate.find(opening):
                issues.append("full boundary appears before the claim")

    actual_actions = [str(item.get("action") or "") for item in ledger.get("actions", [])]
    expected_actions = [str(item) for item in case.get("expected_clarity_actions") or []]
    if actual_actions != expected_actions:
        issues.append(
            f"clarity actions drift: expected {expected_actions}, observed {actual_actions}"
        )
    if case.get("expect_positive_growth") is True and clarity_result.delta <= 0:
        issues.append("case requires a positive evidence-bounded clarity delta")
    if case.get("expect_positive_growth") is False and clarity_result.delta > 0:
        issues.append("case produced unrequested positive prose growth")
    if clarity_result.delta > 0:
        new_numbers = _new_numbers(writer_draft, candidate)
        new_citations = _new_citations(writer_draft, candidate)
        if new_numbers:
            issues.append("clarity edit introduces new number(s): " + ", ".join(sorted(new_numbers)))
        if new_citations:
            issues.append(
                "clarity edit introduces new citation-like anchor(s): "
                + ", ".join(sorted(new_citations))
            )
        if any(
            int(item.get("prose_delta") or 0) > 0
            and str(item.get("action") or "") not in {"BRIDGE", "DEFINE"}
            for item in ledger.get("actions", [])
            if isinstance(item, dict)
        ):
            issues.append("non-BRIDGE/DEFINE clarity action records positive growth")
    return issues


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case.get("id") or "<missing>")
    expected = str(case.get("expected") or "")
    registered_ids = case.get("registered_ids") or []
    try:
        packet = compile_prose_packet(case.get("request"), registered_ids=registered_ids)
    except ProsePacketError as exc:
        passed = expected == "reject"
        return {
            "id": case_id,
            "behavior": case.get("behavior"),
            "status": "PASS" if passed else "FAIL",
            "result": "rejected",
            "detail": str(exc),
            "issues": [] if passed else [str(exc)],
        }
    if expected == "reject":
        return {
            "id": case_id,
            "behavior": case.get("behavior"),
            "status": "FAIL",
            "result": "compiled",
            "issues": ["expected packet rejection but request compiled"],
        }

    issues: list[str] = []
    probe_key = str(case.get("firewall_probe_key") or "")
    if probe_key:
        probe = copy.deepcopy(case["request"])
        probe[probe_key] = "审稿人认为机制解释不足"
        try:
            compile_prose_packet(probe, registered_ids=registered_ids)
        except ProsePacketError:
            pass
        else:
            issues.append("reviewer-control firewall probe unexpectedly compiled")

    writer_draft = fixture_writer(packet, case)
    writer_issues = validate_draft_fidelity(packet, writer_draft, registered_ids=registered_ids)
    issues.extend(f"writer fidelity: {item}" for item in writer_issues)
    candidate, ledger = fixture_clarity_editor(packet, writer_draft, case)
    clarity_result = check_clarity(
        packet,
        writer_draft,
        candidate,
        ledger,
        registered_ids=registered_ids,
    )
    issues.extend(f"clarity gate: {item}" for item in clarity_result.issues)
    issues.extend(
        _contract_issues(case, packet, writer_draft, candidate, clarity_result, ledger)
    )
    baseline = str(case.get("baseline") or "")
    return {
        "id": case_id,
        "behavior": case.get("behavior"),
        "status": "FAIL" if issues else "PASS",
        "result": "compiled",
        "packet_mode": (packet.get("claim") or {}).get("realization_mode"),
        "writer_draft": writer_draft,
        "candidate": candidate,
        "clarity_ledger": ledger,
        "clarity_delta": clarity_result.delta,
        "clarity_growth_ratio": clarity_result.growth_ratio,
        "clarity_warnings": list(clarity_result.warnings),
        "baseline_candidate_delta": prose_units(candidate) - prose_units(baseline),
        "issues": issues,
        "packet": packet,
    }


def run_offline_evaluation(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    corpus = payload or load_corpus()
    results = [evaluate_case(case) for case in corpus["cases"]]
    failures = [result["id"] for result in results if result["status"] != "PASS"]
    return {
        "schema_version": OFFLINE_REPORT_SCHEMA,
        "mode": "offline-deterministic-contract",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "controller_effect": "none",
        "semantic_assurance": "literal-and-structural-only; live blind review required",
        "behaviors_exercised": sorted(
            {str(result.get("behavior") or "") for result in results if result.get("behavior")}
        ),
        "results": results,
    }


def _response_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                parts.append(str(content.get("text") or ""))
    return "\n".join(parts).strip()


def _responses_call(api_key: str, model: str, prompt: str) -> str:
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps({"model": model, "input": prompt}).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"live blind API call failed: {exc}") from exc
    text = _response_text(payload)
    if not text:
        raise RuntimeError("live blind API response contained no output_text")
    return text


def _writer_safe_contract(packet: dict[str, Any]) -> dict[str, Any]:
    claim = packet.get("claim") if isinstance(packet.get("claim"), dict) else {}
    return {
        "canonical_proposition": claim.get("canonical_proposition") or claim.get("text"),
        "realization_mode": claim.get("realization_mode"),
        "protected_atoms": claim.get("protected_atoms"),
        "selected_evidence": [
            {
                key: item.get(key)
                for key in ("text", "locator", "citation_key", "evidence_function")
                if item.get(key) is not None
            }
            for item in packet.get("evidence_items", [])
            if isinstance(item, dict)
        ],
        "warrant": packet.get("warrant"),
        "reader_question": packet.get("reader_question"),
        "reader_update": packet.get("reader_update"),
        "boundaries": [
            {
                "preferred_realization": item.get("preferred_realization"),
                "statement": item.get("statement"),
                "claim_delta": item.get("claim_delta"),
            }
            for item in packet.get("required_boundaries", [])
            if isinstance(item, dict)
        ],
    }


def run_live_blind(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("AVERETH_EVAL_MODEL", "").strip()
    review_model = os.environ.get("AVERETH_EVAL_REVIEW_MODEL", "").strip() or model
    if not api_key or not model:
        return {
            "schema_version": LIVE_REPORT_SCHEMA,
            "mode": "credentialed-live-blind",
            "status": "SKIP",
            "reason": "OPENAI_API_KEY and AVERETH_EVAL_MODEL are both required",
        }
    corpus = payload or load_corpus()
    reviews: list[dict[str, Any]] = []
    for case in corpus["cases"]:
        if case.get("expected") != "pass":
            continue
        packet = compile_prose_packet(
            case["request"], registered_ids=case.get("registered_ids") or []
        )
        generation_prompt = (
            "Write one publication-ready Chinese academic prose unit from the writer-safe packet below. "
            "Preserve the canonical proposition, protected literals, polarity, direction, inferential strength, "
            "scope, numbers, citations, and activated boundaries. In semantic mode, do not copy defensive claim "
            "framing: explain the object, mechanism or warrant, evidence role, and reader update in a continuous "
            "research order. Preserve verbatim material exactly. Do not mention reviews, revisions, workflow, audits, "
            "or the packet. Return only manuscript prose.\n\n"
            + json.dumps(packet, ensure_ascii=False, indent=2)
        )
        candidate = _responses_call(api_key, model, generation_prompt)
        deterministic_issues = validate_draft_fidelity(
            packet, candidate, registered_ids=case.get("registered_ids") or []
        )
        baseline = str(case.get("baseline") or "")
        candidate_first = int(hashlib.sha256(case["id"].encode("utf-8")).hexdigest(), 16) % 2 == 0
        option_a, option_b = (candidate, baseline) if candidate_first else (baseline, candidate)
        contract = _writer_safe_contract(packet)
        review_prompt = (
            "You are an isolated blind academic-prose reviewer. A and B are anonymous. The writer-safe semantic "
            "contract states the proposition and evidence limits, but it does not identify a preferred answer. "
            "Judge bidirectional semantic fidelity, substantive explanation, and revision cleanliness/clean-read. "
            "For clean-read, ask whether a reader can explain the prose from research logic alone and whether any "
            "sentence or sequence only makes sense as a patch to an unseen comment. Do not infer production history, "
            "reward novelty, count negative words, or prefer shorter text automatically. Return JSON only with keys "
            "preferred (A, B, TIE, or BOTH_FAIL), semantic_fidelity (PASS or FAIL), "
            "substantive_explanation (PASS or FAIL), revision_cleanliness (PASS or FAIL), and reason.\n\n"
            "Writer-safe semantic contract:\n"
            + json.dumps(contract, ensure_ascii=False, indent=2)
            + "\n\nA:\n"
            + option_a
            + "\n\nB:\n"
            + option_b
        )
        raw_review = _responses_call(api_key, review_model, review_prompt)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_review.strip(), flags=re.IGNORECASE)
        try:
            review = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"blind reviewer returned invalid JSON for {case['id']}") from exc
        preferred = str(review.get("preferred") or "").upper()
        if preferred not in {"A", "B", "TIE", "BOTH_FAIL"}:
            raise RuntimeError(f"blind reviewer returned invalid preference for {case['id']}")
        preferred_variant = "tie" if preferred == "TIE" else "both_fail"
        if preferred in {"A", "B"}:
            preferred_variant = "candidate" if (preferred == "A") == candidate_first else "baseline"
        dimension_values = {
            key: str(review.get(key) or "").upper()
            for key in (
                "semantic_fidelity",
                "substantive_explanation",
                "revision_cleanliness",
            )
        }
        if any(value not in {"PASS", "FAIL"} for value in dimension_values.values()):
            raise RuntimeError(f"blind reviewer returned invalid dimension verdict for {case['id']}")
        reviews.append(
            {
                "case_id": case["id"],
                "preferred_variant": preferred_variant,
                **dimension_values,
                "reason": review.get("reason"),
                "deterministic_fidelity": "FAIL" if deterministic_issues else "PASS",
                "deterministic_issues": deterministic_issues,
            }
        )
    manual_review = any(
        item["preferred_variant"] != "candidate"
        or item["semantic_fidelity"] != "PASS"
        or item["substantive_explanation"] != "PASS"
        or item["revision_cleanliness"] != "PASS"
        or item["deterministic_fidelity"] != "PASS"
        for item in reviews
    )
    return {
        "schema_version": LIVE_REPORT_SCHEMA,
        "mode": "credentialed-live-blind",
        "status": "REVIEW_REQUIRED" if manual_review else "EVIDENCE_READY",
        "controller_effect": "none",
        "reviews": reviews,
    }


def exit_code_for_report(report: dict[str, Any], *, live_blind: bool) -> int:
    status = str(report.get("status") or "")
    if status == "FAIL":
        return 1
    if live_blind and status not in {"EVIDENCE_READY", "SKIP"}:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    parser.add_argument("--live-blind", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    corpus = load_corpus(args.corpus)
    report = run_live_blind(corpus) if args.live_blind else run_offline_evaluation(corpus)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return exit_code_for_report(report, live_blind=args.live_blind)


if __name__ == "__main__":
    raise SystemExit(main())
