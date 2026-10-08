"""Read-only delegation contracts subordinate to the existing controller.

Discovery candidates are never source facts. The request's control envelope stays
with the primary agent; only public_task may enter the public search context.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import ipaddress
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from ..config import LEGACY_CONFIG_REL, WORKFLOW_CONFIG_REL

REQUEST_SCHEMA = "avereth-delegation-request/v1"
BRIEF_SCHEMA = "avereth-discovery-brief/v1"
RESULT_SCHEMA = "avereth-discovery-candidates/v1"
PUBLIC_TOOLS = frozenset({"exa.search", "web.search"})
DEFAULT_POLICY = {"scout_enabled": False, "max_active": 3, "max_tool_retries": 1,
                  "max_queries_per_task": 4, "max_candidates": 12}
# Missing authorities are also bound so creation invalidates an outstanding task.
CONTROL_INPUTS = (WORKFLOW_CONFIG_REL.as_posix(), LEGACY_CONFIG_REL.as_posix(),
                  "problem_orientation.md", "literature_registry.json",
                  "literature_analysis.json", "research_material_registry.json",
                  "research_feasibility.json", "confirmed_motivation.md",
                  "research_design.json", "method_execution.json")
_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def delegation_policy(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("delegation_policy", {})
    if not isinstance(raw, dict) or set(raw) - set(DEFAULT_POLICY):
        raise ValueError("delegation_policy contains unsupported fields")
    policy = {**DEFAULT_POLICY, **raw}
    if type(policy["scout_enabled"]) is not bool:
        raise ValueError("delegation_policy.scout_enabled must be boolean")
    for key, ceiling in (("max_active", 3), ("max_tool_retries", 1),
                         ("max_queries_per_task", 8), ("max_candidates", 30)):
        value = policy[key]
        minimum = 0 if key == "max_tool_retries" else 1
        if type(value) is not int or not minimum <= value <= ceiling:
            raise ValueError(f"delegation_policy.{key} must be {minimum}..{ceiling}")
    return policy


def _text(value: Any, field: str, maximum: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{field} must be nonempty text of at most {maximum} characters")
    return value.strip()


def _inside(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or ":" in relative:
        raise ValueError("discovery paths must be workspace-relative")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("discovery path escapes the workspace")
    return resolved


def _sha(path: Path) -> str | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"discovery input is not a file: {path.name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_discovery_context(outdir: Path, relative: str) -> dict[str, Any]:
    path = _inside(outdir, relative)
    raw = path.read_bytes()
    if len(raw) > 128 * 1024:
        raise ValueError("discovery brief exceeds 128 KiB")
    brief = json.loads(raw.decode("utf-8-sig"))
    return {"brief": brief, "input_artifact": {
        "path": Path(relative).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(),
        "read_scope": "entire public discovery brief"},
        "authority_hashes": {name: _sha(_inside(outdir, name)) for name in CONTROL_INPUTS}}


def _partitions(brief: Any, policy: dict[str, Any]) -> list[dict[str, Any]]:
    fields = {"schema_version", "public_query_authorized", "question", "partitions"}
    if not isinstance(brief, dict) or set(brief) != fields or brief["schema_version"] != BRIEF_SCHEMA:
        raise ValueError("invalid avereth-discovery-brief/v1")
    if brief["public_query_authorized"] is not True:
        raise ValueError("public search terms require primary-thread authorization")
    question = _text(brief["question"], "question")
    partitions = brief["partitions"]
    if not isinstance(partitions, list) or not 1 <= len(partitions) <= 32:
        raise ValueError("discovery brief requires 1..32 problem partitions")
    ids: set[str] = set()
    queries: set[str] = set()
    result = []
    for partition in partitions:
        if not isinstance(partition, dict) or set(partition) != {"id", "objective", "purpose", "queries", "tool"}:
            raise ValueError("invalid discovery partition fields")
        identifier = partition["id"]
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier) or identifier in ids:
            raise ValueError("discovery partition ids must be unique lowercase slugs")
        ids.add(identifier)
        if not isinstance(partition["purpose"], str) or partition["purpose"] not in {
                "nearest_neighbor", "counterevidence", "coverage_gap"}:
            raise ValueError("partition purpose must identify a problem/evidence gap")
        if not isinstance(partition["tool"], str) or partition["tool"] not in PUBLIC_TOOLS:
            raise ValueError("Scout may use only approved public search adapters")
        items = partition["queries"]
        if not isinstance(items, list) or not 1 <= len(items) <= policy["max_queries_per_task"]:
            raise ValueError("partition exceeds query budget")
        normalized = []
        for item in items:
            query = _text(item, "query", 500)
            key = " ".join(query.casefold().split())
            if key in queries:
                raise ValueError("duplicate search query across discovery partitions")
            queries.add(key)
            normalized.append(query)
        result.append({"question": question, "partition_id": identifier,
                       "objective": _text(partition["objective"], "objective"),
                       "purpose": partition["purpose"], "queries": normalized,
                       "tool": partition["tool"]})
    return result


def project_delegation(plan: dict[str, Any], config: dict[str, Any],
                       protocol: dict[str, Any] | None = None,
                       context: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = delegation_policy(config)
    view: dict[str, Any] = {"delegation_requests": [], "delegation_decisions": [],
                           "delegation_limits": {**policy, "recursive_dispatch": False,
                            "insufficient_resources": "serialize_independent_contexts_or_return_to_primary"}}
    stage = plan["next_stage"]
    if stage in {"complete", "blocked"} or plan["user_decision_required"]:
        view["delegation_decisions"].append({"role": "all", "delegate": False,
                                            "reason": "controller checkpoint owns the next action"})
        return view
    if stage == "execution" and plan.get("granularity") == "operation":
        # The existing risk router owns the entire decision, including run count.
        if protocol and protocol.get("valid"):
            for item in plan.get("work_items", []):
                dispatch = item.get("researcher_dispatch")
                if not item.get("runnable") or not isinstance(dispatch, dict):
                    continue
                if dispatch.get("mode") != "isolated_multi":
                    view["delegation_decisions"].append({"role": "avereth_researcher", "delegate": False,
                        "action": item["id"], "reason": "existing researcher_dispatch selected single"})
                    continue
                view["delegation_requests"].append({
                    "schema_version": REQUEST_SCHEMA, "request_id": "research-" + digest(item),
                    "stage": stage, "action": item["id"], "role": "avereth_researcher",
                    "reason": "existing researcher_dispatch requires isolated runs",
                    "researcher_dispatch_ref": f"work_items/{item['id']}/researcher_dispatch",
                    "researcher_dispatch": deepcopy(dispatch),
                    "input_artifacts": deepcopy(item.get("read_set") or []),
                    "dependencies": deepcopy(item.get("preconditions") or []),
                    "design_sha256": protocol.get("design_sha256"),
                    "allowed_tools": [], "allowed_writes": [],
                    "isolation": "existing frozen researcher prompts; independent fresh contexts",
                    "output_schema": "avereth-research-artifact/v1",
                    "failure_route": deepcopy(item.get("failure_route")),
                    "dispatch_ready": False,
                    "launch_requirement": "use existing researcher capture and frozen input contracts"})
        return view
    eligible = stage in {"acquisition", "research"} and plan["reference_action"] in {
        "discover", "synthesis", "topic-portfolio"}
    reason = ("Scout pilot is disabled" if not policy["scout_enabled"] else
              "current action remains in the primary thread" if not eligible else
              "a primary-authored public discovery brief is required" if context is None else "")
    if reason:
        view["delegation_decisions"].append({"role": "avereth_scout", "delegate": False, "reason": reason})
        return view
    assert context is not None
    for task in _partitions(context["brief"], policy):
        request = {
            "schema_version": REQUEST_SCHEMA, "stage": stage,
            "action": plan["reference_action"], "role": "avereth_scout",
            "reason": task["objective"], "public_task": task,
            "input_artifacts": [deepcopy(context["input_artifact"])],
            "control_snapshot": {"authority_hashes": deepcopy(context["authority_hashes"]),
                                 "checkpoint": plan.get("next_checkpoint")},
            "allowed_tools": [task["tool"]], "allowed_writes": [],
            "output_schema": RESULT_SCHEMA,
            "isolation": {"context": "fresh_no_parent_history", "tool_access": "primary_search_broker_only",
                          "private_files": False, "recursive_dispatch": False},
            "budget": {"max_active": policy["max_active"],
                       "max_tool_retries": policy["max_tool_retries"],
                       "max_tool_calls": len(task["queries"]) * (1 + policy["max_tool_retries"]),
                       "max_candidates": policy["max_candidates"]},
            "failure_route": "return_to_primary_with_attempts_and_gap",
            "dispatch_ready": True,
            "acceptance": "candidate_only; recheck current request before primary-side capture",
        }
        request["request_id"] = "scout-" + digest(request)
        view["delegation_requests"].append(request)
    return view


def public_url(value: Any) -> str:
    url = _text(value, "candidate URL", 4000)
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    if parsed.scheme not in {"https", "http"} or not hostname or parsed.username or parsed.password:
        raise ValueError("candidate URL must be public HTTP(S), without credentials")
    if hostname.casefold() == "localhost" or hostname.casefold().endswith((".localhost", ".local", ".internal")):
        raise ValueError("local addresses are not public discovery candidates")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if "." not in hostname:
            raise ValueError("candidate URL requires a public hostname")
    else:
        if not address.is_global:
            raise ValueError("private addresses are not public discovery candidates")
    return url


def normalize_hit(hit: Any, query: str) -> dict[str, str]:
    if not isinstance(hit, dict) or set(hit) != {"url", "title", "snippet"}:
        raise ValueError("search adapter must return url/title/snippet records")
    snippet = hit["snippet"]
    if not isinstance(snippet, str) or len(snippet) > 12000:
        raise ValueError("search snippet exceeds capture scope")
    return {"url": public_url(hit["url"]), "title": _text(hit["title"], "title", 1000),
            "snippet": snippet, "query": query, "evidence_status": "unverified_candidate"}


def validate_candidate_result(request: dict[str, Any], result: Any) -> None:
    fields = {"schema_version", "request_id", "candidates", "search_log", "gaps"}
    if not isinstance(result, dict) or set(result) != fields or result["schema_version"] != RESULT_SCHEMA:
        raise ValueError("invalid discovery candidate result")
    if result["request_id"] != request["request_id"]:
        raise ValueError("stale or mismatched discovery request")
    log, candidates, gaps = result["search_log"], result["candidates"], result["gaps"]
    if not isinstance(gaps, list) or any(not isinstance(g, str) or not g.strip() or len(g) > 2000 for g in gaps):
        raise ValueError("discovery gaps must be explicit text")
    if not isinstance(log, list) or len(log) > request["budget"]["max_tool_calls"]:
        raise ValueError("search log exceeds the request budget")
    counts: dict[str, int] = {}
    previous_status: dict[str, str] = {}
    successes: set[str] = set()
    observed: set[str] = set()
    for entry in log:
        if not isinstance(entry, dict) or set(entry) != {"tool", "query", "attempt", "status", "hits", "error"}:
            raise ValueError("invalid search log")
        query = entry["query"]
        if entry["tool"] not in request["allowed_tools"] or query not in request["public_task"]["queries"]:
            raise ValueError("search log contains an unauthorized tool or query")
        counts[query] = counts.get(query, 0) + 1
        if (type(entry["attempt"]) is not int or entry["attempt"] != counts[query]
                or counts[query] > 1 + request["budget"]["max_tool_retries"] or query in successes):
            raise ValueError("search retry limit or ordering violated")
        if not isinstance(entry["status"], str) or entry["status"] not in {"success", "temporary_error", "blocked"}:
            raise ValueError("invalid search attempt status")
        if (not isinstance(entry["error"], str) or not isinstance(entry["hits"], list)
                or len(entry["hits"]) > request["budget"]["max_candidates"]):
            raise ValueError("invalid search capture")
        if entry["status"] == "success":
            if entry["error"]:
                raise ValueError("successful search cannot contain an error")
            successes.add(query)
            for hit in entry["hits"]:
                observed.add(digest(normalize_hit(hit, query)))
        elif entry["hits"] or not entry["error"]:
            raise ValueError("failed searches need a reason and no candidate hits")
        if counts[query] > 1 and previous_status[query] != "temporary_error":
            raise ValueError("only temporary tool errors may be retried")
        previous_status[query] = entry["status"]
    if set(request["public_task"]["queries"]) != successes and not gaps:
        raise ValueError("unexecuted or failed searches require a recorded gap")
    if not isinstance(candidates, list) or len(candidates) > request["budget"]["max_candidates"]:
        raise ValueError("candidate count exceeds the request budget")
    urls: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != {"url", "title", "snippet", "query", "evidence_status"}:
            raise ValueError("invalid candidate fields")
        if candidate.get("evidence_status") != "unverified_candidate" or digest(candidate) not in observed:
            raise ValueError("candidate was not present in the search capture")
        url = public_url(candidate["url"])
        if url in urls:
            raise ValueError("duplicate candidate URL")
        urls.add(url)


def capture_candidates(outdir: Path, request: dict[str, Any], result: Any) -> dict[str, Any]:
    """Primary-side immutable candidate capture; no canonical facts or receipts."""
    validate_candidate_result(request, result)
    body = {key: value for key, value in request.items() if key != "request_id"}
    if request["request_id"] != "scout-" + digest(body):
        raise ValueError("invalid request identity")
    for name, expected in request["control_snapshot"]["authority_hashes"].items():
        if _sha(_inside(outdir, name)) != expected:
            raise ValueError("discovery input drift: " + name)
    for artifact in request["input_artifacts"]:
        if _sha(_inside(outdir, artifact["path"])) != artifact["sha256"]:
            raise ValueError("discovery brief changed since dispatch")
    relative = f"discovery_candidates/{request['request_id']}.json"
    path = _inside(outdir, relative)
    envelope = {"request": request, "result": result, "authority": "discovery_candidates_only"}
    content = json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError("a different result already exists for this request; retain the first capture")
        return {"status": "already_captured", "path": relative}
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create makes duplicate concurrent captures fail instead of replace.
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return {"status": "captured_candidates", "path": relative}
