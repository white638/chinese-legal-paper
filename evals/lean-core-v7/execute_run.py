"""Execute registered full-workflow tasks through reviewed external host adapters.

Preflight is the default. Execution requires --execute and an independently
configured assessor. Neither successful execution nor diagnostics authorize release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from capture_run import capture
from diagnose_runs import timestamp
from run_records import evidence_valid, load_json, selection_bindings, selection_issues
from selection import validate_selection, write_selection
from decision_policy import target_issues
from trajectory_report import summarize

SCHEMA = "avereth-workflow-execution-spec/v1"
PLACEHOLDERS = {"request", "workspace", "spec_root", "python"}
BYPASS_FLAGS = {"--dangerously-bypass-approvals-and-sandbox", "--dangerously-skip-permissions",
                "--allow-dangerously-skip-permissions", "--yolo", "bypassPermissions", "danger-full-access"}
CONDITIONS = ("model", "reasoning_effort", "host_version", "tool_versions", "prompt_version", "evaluation_mode")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def inside(root: Path, raw: str) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise ValueError("input paths must be relative to the specification root")
    target = (root / raw).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("input path escapes its root")
    return target


def bound(root: Path, record: dict) -> Path:
    if not evidence_valid(record, root):
        raise ValueError("missing, empty, changed, or escaping evidence file")
    return inside(root, record["path"])


def command_check(command: dict, root: Path, *, assessor: bool = False) -> None:
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) or not arg for arg in argv):
        raise ValueError("reviewed command requires a nonempty argv list")
    if any(any(flag in arg for flag in BYPASS_FLAGS) for arg in argv):
        raise ValueError("sandbox/approval bypass flags are not supported")
    executable = os.sys.executable if argv[0] == "{python}" else argv[0]
    if not Path(executable).is_absolute() or not Path(executable).is_file():
        raise ValueError("command executable must be an existing absolute path")
    if Path(argv[0]).name.lower() in {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe", "sh", "bash", "zsh"}:
        raise ValueError("invoke an adapter executable directly, not a command shell")
    fields = set(re.findall(r"\{([^{}]+)\}", " ".join(argv)))
    if fields - PLACEHOLDERS or "request" not in fields:
        raise ValueError("argv must use {request}; supported substitutions are request, workspace, spec_root and python")
    review = load_json(bound(root, command["review_record"]))
    digest = hashlib.sha256(json.dumps(argv, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    if review.get("argv_sha256") != digest or not review.get("reviewer") or not review.get("evidence_notes"):
        raise ValueError("command review must bind the exact argv and retain reviewer evidence")
    if review.get("sandbox_policy") != "host_enforced" or review.get("network_policy") not in {"disabled", "explicitly_authorized"}:
        raise ValueError("command review must retain host sandbox and explicit network policy")
    adapters = command.get("adapter_files")
    if not isinstance(adapters, list) or not adapters:
        raise ValueError("command adapter files must be hash-bound")
    for item in adapters:
        bound(root, item)
    if assessor:
        if not command.get("reviewer_id") or not command.get("independence_basis"):
            raise ValueError("assessor needs an independent reviewer identity and basis")
    elif not {"full_workflow", "isolated_workspace", "raw_trace"} <= set(command.get("capabilities", [])):
        raise ValueError("host must implement full_workflow, isolated_workspace and raw_trace")


def preflight(spec_path: Path, experiment_path: Path, manifest_path: Path) -> dict:
    report = {"schema_version": "avereth-workflow-preflight/v1", "status": "blocked", "issues": [],
              "required_tasks": 0, "ready_tasks": 0, "release_authorized": False, "model_calls": 0}
    issues = report["issues"]
    try:
        manifest = load_json(manifest_path)
        validate_selection(manifest, manifest_path.parent)
        selected = selection_bindings(manifest)
        expected = {task["id"]: task for task in manifest["tasks"]}
        report["required_tasks"] = len(expected)
        spec, experiment = map(load_json, (spec_path, experiment_path))
        issues.extend(selection_issues(manifest, spec))
        if selected and any(experiment.get(key) != value for key, value in selected.items()):
            issues.append("experiment must register the selected bank and task identity")
        root = spec_path.resolve().parent
        if spec.get("schema_version") != SCHEMA or not re.fullmatch(r"[A-Za-z0-9_.-]+", spec.get("run_id", "")):
            issues.append("execution spec schema and safe run_id are required")
        if spec.get("evidence_mode") != "real_workflow":
            issues.append("execution spec must declare real_workflow; synthetic tests are not a live evaluation")
        if experiment.get("schema_version") != "avereth-paired-experiment/v1" or not experiment.get("experiment_id"):
            issues.append("registered paired experiment is required")
        if experiment.get("manifest_sha256") != sha(manifest_path):
            issues.append("experiment must bind the unchanged frozen manifest")
        issues.extend(target_issues(experiment.get("target")))
        repeat = (experiment.get("execution") or {}).get("repeat_on_uncertain", 0)
        if not isinstance(repeat, int) or isinstance(repeat, bool) or not 0 <= repeat <= 2:
            issues.append("repeat_on_uncertain must be an integer from 0 to 2")
        try:
            if timestamp(experiment.get("registered_at")) > datetime.now(timezone.utc):
                issues.append("experiment registration cannot be in the future")
        except ValueError:
            issues.append("experiment needs a real registration timestamp before execution")
        side = spec.get("side")
        if side not in {"baseline", "candidate"}:
            issues.append("side must be baseline or candidate")
        config_path = bound(root, spec["effective_config"])
        config = load_json(config_path)
        if sha(config_path) != experiment.get(str(side) + "_config_sha256"):
            issues.append("effective configuration hash differs from registered side")
        for field in CONDITIONS:
            if not config.get(field) or config.get(field) == "REQUIRED":
                issues.append(f"effective configuration is missing {field}")
        if config.get("evaluation_mode") != experiment.get("evaluation_mode") or config.get("evaluation_mode") not in {"offline_fixed_materials", "online_retrieval"}:
            issues.append("evaluation mode must match the experiment")
        if not config.get("source_access") or not config.get("budget"):
            issues.append("source access conditions and an explicit execution budget are required")
        supported_config = {*CONDITIONS, "source_access", "budget", "workflow_config_overrides", "instruction_variant"}
        if set(config) - supported_config:
            issues.append("unsupported effective configuration fields cannot be treated as applied variables")
        if config.get("instruction_variant", "current") not in {"current", "lean", "minimal"}:
            issues.append("instruction_variant must be current, lean or minimal")
        if config.get("budget") != {"task_timeout_seconds": spec.get("task_timeout_seconds")}:
            issues.append("supported budget is the enforced task_timeout_seconds; token/currency limits require another adapter")
        for role in ("host", "assessor"):
            try:
                command_check(spec[role], root, assessor=role == "assessor")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                issues.append(f"{role}: {exc}")
        timeout = spec.get("task_timeout_seconds")
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 86400:
            issues.append("task_timeout_seconds must be an integer from 1 to 86400")
        code_root = (root / spec["code_root"]).resolve()
        if not any((code_root / "skills/cnki-paper" / name).is_file() for name in ("SKILL.md", "SKILL.source.md")):
            issues.append("code_root must contain the Avereth workflow")
        revision = subprocess.run(["git", "-c", "safe.directory=" + code_root.as_posix(), "-C", str(code_root), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, check=False)
        dirty = subprocess.run(["git", "-c", "safe.directory=" + code_root.as_posix(), "-C", str(code_root), "status", "--porcelain"],
                               capture_output=True, text=True, check=False)
        if revision.returncode or revision.stdout.strip() != spec.get("code_revision") or dirty.returncode or dirty.stdout.strip():
            issues.append("code_root must be clean and match the exact configured code revision")
        rows = spec.get("tasks", [])
        ids = [row.get("id") for row in rows if isinstance(row, dict)]
        if len(ids) != len(rows) or len(set(ids)) != len(rows) or not set(expected) <= set(ids):
            issues.append("all selected task IDs must occur exactly once; no selected task may be dropped")
        for row in (item for item in rows if isinstance(item, dict) and item.get("id") in expected):
            try:
                task_id = row["id"]
                if task_id not in expected or not re.fullmatch(r"[A-Za-z0-9_.-]+", task_id):
                    raise ValueError("unknown or unsafe task ID")
                snapshot_path = bound(root, row["materials"])
                snapshot = load_json(snapshot_path)
                if snapshot.get("schema_version") != "avereth-material-snapshot/v1" or not snapshot.get("files"):
                    raise ValueError("actual material snapshot with files is required")
                destinations = set()
                for item in snapshot["files"]:
                    bound(snapshot_path.parent, item)
                    destination = inside(Path("/material-root").resolve(), item["destination"])
                    if destination in destinations:
                        raise ValueError("material destinations must be unique")
                    destinations.add(destination)
                    if item.get("content_verified") is not True or item.get("permission") not in {"public_domain", "licensed", "authorized_private"}:
                        raise ValueError("each material needs content verification and permitted use")
                    if not item.get("source_id") or not item.get("role") or not item.get("verification_notes"):
                        raise ValueError("each material needs source identity, role and verification evidence")
                authorization = load_json(bound(root, row["authorization"]))
                if authorization.get("task_prompt_sha256") != hashlib.sha256(expected[task_id]["task"].encode()).hexdigest():
                    raise ValueError("task authorization does not bind the frozen prompt")
                if not authorization.get("permitted_endpoint") or not authorization.get("authority_evidence"):
                    raise ValueError("task needs an authorized endpoint and evidence; missing user decisions remain checkpoints")
                endpoint = authorization["permitted_endpoint"]
                if not isinstance(endpoint, dict) or endpoint.get("kind") not in {"profile_complete", "stage_complete"}:
                    raise ValueError("workflow endpoint must be profile_complete or stage_complete")
                if endpoint["kind"] == "stage_complete" and endpoint.get("stage") not in {"intake", "topic_selection", "acquisition", "design", "execution", "build", "audit", "output"}:
                    raise ValueError("stage_complete requires a canonical stage")
                if row.get("workflow_config"):
                    load_json(bound(root, row["workflow_config"]))
                elif config.get("workflow_config_overrides"):
                    raise ValueError("registered workflow overrides require each task's bound initial workflow_config")
                report["ready_tasks"] += 1
            except (OSError, ValueError, KeyError, TypeError) as exc:
                issues.append(f"{row.get('id', 'unknown')}: {exc}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        issues.append(str(exc))
    if not issues:
        report["status"] = "ready_for_execution"
    return report


def init_spec(root: Path, manifest_path: Path, code_root: Path, codex: str | None = None, *, scope: str = "targeted",
              tags: list[str] | None = None, exclude_tags: list[str] | None = None, max_cases: int | None = None) -> dict:
    """Write an explicitly incomplete setup, never authorizations or quality scores."""
    root.mkdir(parents=True, exist_ok=False)
    frozen = load_json(manifest_path)
    if frozen.get("bank_version") and not frozen.get("selection"):
        frozen = write_selection(manifest_path, root / "selected-manifest.json", scope=scope, tags=tags, exclude_tags=exclude_tags, max_cases=max_cases)
        manifest_path = root / "selected-manifest.json"
    else:
        validate_selection(frozen, manifest_path.parent)
    adapter_root = root / "adapter"
    adapter_root.mkdir()
    for name in ("codex_workflow_adapter.py", "instruction_variants.py", "execute_run.py", "capture_run.py", "compare_runs.py", "diagnose_runs.py", "run_records.py", "trajectory_report.py", "selection.py", "decision_policy.py"):
        shutil.copyfile(Path(__file__).with_name(name), adapter_root / name)
    adapter_bindings = [{"path": path.relative_to(root).as_posix(), "sha256": sha(path)} for path in sorted(adapter_root.glob("*.py"))]
    version = "REQUIRED"
    if codex:
        result = subprocess.run([codex, "--version"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            version = result.stdout.strip()
    config = {"model": "REQUIRED", "reasoning_effort": "medium", "host_version": version,
              "tool_versions": {"codex": version, "python": os.sys.version.split()[0]}, "prompt_version": "codex-workflow-adapter/v1",
              "evaluation_mode": "offline_fixed_materials", "source_access": {"network": "disabled"},
              "budget": {"task_timeout_seconds": 1800}, "workflow_config_overrides": {}, "instruction_variant": "current"}
    write_new(root / "effective-config.json", config)
    commands = {}
    for role, mode in (("host", "workflow"), ("assessor", "assess")):
        argv = ["{python}", "{spec_root}/adapter/codex_workflow_adapter.py", mode, "--request", "{request}", "--codex", codex or "REQUIRED", "--timeout", "1740"]
        if role == "assessor":
            argv.extend(["--model", "REQUIRED", "--reasoning", "medium"])
        review = {"argv_sha256": hashlib.sha256(json.dumps(argv, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
                  "reviewer": "", "evidence_notes": "", "sandbox_policy": "host_enforced", "network_policy": "disabled"}
        review_path = root / (role + "-command-review.json")
        write_new(review_path, review)
        command = {"argv": argv, "adapter_files": adapter_bindings,
                   "review_record": {"path": review_path.name, "sha256": sha(review_path)}}
        if role == "host":
            command["capabilities"] = ["full_workflow", "isolated_workspace", "raw_trace"]
        else:
            command.update(reviewer_id="", independence_basis="")
        commands[role] = command
    tasks = []
    for task in frozen["tasks"]:
        directory = root / "inputs" / task["id"]
        write_new(directory / "materials.json", {"schema_version": "avereth-material-snapshot/v1", "files": []})
        write_new(directory / "authorization.json", {"task_prompt_sha256": hashlib.sha256(task["task"].encode()).hexdigest(),
                                                       "permitted_endpoint": None, "authority_evidence": "", "user_decisions": []})
        tasks.append({"id": task["id"], **{name: {"path": (directory / filename).relative_to(root).as_posix(), "sha256": sha(directory / filename)}
                                          for name, filename in (("materials", "materials.json"), ("authorization", "authorization.json"))}})
    code_root = code_root.resolve()
    revision = subprocess.run(["git", "-c", "safe.directory=" + code_root.as_posix(), "-C", str(code_root), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    spec = {"schema_version": SCHEMA, "run_id": "lean-core-baseline", "side": "baseline", "evidence_mode": "real_workflow",
            "code_root": str(code_root), "code_revision": revision.stdout.strip(), "task_timeout_seconds": 1800,
            "effective_config": {"path": "effective-config.json", "sha256": sha(root / "effective-config.json")}, **commands, "tasks": tasks}
    spec.update(selection_bindings(frozen))
    write_new(root / "execution-spec.json", spec)
    write_new(root / "experiment.json", {"schema_version": "avereth-paired-experiment/v1", "experiment_id": "setup-pending-registration",
                                         "registered_at": "REQUIRED", "manifest_sha256": sha(manifest_path),
                                         "baseline_config_sha256": sha(root / "effective-config.json"), "candidate_config_sha256": "REQUIRED",
                                         "allowed_config_changes": [], "evaluation_mode": "offline_fixed_materials", "target": None,
                                         "execution": {"repeat_on_uncertain": 0}, **selection_bindings(frozen)})
    write_new(root / "setup-gaps.json", {"status": "blocked", "required_tasks": len(tasks), "material_tasks_missing": [task["id"] for task in tasks],
                                       "required": ["registered experiment and side configurations", "actual model and CLI versions", "reviewed commands and independent assessor", "verified per-task materials and actual authorization evidence"],
                                       "release_authorized": False})
    return {"status": "blocked", "required_tasks": len(tasks), "release_authorized": False}


def stop_process_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def invoke(command: dict, request: Path, workspace: Path, log_dir: Path, timeout: int, *, spec_root: Path | None = None) -> dict:
    argv = [arg.format(request=str(request), workspace=str(workspace), spec_root=str(spec_root or request.parent), python=os.sys.executable) for arg in command["argv"]]
    started, tick = utc(), time.monotonic()
    with (log_dir / "stdout.raw").open("xb") as stdout, (log_dir / "stderr.raw").open("xb") as stderr:
        try:
            environment = os.environ.copy()
            environment["AVERETH_EVAL_PROCESS_GROUP_OWNED"] = "1"
            process = subprocess.Popen(argv, cwd=workspace, shell=False, stdout=stdout, stderr=stderr, env=environment,
                                       creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                                       start_new_session=os.name != "nt")
            try:
                returncode = process.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                stop_process_tree(process)
                raise
            outcome = {"returncode": returncode, "failure_type": None if returncode == 0 else "host_exit_nonzero"}
        except subprocess.TimeoutExpired:
            outcome = {"returncode": None, "failure_type": "host_timeout"}
        except KeyboardInterrupt:
            outcome = {"returncode": None, "failure_type": "operator_interruption"}
        except OSError as exc:
            stderr.write(str(exc).encode("utf-8"))
            outcome = {"returncode": None, "failure_type": "host_start_failed"}
    outcome.update(started_at=started, wall_time_seconds=time.monotonic() - tick, argv=argv)
    write_new(log_dir / "process.json", outcome)
    return outcome


def context_for(spec: dict, config: dict, task: dict, materials: Path) -> dict:
    return {**{key: config[key] for key in CONDITIONS}, "run_id": spec["run_id"], "code_revision": spec["code_revision"],
            "effective_config_sha256": spec["effective_config"]["sha256"], "task_prompt_sha256": hashlib.sha256(task["task"].encode()).hexdigest(),
            "material_snapshot_sha256": sha(materials), **{key: spec[key] for key in ("selection_sha256", "bank_sha256") if key in spec}}


def validate_trace(path: Path, expected: dict, output: Path, started_at: str) -> dict:
    trace = load_json(path)
    context = trace.get("run_context") or {}
    if not isinstance(trace.get("events"), list) or not trace["events"]:
        raise ValueError("host must export original events")
    if any(context.get(key) != value for key, value in expected.items()):
        raise ValueError("actual host context differs from registered execution conditions")
    if timestamp(context.get("started_at")) < timestamp(started_at):
        raise ValueError("host trace predates this attempt")
    if not context.get("context_id") or trace.get("execution_scope") != "full_workflow":
        raise ValueError("full-workflow scope and actual context identity are required")
    if trace.get("status") not in {"completed", "failed", "interrupted", "refused"}:
        raise ValueError("host trace has no final execution status")
    if trace["status"] == "completed":
        if not output.is_file() or not output.stat().st_size or trace.get("output_sha256") != sha(output):
            raise ValueError("completed host trace must bind its actual nonempty output")
        if not trace.get("workflow_evidence"):
            raise ValueError("completed workflow needs concrete endpoint evidence")
    elif not trace.get("failure_reason"):
        raise ValueError("unfinished host trace needs a reason")
    return trace


def validate_assessment(path: Path, raw: Path, trace: Path, output: Path, reviewer: dict, writer_context: str) -> None:
    assessment = load_json(path)
    context = assessment.get("review_context") or {}
    if not context.get("context_id") or context["context_id"] == writer_context or context.get("reviewer_id") != reviewer["reviewer_id"]:
        raise ValueError("assessment requires a distinct independent reviewer context")
    if not context.get("independence_basis") or not assessment.get("evidence_notes"):
        raise ValueError("original review evidence and independence basis are required")
    if assessment.get("trace_sha256") != sha(trace) or assessment.get("raw_review_sha256") != sha(raw):
        raise ValueError("assessment must bind the actual trace and original review")
    if output.is_file() and assessment.get("output_sha256") != sha(output):
        raise ValueError("assessment must bind the actual output")


def fallback_trace(path: Path, spec: dict, expected: dict, process: dict, reason: str) -> dict:
    context = {"run_id": spec["run_id"], "code_revision": spec["code_revision"], "started_at": process["started_at"],
               "effective_config_sha256": spec["effective_config"]["sha256"],
               "task_prompt_sha256": expected["task_prompt_sha256"], "material_snapshot_sha256": expected["material_snapshot_sha256"]}
    context.update({key: expected[key] for key in ("selection_sha256", "bank_sha256") if key in expected})
    trace = {"run_context": context, "requested_context": expected, "events": [{"type": "runner.process", **process}],
             "measurements": {"wall_time_seconds": process["wall_time_seconds"]}, "status": "interrupted" if process["failure_type"] in {"host_timeout", "operator_interruption"} else "failed",
             "failure_type": process["failure_type"] or "invalid_host_export", "failure_reason": reason}
    write_new(path, trace)
    return trace


def execute_task(spec: dict, source_root: Path, run_root: Path, task: dict, row: dict, attempt: Path) -> None:
    task_started = time.monotonic()
    config = load_json(run_root / "effective-config.json")
    workspace = attempt / "workspace"
    workspace.mkdir()
    source_snapshot = bound(source_root, row["materials"])
    shutil.copyfile(source_snapshot, attempt / "materials.json")
    shutil.copyfile(bound(source_root, row["authorization"]), attempt / "authorization.json")
    snapshot = load_json(source_snapshot)
    for item in snapshot["files"]:
        destination = inside(workspace / "materials", item["destination"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bound(source_snapshot.parent, item), destination)
    if row.get("workflow_config"):
        workflow_config = load_json(bound(source_root, row["workflow_config"]))
        workflow_config.update(config.get("workflow_config_overrides") or {})
        write_new(workspace / "workflow_config.json", workflow_config)
    expected = context_for(spec, config, task, attempt / "materials.json")
    request = {"schema_version": "avereth-workflow-host-request/v1", "task": task,
               "code_root": spec["code_root"], "effective_config": str(run_root / "effective-config.json"),
               "expected_context": expected, "authorization": str(attempt / "authorization.json"),
               "materials": str(attempt / "materials.json"), "material_root": str(workspace / "materials"),
               "workspace": str(workspace), "trace_output": str(attempt / "host-trace.json"),
               "output": str(attempt / "output.json"), "required_execution_scope": "full_workflow"}
    write_new(attempt / "request.json", request)
    write_new(attempt / "started.json", {"started_at": utc()})
    process = invoke(spec["host"], attempt / "request.json", workspace, attempt, spec["task_timeout_seconds"], spec_root=source_root)
    output, trace_path = attempt / "output.json", attempt / "host-trace.json"
    try:
        if process["failure_type"]:
            raise ValueError(process["failure_type"])
        trace = validate_trace(trace_path, expected, output, process["started_at"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        trace_path = attempt / "runner-failure-trace.json"
        trace = fallback_trace(trace_path, spec, expected, process, str(exc))
    assessment_dir = attempt / "review"
    assessment_dir.mkdir()
    review_request = {"schema_version": "avereth-workflow-assessment-request/v1", "task": task,
                      "trace": str(trace_path), "output": str(output) if output.is_file() else None,
                      "materials": str(attempt / "materials.json"), "material_root": str(workspace / "materials"),
                      "trace_sha256": sha(trace_path), "output_sha256": sha(output) if output.is_file() else None,
                      "writer_context_id": (trace.get("run_context") or {}).get("context_id"),
                      "reviewer_id": spec["assessor"]["reviewer_id"], "assessment_output": str(assessment_dir / "assessment.json"),
                      "raw_review_output": str(assessment_dir / "raw-review.json")}
    write_new(assessment_dir / "request.json", review_request)
    remaining = spec["task_timeout_seconds"] - (time.monotonic() - task_started)
    review_process = ({"failure_type": "operator_interruption"} if process["failure_type"] == "operator_interruption" else
                      {"failure_type": "task_budget_exhausted"} if remaining <= 0 else
                      invoke(spec["assessor"], assessment_dir / "request.json", assessment_dir, assessment_dir, remaining, spec_root=source_root))
    assessment = assessment_dir / "assessment.json"
    review_issue = None
    try:
        if review_process["failure_type"]:
            raise ValueError(review_process["failure_type"])
        validate_assessment(assessment, assessment_dir / "raw-review.json", trace_path, output, spec["assessor"],
                            (trace.get("run_context") or {}).get("context_id"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        review_issue = str(exc)
        assessment = assessment_dir / "unassessed.json"
        write_new(assessment, {"trace_sha256": sha(trace_path), "output_sha256": sha(output) if output.is_file() else None,
                              "quality": {}, "factual_checks": {}, "diagnostics": {}, "responsibility_coverage": {},
                              "evidence_notes": "Independent assessment unavailable: " + review_issue})
    outcome = {"id": task["id"], "status": trace["status"], "review_status": "blocked" if review_issue else "assessed",
               "review_issue": review_issue, "failure_type": trace.get("failure_type"),
               "trace": trace_path.relative_to(run_root).as_posix(), "assessment": assessment.relative_to(run_root).as_posix(),
               "materials": (attempt / "materials.json").relative_to(run_root).as_posix()}
    if trace["status"] == "completed":
        outcome["output"] = output.relative_to(run_root).as_posix()
    outcome["operator_interrupted"] = process["failure_type"] == "operator_interruption" or review_process["failure_type"] == "operator_interruption"
    outcome["sealed_files"] = {path.relative_to(run_root).as_posix(): sha(path) for path in attempt.rglob("*") if path.is_file()}
    write_new(attempt / "outcome.json", outcome)


def check_sealed(outcome: dict, root: Path, attempt: Path) -> None:
    seals = outcome.get("sealed_files")
    if not isinstance(seals, dict) or not seals:
        raise ValueError("resumed attempt has no sealed evidence")
    for relative, expected in seals.items():
        path = inside(root, relative)
        if not path.is_relative_to(attempt) or not path.is_file() or sha(path) != expected:
            raise ValueError("resumed attempt evidence changed; preserve it and start a separately identified run")
    for key in ("trace", "assessment", "materials"):
        if outcome.get(key) not in seals:
            raise ValueError("resumed outcome points outside its sealed evidence")
    if outcome.get("output") and outcome["output"] not in seals:
        raise ValueError("resumed output is not sealed")


def execute(spec_path: Path, experiment_path: Path, manifest_path: Path, run_root: Path, *, retry_failed: bool = False) -> dict:
    check = preflight(spec_path, experiment_path, manifest_path)
    if check["status"] != "ready_for_execution":
        return check
    spec, manifest = load_json(spec_path), load_json(manifest_path)
    root, run_root = spec_path.resolve().parent, run_root.resolve()
    spec["code_root"] = str((root / spec["code_root"]).resolve())
    binding = {"spec_sha256": sha(spec_path), "experiment_sha256": sha(experiment_path), "manifest_sha256": sha(manifest_path)}
    if run_root.exists():
        if not (run_root / "binding.json").is_file() or load_json(run_root / "binding.json") != binding:
            raise ValueError("existing run root belongs to another or changed specification")
    else:
        run_root.mkdir(parents=True)
        write_new(run_root / "binding.json", binding)
        for source, name in ((spec_path, "execution-spec.json"), (experiment_path, "experiment.json"), (manifest_path, "manifest.json"),
                             (bound(root, spec["effective_config"]), "effective-config.json")):
            shutil.copyfile(source, run_root / name)
        if manifest.get("source_bank"):
            record = manifest["source_bank"]
            destination = inside(run_root, record["path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bound(manifest_path.parent, record), destination)
    records, selected = [], []
    rows = {row["id"]: row for row in spec["tasks"]}
    for task in manifest["tasks"]:
        task_root = run_root / "tasks" / task["id"]
        task_root.mkdir(parents=True, exist_ok=True)
        attempts = sorted(task_root.glob("attempt-*"))
        previous = load_json(attempts[-1] / "outcome.json") if attempts and (attempts[-1] / "outcome.json").is_file() else None
        if previous:
            check_sealed(previous, run_root, attempts[-1])
        if attempts and previous is None and not retry_failed:
            records.append({"id": task["id"], "status": "interrupted", "review_status": "blocked", "failure_type": "unsealed_attempt"})
            continue
        if previous and (not retry_failed or (previous["status"] == "completed" and previous["review_status"] == "assessed")):
            outcome = previous
        else:
            attempt = task_root / f"attempt-{len(attempts) + 1:04d}"
            attempt.mkdir()
            execute_task(spec, root, run_root, task, rows[task["id"]], attempt)
            outcome = load_json(attempt / "outcome.json")
        records.append(outcome)
        selected.append(outcome)
        if outcome.get("operator_interrupted"):
            remaining = manifest["tasks"][len(records):]
            records.extend({"id": item["id"], "status": "interrupted", "failure_type": "not_started_after_operator_interruption", "review_status": "blocked"} for item in remaining)
            break
    ordinal = len(list(run_root.glob("execution-*.json"))) + 1
    result = {"schema_version": "avereth-workflow-execution/v1", "status": "assessment_ready" if all(row.get("review_status") == "assessed" for row in records) else "blocked",
              "required_tasks": len(manifest["tasks"]), "completed_tasks": sum(row["status"] == "completed" for row in records),
              "records": records, "release_authorized": False, "quality_passed": False}
    if len(selected) == len(manifest["tasks"]):
        capture_spec = {"effective_config": "effective-config.json", "tasks": selected}
        if manifest.get("selection"):
            capture_spec.update(manifest="manifest.json", selection_bindings=selection_bindings(manifest))
        write_new(run_root / f"capture-{ordinal:04d}.json", capture_spec)
        captured = capture(capture_spec, run_root, run_root / "experiment.json")
        run_path = run_root / f"run-{ordinal:04d}.json"
        write_new(run_path, captured)
        result["captured_run"] = run_path.name
        write_new(run_root / f"trajectory-{ordinal:04d}.json", summarize(manifest, captured, run_root))
    write_new(run_root / f"execution-{ordinal:04d}.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, nargs="?")
    parser.add_argument("--experiment", type=Path)
    parser.add_argument("--init-spec", type=Path)
    parser.add_argument("--code-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--codex")
    parser.add_argument("--scope", choices=("smoke", "targeted", "broader"), default="targeted")
    parser.add_argument("--tags", default="")
    parser.add_argument("--exclude-tags", default="")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--preflight-output", type=Path)
    args = parser.parse_args()
    if args.init_spec:
        result = init_spec(args.init_spec, args.manifest, args.code_root, args.codex, scope=args.scope,
                           tags=[tag.strip() for tag in args.tags.split(",") if tag.strip()],
                           exclude_tags=[tag.strip() for tag in args.exclude_tags.split(",") if tag.strip()], max_cases=args.max_cases)
        print(json.dumps(result))
        return 0
    if not args.spec or not args.experiment:
        parser.error("preflight/execution require SPEC and --experiment")
    if args.execute and not args.output_root:
        parser.error("--execute requires --output-root")
    if args.retry_failed and not args.execute:
        parser.error("--retry-failed requires --execute")
    result = execute(args.spec, args.experiment, args.manifest, args.output_root, retry_failed=args.retry_failed) if args.execute else preflight(args.spec, args.experiment, args.manifest)
    if args.preflight_output:
        write_new(args.preflight_output, result)
    print(json.dumps({key: result[key] for key in ("status", "required_tasks", "release_authorized")}, ensure_ascii=False))
    for issue in result.get("issues", []):
        print(issue)
    return 0 if result["status"] in {"ready_for_execution", "assessment_ready"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
