"""Capture exact judge dispatches from a clean, explicitly pinned source tree."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path


BASELINE_COMMIT = "fae2cbf09fc5d394bf1a0dd15b587294fad2e667"
SOURCE_PATHS = (
    "skills/cnki-paper/scripts/taste_judge.py",
    "skills/cnki-paper/scripts/taste_cards.py",
    "skills/cnki-paper/scripts/avereth_core/hosts/agent_declared.py",
    "skills/cnki-paper/scripts/avereth_core/hosts/base.py",
    "skills/cnki-paper/references/taste/branch-taste-cards.json",
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def git(source: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source), *args],
        text=True,
        encoding="utf-8",
    ).strip()


def fixtures() -> dict:
    candidate = {
        "id": "CAND-01",
        "status": "alternate",
        "maturity": "screened",
        "research_question": "When do recording rules change apparent service completion?",
        "potential_contribution": "Separate recorded completion from actual access before interpreting differences.",
    }
    references = [
        {
            "identifier": f"SYNTHETIC-RESULT-{index:02d}",
            "title": title,
            "claim": claim,
        }
        for index, title, claim in (
            (1, "Recording rules and completion", "The synthetic result attributes completion differences to recording rules."),
            (2, "Access costs and service use", "The synthetic result attributes uptake differences to the cost of access."),
        )
    ]
    proposals = [
        {
            "identifier": f"SYNTHETIC-PROPOSAL-{index:02d}",
            "title": title,
            "claim": update,
            "comparison_view": {
                "maturity": "proposal",
                "origin": "contemporaneous",
                "question": question,
                "update": update,
            },
        }
        for index, title, question, update in (
            (1, "Comparability of completion measures", "Do completion records describe the same event across districts?", "Identify which district comparisons are supported by consistent definitions."),
            (2, "Costs of applying for services", "When do application costs explain non-use of services?", "Distinguish access costs from eligibility in an explicitly bounded comparison."),
        )
    ]
    return {
        "synthetic": True,
        "evidence_kind": "contract fixtures, not real projects, articles, proposals, or model judgments",
        "config": {"task_profile": "topic_selection", "direction_contract": {"field": "比较政治"}},
        "candidate": candidate,
        "published-results": references,
        "original-proposals": proposals,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--expected-commit", default=BASELINE_COMMIT)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.out.resolve()
    commit = git(source, "rev-parse", "HEAD")
    if commit != args.expected_commit:
        raise ValueError("source HEAD does not match the explicitly selected baseline")
    if git(source, "status", "--porcelain"):
        raise ValueError("baseline source tree must be clean")
    if out.exists() and any(out.iterdir()):
        raise ValueError("capture output must be empty; frozen evidence is never overwritten")
    sys.path.insert(0, str(source / "skills/cnki-paper/scripts"))
    import taste_cards
    import taste_judge

    inputs = fixtures()
    registry = taste_cards.load_registry()
    card = taste_cards.card_by_slug(registry, "comparative-politics")
    assert card is not None
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "fixtures.json", inputs)
    summaries = {}
    with tempfile.TemporaryDirectory(prefix="taste-baseline-") as temporary:
        workspace = Path(temporary)
        write_json(workspace / "workflow_config.json", inputs["config"])
        write_json(workspace / "research_decision.json", {"candidates": [inputs["candidate"]]})
        for case in ("published-results", "original-proposals"):
            references_path = workspace / "references.json"
            write_json(references_path, inputs[case])
            with contextlib.redirect_stdout(io.StringIO()):
                status = taste_judge.main([
                    "emit", str(workspace), "--model-revision", "synthetic-capture-no-model-run",
                    "--references", str(references_path), "--out", str(out / case),
                ])
            if status != 0:
                raise RuntimeError(f"baseline emit failed for {case}: {status}")
            plan_path = out / case / f"base.{taste_judge.PLAN_NAME}"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            manifest = json.loads((out / case / "manifest.json").read_text(encoding="utf-8"))
            prompt_files = [out / case / item["prompt_path"] for item in manifest["steps"].values()]
            prompt_text = "\n".join(path.read_text(encoding="utf-8") for path in prompt_files)
            pairs = [pair for item in plan["items"] for pair in item["pairs"]]
            exemplars = [entry for group in card.get("exemplars", {}).values() if isinstance(group, list) for entry in group]
            summaries[case] = {
                "candidate_count": len(plan["items"]),
                "reference_count": len(plan["references"]),
                "pair_count": len(pairs),
                "comparable_pairs": sum(pair.get("comparable") is True for pair in pairs),
                "noncomparable_pairs": sum(pair.get("comparable") is False for pair in pairs),
                "emitted_prompt_count": len(prompt_files),
                "card_exemplar_count": len(exemplars),
                "verbatim_exemplar_explanations_in_emitted_prompts": sum(bool(entry.get("why")) and entry["why"] in prompt_text for entry in exemplars),
                "prompt_bytes": sum(path.stat().st_size for path in prompt_files),
            }
    write_json(out / "input-availability.json", {
        "evidence_kind": "observed dispatch behavior on synthetic fixtures",
        "production_reference_absence_frequency": "not_measured",
        "research_quality_effect": "not_measured",
        "cases": summaries,
    })
    files = sorted(path for path in out.rglob("*") if path.is_file())
    write_json(out / "manifest.json", {
        "source_commit": commit,
        "evidence_kind": "exact CLI prompt capture; synthetic inputs; no model responses",
        "source_sha256": {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in SOURCE_PATHS},
        "capture_sha256": {path.relative_to(out).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
    })
    print(json.dumps(summaries, ensure_ascii=False))


if __name__ == "__main__":
    main()
