"""Replay synthetic judgment inputs against an explicitly selected source tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    sys.path.insert(0, str(source / "skills/cnki-paper/scripts"))
    import taste_cards
    import taste_exemplars
    import taste_judge

    registry = taste_cards.load_registry()
    card = taste_cards.card_by_slug(registry, "comparative-politics")
    shortlist = {
        role: [{"record_id": rid, "title": title, "abstract": abstract, "cited_by": citations}]
        for role, rid, title, abstract, citations in (
            ("positive", "SAMPLE-A", "Allocation rules and local compliance", "This synthetic study compares allocation rules and observes compliance under bounded resource conditions.", 900),
            ("negative", "SAMPLE-B", "Recording practices and apparent service success", "This synthetic study examines whether altered recording rules account for apparent improvements in service completion.", 0),
            ("middle", "SAMPLE-C", "Access costs and service uptake", "This synthetic study tests rival explanations of service non-use using administrative and interview materials.", 40),
        )
    }
    candidate = {"id": "CAND-01", "candidate_family": "accountability", "research_question": "When do accountability reforms change local compliance?", "potential_contribution": "Identify scope conditions under which accountability changes observed compliance."}
    reference = {"ref_id": "REF-01", "identifier": "SYNTHETIC-RESULT-01", "title": "Allocation and compliance", "claim": "Resource allocation explains compliance differences in the synthetic study.", "comparison_view": {"maturity": "result", "text": "Allocation and compliance: resource allocation explains differences in the synthetic study."}}
    plan = taste_judge.build_plan(card=card, registry=registry, candidates=[candidate], references=[reference], variant="base")
    outputs = {
        "fixtures.json": json.dumps({"synthetic": True, "shortlist": shortlist, "candidate": candidate, "reference": reference}, ensure_ascii=False, indent=2) + "\n",
        "selection.prompt.md": taste_exemplars.selection_prompt(card, shortlist, pick_positive=1, pick_negative=1),
        "selection.schema.json": json.dumps(taste_exemplars.selection_schema(1, 1), ensure_ascii=False, indent=2) + "\n",
        "judge.prompt.md": taste_judge.judge_prompt(plan, plan["items"][0], card),
        "judge.schema.json": json.dumps(taste_judge.output_schema(1), ensure_ascii=False, indent=2) + "\n",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        (args.out / name).write_bytes(content.encode("utf-8"))
    commit = subprocess.check_output(["git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    paths = ["skills/cnki-paper/scripts/" + name for name in ("taste_exemplars.py", "taste_judge.py", "taste_cards.py", "problem_orientation_check.py", "topic_packet.py")]
    paths.append(str(taste_cards.DEFAULT_REGISTRY.relative_to(source)).replace("\\", "/"))
    manifest = {
        "source_commit": commit,
        "evidence_kind": "synthetic deterministic prompt capture; no model responses",
        "source_sha256": {path: hashlib.sha256((source / path).read_bytes()).hexdigest() for path in paths},
        "capture_sha256": {name: hashlib.sha256(content.encode("utf-8")).hexdigest() for name, content in outputs.items()},
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
