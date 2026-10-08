#!/usr/bin/env python3
"""Create a v6 CNKI-Paper workflow configuration."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from avereth_core.config import (  # noqa: E402
    WORKFLOW_CONFIG_MD_REL,
    validate_workflow_config,
    write_config,
)
from avereth_core.version import VERSION, WORKFLOW_CONFIG_SCHEMA  # noqa: E402


WORKFLOWS = ("rewrite_existing", "build_from_materials")
TASK_PROFILES = (
    "full_paper",
    "topic_selection",
    "research_design",
    "manuscript_audit",
    "manuscript_revision",
)
PUBLICATION_TRACKS = ("cnki-cn", "international-ssci", "mixed")
SCENES = ("journal", "conference", "report_review", "competition")
TOPIC_ORIGIN_MODES = ("direction_first", "workspace_extension", "material_opportunity", "phenomenon_first")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("paper_rewriting_output"))
    parser.add_argument("--workflow", choices=WORKFLOWS, default="rewrite_existing")
    parser.add_argument("--task-profile", choices=TASK_PROFILES, default="full_paper")
    parser.add_argument("--publication-track", choices=PUBLICATION_TRACKS)
    parser.add_argument("--scene", choices=SCENES, default="journal")
    parser.add_argument("--tier", choices=("flash", "pro"), default="flash")
    parser.add_argument("--output-language", choices=("en", "zh"), default="en")
    parser.add_argument("--word-output", choices=("none", "docx"), default="docx")
    parser.add_argument("--pdf-output", choices=("none", "pdf"), default="none")
    parser.add_argument("--word-font-policy", choices=("default", "template", "skip"), default="default")
    parser.add_argument("--citation-mode", choices=("numeric", "author_year", "footnote"), default="numeric")
    parser.add_argument("--prose-mode", choices=("clear", "distinguished"), default="distinguished")
    parser.add_argument(
        "--prose-conditioning", choices=("none", "commonplace", "auto"),
        help="New full papers and substantive revisions default to auto; other profiles default to none.",
    )
    parser.add_argument("--translation-package", choices=("none", "zh"), default="none")
    parser.add_argument("--translation-source", default="")
    parser.add_argument("--translation-coverage-source", default="")
    parser.add_argument("--submission-package", choices=("none", "journal"), default="none")
    parser.add_argument("--submission-source-dir", default="")
    parser.add_argument("--submission-contract", default="")
    parser.add_argument("--submission-required-file", action="append", default=[])
    parser.add_argument("--response-package", choices=("none", "review_response", "rebuttal"), default="none")
    parser.add_argument("--response-source-dir", default="")
    parser.add_argument("--response-review-source", default="")
    parser.add_argument("--response-required-file", action="append", default=[])
    parser.add_argument("--target-name", default="")
    parser.add_argument("--canonical-manuscript", default="")
    parser.add_argument("--materials-dir", default="")
    parser.add_argument("--draft-path", default="")
    parser.add_argument("--user-motivation", default="")
    parser.add_argument("--special-requirement", action="append", default=[])
    parser.add_argument("--topic-origin-mode", choices=TOPIC_ORIGIN_MODES)
    parser.add_argument("--brainstorm-depth", choices=("broad", "focused"))
    parser.add_argument("--current-user-goal", default="")
    parser.add_argument("--direction-field", default="")
    parser.add_argument("--core-problem", default="")
    parser.add_argument("--preferred-contribution", action="append", default=[])
    parser.add_argument("--object-scope", default="")
    parser.add_argument("--must-preserve", action="append", default=[])
    parser.add_argument("--must-avoid", action="append", default=[])
    parser.add_argument("--acceptable-adjacency", choices=("narrow", "medium", "broad"), default="medium")
    parser.add_argument("--method-role", choices=("open", "preferred", "fixed-by-user"), default="open")
    parser.add_argument("--no-interactive", action="store_true")
    return parser.parse_args()


def choose_publication_track(current: str | None, *, interactive: bool) -> str:
    if current in PUBLICATION_TRACKS:
        return str(current)
    if not interactive:
        raise ValueError(
            "--publication-track is required and must be cnki-cn, international-ssci, or mixed"
        )
    print("Publication track:")
    for index, value in enumerate(PUBLICATION_TRACKS, start=1):
        print(f"  {index}. {value}")
    answer = input("Select 1-3: ").strip()
    if answer not in {"1", "2", "3"}:
        raise ValueError("publication track selection is required")
    return PUBLICATION_TRACKS[int(answer) - 1]


def choose_required_text(current: str, *, label: str, interactive: bool) -> str:
    value = str(current or "").strip()
    if value:
        return value
    if not interactive:
        raise ValueError(f"{label} is required for task_profile=topic_selection")
    value = input(f"{label}: ").strip()
    if not value:
        raise ValueError(f"{label} is required for task_profile=topic_selection")
    return value


def build_config(args: argparse.Namespace) -> dict[str, object]:
    track = choose_publication_track(args.publication_track, interactive=not args.no_interactive)
    payload: dict[str, object] = {
        "schema_version": WORKFLOW_CONFIG_SCHEMA,
        "framework_version": VERSION,
        "workflow": args.workflow,
        "task_profile": args.task_profile,
        "publication_track": track,
        "scene": args.scene,
        "tier": args.tier,
        "output_language": args.output_language,
        "word_output": args.word_output,
        "pdf_output": args.pdf_output,
        "word_font_policy": args.word_font_policy,
        "citation_mode": args.citation_mode,
        "prose_mode": args.prose_mode,
        "prose_conditioning": getattr(args, "prose_conditioning", None) or (
            "auto" if args.task_profile in {"full_paper", "manuscript_revision"} else "none"
        ),
        "resource_policy": {
            "max_f1_metadata_queries": 12,
            "max_f2_sample_bytes": 10485760,
            "max_f2_probe_seconds": 120,
        },
        "translation_package": args.translation_package,
        "submission_package": args.submission_package,
        "response_package": args.response_package,
        "target_name": args.target_name,
        "materials_dir": args.materials_dir,
        "user_motivation": args.user_motivation,
        "special_requirements": list(args.special_requirement),
    }
    if args.canonical_manuscript:
        payload["canonical_manuscript"] = args.canonical_manuscript
    if args.draft_path:
        payload["draft_path"] = args.draft_path
    if args.translation_source:
        payload["translation_source"] = args.translation_source
    if args.translation_coverage_source:
        payload["translation_coverage_source"] = args.translation_coverage_source
    if args.submission_source_dir:
        payload["submission_source_dir"] = args.submission_source_dir
    if args.submission_contract:
        payload["submission_contract"] = args.submission_contract
    if args.submission_required_file:
        payload["submission_required_files"] = list(args.submission_required_file)
    if args.response_source_dir:
        payload["response_source_dir"] = args.response_source_dir
    if args.response_review_source:
        payload["response_review_source"] = args.response_review_source
    if args.response_required_file:
        payload["response_required_files"] = list(args.response_required_file)
    if args.task_profile == "topic_selection":
        origin_mode = args.topic_origin_mode or "direction_first"
        brainstorm_depth = args.brainstorm_depth or "broad"
        workspace_policy = (
            "quarantine_until_divergence"
            if origin_mode == "direction_first"
            else "declared_source_from_start"
        )
        current_user_goal = choose_required_text(
            args.current_user_goal or args.user_motivation,
            label="current user goal",
            interactive=not args.no_interactive,
        )
        direction_field = choose_required_text(
            args.direction_field,
            label="discipline and subfield",
            interactive=not args.no_interactive,
        )
        core_problem = choose_required_text(
            args.core_problem,
            label="core problem to explore",
            interactive=not args.no_interactive,
        )
        object_scope = choose_required_text(
            args.object_scope,
            label="acceptable object, level, place, and period scope",
            interactive=not args.no_interactive,
        )
        workspace_role = {
            "direction_first": "optional-after-divergence",
            "workspace_extension": "declared-extension-source",
            "material_opportunity": "declared-material-source",
            "phenomenon_first": "declared-phenomenon-source",
        }[origin_mode]
        payload["topic_selection"] = {
            "origin_mode": origin_mode,
            "brainstorm_depth": brainstorm_depth,
            "workspace_policy": workspace_policy,
        }
        payload["direction_contract"] = {
            "current_user_goal": current_user_goal,
            "field": direction_field,
            "core_problem": core_problem,
            "preferred_contribution": list(args.preferred_contribution or ["open"]),
            "object_scope": object_scope,
            "must_preserve": list(args.must_preserve),
            "must_avoid": list(args.must_avoid),
            "acceptable_adjacency": args.acceptable_adjacency,
            "publication_track": track,
            "method_role": args.method_role,
            "workspace_role": workspace_role,
            "authority": "current-user-request",
        }
    return payload


def render_markdown(config: dict[str, object]) -> str:
    lines = ["# CNKI-Paper Workflow Config", ""]
    for key, value in config.items():
        rendered = ", ".join(str(item) for item in value) if isinstance(value, list) else value
        lines.append(f"- **{key}**: {rendered}")
    lines.append("")
    return "\n".join(lines)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    try:
        config = build_config(args)
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 2
    issues = validate_workflow_config(config)
    if issues:
        print("Configuration error: " + "; ".join(issues))
        return 2
    json_path = write_config(args.output_dir, config)
    md_path = args.output_dir / WORKFLOW_CONFIG_MD_REL
    _atomic_text(md_path, render_markdown(config))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
