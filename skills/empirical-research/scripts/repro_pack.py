#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""repro_pack.py — 实证研究复现包与可复现性审计（仅标准库）。

把 cnki-paper 的"绝不伪造 / 页码分级证据"理念落到实证研究：
  · 数据来源登记（sha256 + 行列数 + 获取信息）—— 来源可追溯
  · 样本构造留痕（每一步排除的 n_before→n_after，即 AER 的 footnote 4）
  · 决策日志（计划 vs 实际偏差，防事后编故事）
  · 数字派生视图（从 method_execution.json 的哈希工件定位器生成）
  · 环境冻结（pip freeze；R/Stata 版本手记）
  · check 审计：来源文件在否/哈希对否、登记数字的脚本与输出在否、种子是否冻结

设计原则：纯标准库，跨平台；元数据集中在 <root>/repro/ 下，人可读 + 机器可校验。
与 page-evidence 的 page_evidence_audit.py 同构——证据可追溯，断言才成立。

用法：
  python repro_pack.py init [项目目录]
  python repro_pack.py add-source --file data/raw/survey.csv [--source-url URL --access-date 2026-06-14 --note 备注]
  python repro_pack.py exclude --step "删除缺失因变量" --n-before 5000 --n-after 4731
  python repro_pack.py decision --date 2026-06-14 --what "改用聚类稳健SE" --why "组内相关"
  # 数字只在 method_execution.json 登记；numbers.jsonl 是自动生成的兼容视图
  python repro_pack.py freeze
  python repro_pack.py check           # 审计；有问题退出码 1
  python repro_pack.py manifest        # 重新生成 REPRODUCIBILITY.md
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import method_execution as method_execution_authority  # noqa: E402

REPRO_DIR = "repro"
PROVENANCE = "provenance.json"      # 数据来源登记
SAMPLE_LOG = "sample_log.json"      # 样本构造（排除链）
DECISIONS = "decisions.jsonl"       # 决策日志
NUMBERS = "numbers.jsonl"           # 由 method_execution.json 生成的只读兼容视图
METHOD_EXECUTION = "method_execution.json"  # 落稿数字的唯一事实源
ENVIRONMENT = "environment.txt"     # 环境冻结
MANIFEST_MD = "REPRODUCIBILITY.md"

SCAFFOLD = [
    "data/raw", "data/clean", "scripts",
    "output/tables", "output/figures", "docs",
]


# --------------------------------------------------------------------------- #
# 路径与 IO helper
# --------------------------------------------------------------------------- #
def repro_root(start: Path) -> Path:
    """从 start 向上找含 repro/ 的项目根；找不到则用 start。"""
    start = start.resolve()
    for d in [start, *start.parents]:
        if (d / REPRO_DIR).is_dir():
            return d
    return start


def meta_path(root: Path, name: str) -> Path:
    return root / REPRO_DIR / name


def load_json(p: Path, default):
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(p: Path) -> list:
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(p: Path, rows: list[dict]) -> None:
    """Deterministically replace a generated JSONL view."""
    p.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    p.write_text(text, encoding="utf-8")


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_shape(p: Path):
    """返回 (n_rows_excluding_header, n_cols)；非 csv 或读不动返回 (None, None)。"""
    if p.suffix.lower() not in (".csv", ".tsv"):
        return None, None
    delim = "\t" if p.suffix.lower() == ".tsv" else ","
    try:
        with p.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f, delimiter=delim)
            rows = 0
            ncols = None
            for i, row in enumerate(reader):
                if i == 0:
                    ncols = len(row)
                else:
                    rows += 1
            return rows, ncols
    except (UnicodeDecodeError, csv.Error):
        return None, None


# --------------------------------------------------------------------------- #
# 子命令
# --------------------------------------------------------------------------- #
def cmd_init(args) -> int:
    root = Path(args.dir).resolve()
    for sub in SCAFFOLD:
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / REPRO_DIR).mkdir(parents=True, exist_ok=True)
    # 初始化元数据文件（已存在则不覆盖）
    if not meta_path(root, PROVENANCE).exists():
        save_json(meta_path(root, PROVENANCE), {"sources": []})
    if not meta_path(root, SAMPLE_LOG).exists():
        save_json(meta_path(root, SAMPLE_LOG), {"steps": []})
    meta_path(root, DECISIONS).touch()
    _write_manifest(root)
    print("复现包初始化于：%s" % root)
    print("  结构：%s + repro/（元数据）" % ", ".join(SCAFFOLD))
    return 0


def add_source(root: Path, file: str, source_url=None, access_date=None, note=None) -> dict:
    f = (root / file) if not Path(file).is_absolute() else Path(file)
    if not f.exists():
        raise FileNotFoundError("数据文件不存在：%s" % f)
    rows, ncols = csv_shape(f)
    rec = {
        "file": str(Path(file).as_posix()),
        "sha256": sha256_of(f),
        "bytes": f.stat().st_size,
        "n_rows": rows,
        "n_cols": ncols,
        "source_url": source_url,
        "access_date": access_date,
        "note": note,
    }
    pv = load_json(meta_path(root, PROVENANCE), {"sources": []})
    # 同名文件更新而非重复
    pv["sources"] = [s for s in pv["sources"] if s.get("file") != rec["file"]]
    pv["sources"].append(rec)
    save_json(meta_path(root, PROVENANCE), pv)
    return rec


def cmd_add_source(args) -> int:
    root = repro_root(Path("."))
    rec = add_source(root, args.file, args.source_url, args.access_date, args.note)
    shape = "%s 行 × %s 列" % (rec["n_rows"], rec["n_cols"]) if rec["n_rows"] is not None else "（二进制，未计行列）"
    print("登记来源：%s  sha256=%s…  %s" % (rec["file"], rec["sha256"][:12], shape))
    return 0


def cmd_exclude(args) -> int:
    root = repro_root(Path("."))
    sl = load_json(meta_path(root, SAMPLE_LOG), {"steps": []})
    sl["steps"].append({
        "step": args.step,
        "n_before": args.n_before,
        "n_after": args.n_after,
        "dropped": args.n_before - args.n_after,
    })
    save_json(meta_path(root, SAMPLE_LOG), sl)
    print("样本构造：%s  %d → %d（删 %d）" %
          (args.step, args.n_before, args.n_after, args.n_before - args.n_after))
    return 0


def cmd_decision(args) -> int:
    root = repro_root(Path("."))
    append_jsonl(meta_path(root, DECISIONS),
                 {"date": args.date, "what": args.what, "why": args.why or ""})
    print("决策已记：[%s] %s" % (args.date, args.what))
    return 0


def cmd_number(args) -> int:
    del args
    print(
        "拒绝写入第二份数字真相：请在 method_execution.json 的 "
        "runs[].results[].numeric_values 中登记 value、Evidence ID、Artifact ID、"
        "locator 与 reproduction_command；随后运行 manifest 生成兼容视图。",
        file=sys.stderr,
    )
    return 2


def execution_numbers(root: Path) -> tuple[list[dict], list[str]]:
    """Derive manuscript-number records from the canonical execution contract.

    This function deliberately does not execute ``reproduction_command``.  Safe
    locator recomputation belongs to the method-execution validator; this view
    only exposes its hash-bound identities for the reproducibility manifest.
    """
    execution_path = root / METHOD_EXECUTION
    if not execution_path.is_file():
        return [], ["缺少 method_execution.json——落稿数字必须来自执行合同单一事实源"]
    try:
        payload = load_json(execution_path, {})
    except (json.JSONDecodeError, OSError) as exc:
        return [], ["method_execution.json 无法读取：%s" % exc]
    if not isinstance(payload, dict):
        return [], ["method_execution.json 顶层必须是对象"]

    projection = method_execution_authority.downstream_eligibility(root, payload)
    if projection.get("status") != "PASS":
        details = []
        for issue in projection.get("issues") or []:
            if not isinstance(issue, dict):
                continue
            code = str(issue.get("code") or "ME.ELIGIBILITY.BLOCKED")
            message = str(issue.get("message") or "canonical execution validation failed")
            details.append(f"{code}: {message}")
        return [], details or ["method_execution.json 未通过 canonical v3 下游资格验证"]
    eligible_result_ids = {
        str(result_id).upper()
        for result_id, record in (projection.get("results") or {}).items()
        if isinstance(record, dict) and record.get("allowed_uses")
    }
    digest = sha256_of(execution_path)
    rows: list[dict] = []
    issues: list[str] = []
    for run_index, run in enumerate(payload.get("runs") or []):
        if not isinstance(run, dict):
            continue
        artifacts = {
            str(item.get("id", "")).upper(): item
            for item in (run.get("artifacts") or [])
            if isinstance(item, dict) and item.get("id")
        }
        for result_index, result in enumerate(run.get("results") or []):
            if not isinstance(result, dict):
                continue
            result_id = str(
                result.get("id")
                or "runs[%d].results[%d]" % (run_index, result_index)
            )
            if result_id.upper() not in eligible_result_ids:
                issues.append(
                    "结果 %s 未进入 canonical 下游资格投影；其数字未进入复现视图"
                    % result_id
                )
                continue
            for numeric_index, numeric in enumerate(result.get("numeric_values") or []):
                if not isinstance(numeric, dict):
                    issues.append(
                        "执行数字不是对象：runs[%d].results[%d].numeric_values[%d]"
                        % (run_index, result_index, numeric_index)
                    )
                    continue
                artifact_id = str(numeric.get("artifact_id", "")).upper()
                locator = str(numeric.get("locator", "")).strip()
                reproduction = str(numeric.get("reproduction_command", "")).strip()
                evidence_id = str(numeric.get("evidence_id", "")).upper()
                number_id = str(numeric.get("id") or "%s:N%d" % (result.get("id", "RESULT"), numeric_index + 1))
                missing = [
                    name
                    for name, value in (
                        ("evidence_id", evidence_id),
                        ("artifact_id", artifact_id),
                        ("locator", locator),
                        ("reproduction_command", reproduction),
                    )
                    if not value
                ]
                if missing:
                    issues.append("数字 %s 缺少：%s" % (number_id, ", ".join(missing)))
                artifact = artifacts.get(artifact_id)
                if artifact is None:
                    issues.append("数字 %s 指向未知 Artifact ID：%s" % (number_id, artifact_id or "<empty>"))
                    artifact = {}
                artifact_path = str(artifact.get("path", ""))
                if artifact_path:
                    local = (root / artifact_path).resolve()
                    try:
                        local.relative_to(root.resolve())
                    except ValueError:
                        issues.append("数字 %s 的工件路径越出项目根：%s" % (number_id, artifact_path))
                    else:
                        if not local.is_file():
                            issues.append("数字 %s 的工件缺失：%s" % (number_id, artifact_path))
                        elif artifact.get("sha256") and sha256_of(local) != artifact.get("sha256"):
                            issues.append("数字 %s 的工件哈希不符：%s" % (number_id, artifact_path))
                rows.append(
                    {
                        "id": number_id,
                        "value": numeric.get("value"),
                        "evidence_id": evidence_id,
                        "artifact_id": artifact_id,
                        "artifact_path": artifact_path,
                        "locator": locator,
                        "reproduction_command": reproduction,
                        "run_id": run.get("id"),
                        "result_id": result.get("id"),
                        "generated_from": METHOD_EXECUTION,
                        "execution_sha256": digest,
                    }
                )
    return rows, issues


def sync_numbers_view(root: Path) -> tuple[list[dict], list[str]]:
    rows, issues = execution_numbers(root)
    if (root / METHOD_EXECUTION).is_file():
        write_jsonl(meta_path(root, NUMBERS), rows)
    return rows, issues


def cmd_freeze(args) -> int:
    root = repro_root(Path("."))
    import subprocess
    lines = ["# environment freeze — %s" % datetime.now(timezone.utc).isoformat()]
    try:
        out = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                             capture_output=True, text=True, timeout=120)
        lines.append("## python: %s" % sys.version.split()[0])
        lines.append(out.stdout.strip())
    except Exception as e:  # noqa: BLE001
        lines.append("## pip freeze 失败：%s" % e)
    lines.append("\n## R / Stata 版本请手动补记（sessionInfo() / Stata version）")
    meta_path(root, ENVIRONMENT).write_text("\n".join(lines), encoding="utf-8")
    print("环境已冻结 → %s" % meta_path(root, ENVIRONMENT))
    return 0


def run_check(root: Path) -> list[str]:
    issues = []
    # 1) 数据来源：文件在否 + 哈希对否
    pv = load_json(meta_path(root, PROVENANCE), {"sources": []})
    if not pv["sources"]:
        issues.append("尚未登记任何数据来源（repro_pack.py add-source）")
    for s in pv["sources"]:
        f = root / s["file"]
        if not f.exists():
            issues.append("来源文件缺失：%s" % s["file"])
        elif s.get("sha256") and sha256_of(f) != s["sha256"]:
            issues.append("来源文件哈希不符（数据被改动？）：%s" % s["file"])
    # 2) 落稿数字：只从 method_execution.json 派生；不执行任意重现命令。
    _nums, number_issues = sync_numbers_view(root)
    issues.extend(number_issues)
    # 3) 环境是否冻结
    if not meta_path(root, ENVIRONMENT).exists():
        issues.append("环境未冻结（repro_pack.py freeze）——种子/版本未锁定不可复现")
    return issues


def cmd_check(args) -> int:
    root = repro_root(Path("."))
    issues = run_check(root)
    _write_manifest(root)
    if issues:
        print("可复现性审计：发现 %d 处问题" % len(issues))
        for s in issues:
            print("  ✗ " + s)
        return 1
    print("可复现性审计：通过 ✓（来源可追溯、数字有出处、环境已冻结）")
    return 0


def cmd_manifest(args) -> int:
    root = repro_root(Path("."))
    _write_manifest(root)
    print("已生成 %s" % meta_path(root, MANIFEST_MD))
    return 0


def _write_manifest(root: Path) -> None:
    pv = load_json(meta_path(root, PROVENANCE), {"sources": []})
    sl = load_json(meta_path(root, SAMPLE_LOG), {"steps": []})
    nums, _number_issues = sync_numbers_view(root)
    decs = read_jsonl(meta_path(root, DECISIONS))
    L = ["# 可复现性清单（REPRODUCIBILITY.md）", "",
         "> 由 `repro_pack.py` 自动生成。本文件是复现本研究的总入口。", ""]
    L.append("## 数据来源（%d）" % len(pv["sources"]))
    for s in pv["sources"]:
        shape = "%s×%s" % (s["n_rows"], s["n_cols"]) if s.get("n_rows") is not None else "bin"
        L.append("- `%s`（%s，sha256 `%s…`）来源：%s 获取：%s" %
                 (s["file"], shape, (s.get("sha256") or "")[:12],
                  s.get("source_url") or "—", s.get("access_date") or "—"))
    L.append("")
    L.append("## 样本构造（footnote 4）")
    for st in sl["steps"]:
        L.append("- %s：%s → %s（删 %s）" %
                 (st["step"], st["n_before"], st["n_after"], st["dropped"]))
    L.append("")
    L.append("## 落稿数字溯源（%d）" % len(nums))
    for n in nums:
        L.append("- `%s` = %s ← `%s` `%s`（%s）" %
                 (n.get("id"), n.get("value"), n.get("artifact_id"),
                  n.get("locator"), n.get("evidence_id")))
    L.append("")
    L.append("## 关键决策日志（%d）" % len(decs))
    for d in decs:
        L.append("- [%s] %s%s" % (d.get("date"), d.get("what"),
                                  ("：" + d["why"]) if d.get("why") else ""))
    L.append("")
    L.append("## 环境")
    L.append("见 `repro/environment.txt`（pip freeze）。R/Stata 版本须手记。")
    meta_path(root, MANIFEST_MD).write_text("\n".join(L) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser():
    ap = argparse.ArgumentParser(description="实证研究复现包与可复现性审计（仅标准库）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="初始化复现包结构")
    p.add_argument("dir", nargs="?", default=".")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("add-source", help="登记一个数据来源（哈希+行列）")
    p.add_argument("--file", required=True)
    p.add_argument("--source-url")
    p.add_argument("--access-date")
    p.add_argument("--note")
    p.set_defaults(func=cmd_add_source)

    p = sub.add_parser("exclude", help="记录一步样本排除")
    p.add_argument("--step", required=True)
    p.add_argument("--n-before", type=int, required=True)
    p.add_argument("--n-after", type=int, required=True)
    p.set_defaults(func=cmd_exclude)

    p = sub.add_parser("decision", help="记录一条决策")
    p.add_argument("--date", required=True)
    p.add_argument("--what", required=True)
    p.add_argument("--why")
    p.set_defaults(func=cmd_decision)

    p = sub.add_parser("number", help="已弃用：数字必须登记在 method_execution.json")
    p.add_argument("--id", required=True)
    p.add_argument("--value", required=True)
    p.add_argument("--script", required=True)
    p.add_argument("--output")
    p.set_defaults(func=cmd_number)

    p = sub.add_parser("freeze", help="冻结 python 环境（pip freeze）")
    p.set_defaults(func=cmd_freeze)

    p = sub.add_parser("check", help="可复现性审计（不过退出码 1）")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("manifest", help="重新生成 REPRODUCIBILITY.md")
    p.set_defaults(func=cmd_manifest)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
