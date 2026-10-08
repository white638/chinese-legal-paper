"""Build the machine-prefilled section of the existing figure asset map."""

from __future__ import annotations

from typing import Any, Mapping

from .contract import exhibit_spec


START_MARKER = "<!-- avereth:exhibit-prefill:start -->"
END_MARKER = "<!-- avereth:exhibit-prefill:end -->"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _ids(value: Any) -> list[str]:
    return [_text(item).upper() for item in value or [] if _text(item)]


def _cell(value: Any) -> str:
    return _text(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ") or "—"


def _current_actions(raw_actions: Any) -> list[Mapping[str, Any]]:
    latest: dict[str, tuple[int, str, Mapping[str, Any]]] = {}
    for action in raw_actions or []:
        if not isinstance(action, Mapping):
            continue
        operation_id = _text(action.get("operation_id")).upper()
        action_id = _text(action.get("id")).upper()
        attempt = action.get("attempt")
        if not operation_id or not action_id or not isinstance(attempt, int) or isinstance(attempt, bool):
            continue
        candidate = (attempt, action_id, action)
        if operation_id not in latest or candidate[:2] > latest[operation_id][:2]:
            latest[operation_id] = candidate
    return [item[2] for item in sorted(latest.values(), key=lambda item: (item[0], item[1]))]


def render_prefill(payload: Mapping[str, Any], *, execution_sha256: str = "") -> str:
    rows: list[list[str]] = []
    for run in payload.get("runs") or []:
        if not isinstance(run, Mapping):
            continue
        if _text(run.get("status")) in {"withdrawn", "not-applicable", "planned"}:
            continue
        artifacts = {
            _text(item.get("id")).upper(): item
            for item in run.get("artifacts") or []
            if isinstance(item, Mapping) and _text(item.get("id"))
        }
        results = {
            _text(item.get("id")).upper(): item
            for item in run.get("results") or []
            if isinstance(item, Mapping) and _text(item.get("id"))
        }
        for action in _current_actions(run.get("actions")):
            if _text(action.get("status")) != "accepted":
                continue
            spec = exhibit_spec(action)
            if spec is None:
                continue
            output_ids = _ids(action.get("output_artifact_ids"))
            output = [artifacts[item] for item in output_ids if item in artifacts]
            paths = [f"{_text(item.get('path'))} [{_text(item.get('format')) or _text(item.get('role'))}]" for item in output]
            digests = [f"{_text(item.get('id'))}:{_text(item.get('sha256'))[:12]}" for item in output]
            source_result_ids = _ids(spec.get("source_result_ids"))
            claim_ids = sorted({claim_id for result_id in source_result_ids for claim_id in _ids((results.get(result_id) or {}).get("claim_ids"))})
            data_artifact = next((item for item in output if _text(item.get("role")) in {"plot_data", "table_data"}), {})
            checks = [
                "hash",
                "companion-data",
                "numeric-locator",
                "CI/unit/N",
                "line-marker identity",
                "font/DPI metadata",
            ]
            rows.append(
                [
                    _text(spec.get("exhibit_id")),
                    _text(spec.get("kind")),
                    ", ".join(source_result_ids),
                    _text(action.get("id")),
                    ", ".join(claim_ids),
                    f"{_text(spec.get('quantity'))} ({_text(spec.get('unit'))})",
                    ", ".join(_text(value) for value in spec.get("confidence_levels") or []) or "—",
                    _text(spec.get("placement")),
                    _text(spec.get("argument_role")),
                    "; ".join(paths),
                    "; ".join(digests),
                    _text(data_artifact.get("id")),
                    ", ".join(checks),
                    "待作者确认",
                ]
            )
    lines = [
        START_MARKER,
        "## 实证表图机器预填",
        "",
        "本区仅投影 `method_execution.json` 中通过验证的 accepted 表图 Action。作者判断仍在本表最后一列确认。",
        f"Execution SHA-256: `{execution_sha256 or 'unbound'}`",
        "",
        "| Exhibit ID | 类型 | 来源 Result | 渲染 Action | Claim | 估计量/单位 | CI | 位置 | 论证角色 | 文件/格式 | Artifact/SHA | Companion data | 技术检查 | 作者确认 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    if rows:
        lines.extend("| " + " | ".join(_cell(item) for item in row) + " |" for row in rows)
    else:
        lines.append("| — | — | — | — | — | — | — | — | — | — | — | — | 当前无已接受的表图 Action | — |")
    lines.extend(
        [
            "",
            "作者确认应说明：为何需要表图、读者应获得的认识、图注是否自足、目标刊功能对应，以及保留/合并/拆分/删除处置。",
            END_MARKER,
        ]
    )
    return "\n".join(lines) + "\n"


def update_document(existing: str, prefill: str) -> str:
    start_count = existing.count(START_MARKER)
    end_count = existing.count(END_MARKER)
    if start_count != end_count or start_count not in {0, 1}:
        raise ValueError(
            "EXHIBIT.MANUSCRIPT.MAP_MARKERS_INVALID: machine prefill markers must be absent or form one pair"
        )
    if start_count == 1:
        start = existing.index(START_MARKER)
        end = existing.index(END_MARKER) if END_MARKER in existing else -1
        if end < start:
            raise ValueError(
                "EXHIBIT.MANUSCRIPT.MAP_MARKERS_INVALID: machine prefill markers are reversed"
            )
        end += len(END_MARKER)
        return existing[:start] + prefill.rstrip("\r\n") + existing[end:]
    if not existing:
        return "# Figure Asset Map\n\n" + prefill
    separator = "\n" if existing.endswith(("\n", "\r")) else "\n\n"
    return existing + separator + prefill
