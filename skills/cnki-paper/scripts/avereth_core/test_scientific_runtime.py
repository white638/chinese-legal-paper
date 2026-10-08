from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from avereth_core import cli
from avereth_core.scientific_runtime import (
    scientific_runtime_digest,
    scientific_runtime_issues,
    scientific_runtime_manifest,
)


class ScientificRuntimeTests(unittest.TestCase):
    def test_checked_in_scientific_runtime_manifest_has_no_missing_assets(self) -> None:
        manifest = scientific_runtime_manifest()
        self.assertTrue(manifest)
        self.assertEqual([], [path for path, digest in manifest.items() if digest == "missing"])

    def test_digest_is_path_stable_and_changes_with_runtime_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "methods" / "schema.json"
            second = root / "methods" / "validator.py"
            first.parent.mkdir(parents=True)
            first.write_text('{"version": 1}\n', encoding="utf-8")
            second.write_text("def validate(): return True\n", encoding="utf-8")
            paths = ["methods/validator.py", "methods/schema.json"]

            before = scientific_runtime_digest(root, relative_paths=paths)
            self.assertEqual(
                before,
                scientific_runtime_digest(root, relative_paths=reversed(paths)),
            )
            second.write_text("def validate(): return False\n", encoding="utf-8")
            self.assertNotEqual(
                before,
                scientific_runtime_digest(root, relative_paths=paths),
            )

    def test_missing_runtime_asset_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = scientific_runtime_manifest(
                Path(tmp), relative_paths=["methods/missing.schema.json"]
            )
            self.assertEqual("missing", manifest["methods/missing.schema.json"])

    def test_checked_in_scientific_runtime_has_no_missing_issue(self) -> None:
        self.assertEqual([], scientific_runtime_issues())

    def test_runtime_groups_do_not_bind_unused_method_contracts(self) -> None:
        venue_only = scientific_runtime_manifest(groups={"venue"})
        self.assertIn("journal-fit/references/venue-overlay-registry.json", venue_only)
        self.assertIn(
            "journal-fit/packs/apsr/skills/apsr-data-analysis/SKILL.md",
            venue_only,
        )
        self.assertNotIn(
            "empirical-research/references/method-adapter-registry.json",
            venue_only,
        )
        methods = scientific_runtime_manifest(groups={"methods"})
        self.assertIn(
            "empirical-research/references/method-adapter-registry.json",
            methods,
        )

    def test_manifest_covers_controller_and_transitive_scientific_dependencies(self) -> None:
        research = scientific_runtime_manifest(groups={"research"})
        for relative in (
            "cnki-paper/scripts/avereth_core/cli.py",
            "cnki-paper/scripts/avereth_core/stages.py",
            "cnki-paper/scripts/topic_reasoning_check.py",
            "cnki-paper/scripts/research_quality_check.py",
        ):
            self.assertIn(relative, research)

        methods = scientific_runtime_manifest(groups={"methods"})
        self.assertIn("cnki-paper/scripts/research_design_v2.py", methods)
        self.assertIn(
            "cnki-paper/references/schemas/cnki-research-design-v2.schema.json",
            methods,
        )

    def test_audit_and_output_receipts_bind_scientific_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = scientific_runtime_digest()
            self.assertFalse(cli.write_audit_receipt(root, passed=False))
            audit = json.loads((root / "audit_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(expected, audit["scientific_runtime_digest"])

            self.assertFalse(cli.write_output_receipt(root, passed=False))
            output = json.loads((root / "output_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(expected, output["scientific_runtime_digest"])

    def test_runtime_dependency_change_makes_audit_receipt_stale(self) -> None:
        with tempfile.TemporaryDirectory() as runtime_tmp, tempfile.TemporaryDirectory() as out_tmp:
            runtime_root = Path(runtime_tmp)
            dependency = runtime_root / "cnki-paper/scripts/topic_reasoning_check.py"
            dependency.parent.mkdir(parents=True)
            dependency.write_text("DECISION = 'before'\n", encoding="utf-8")
            relative = ["cnki-paper/scripts/topic_reasoning_check.py"]
            before = scientific_runtime_digest(runtime_root, relative_paths=relative)

            outdir = Path(out_tmp)
            cli.write_audit_receipt(outdir, passed=False)
            receipt_path = outdir / "audit_receipt.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["status"] = "PASS"
            receipt["scientific_runtime_digest"] = before
            receipt_path.write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            dependency.write_text("DECISION = 'after'\n", encoding="utf-8")
            after = scientific_runtime_digest(runtime_root, relative_paths=relative)
            self.assertNotEqual(before, after)
            with mock.patch.object(cli, "scientific_runtime_digest", return_value=after):
                ok, issue = cli.audit_receipt_status(outdir)
            self.assertFalse(ok)
            self.assertIn("scientific method", issue)


if __name__ == "__main__":
    unittest.main()
