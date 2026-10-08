from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "cnki-paper" / "scripts"
TOOLS = REPO / "tools"
for path in (str(SCRIPTS), str(REPO)):
    if path not in sys.path:
        sys.path.insert(0, path)

from avereth_core.stages import STAGES  # noqa: E402
from avereth_core.version import VERSION, WORKFLOW_CONFIG_SCHEMA  # noqa: E402
from tools.legacy_runtime_retirement import contains_legacy_identity, retired_top_levels  # noqa: E402


class AverethV60Evals(unittest.TestCase):
    def test_manifest_and_engine_version_are_synchronized(self) -> None:
        manifest = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(VERSION, manifest["framework_version"])
        self.assertEqual("avereth-workflow-config/v1", WORKFLOW_CONFIG_SCHEMA)

    def test_only_one_exact_eight_state_model_is_public(self) -> None:
        self.assertEqual(8, len(STAGES))
        self.assertEqual("intake", STAGES[0])
        self.assertEqual("output", STAGES[-1])
        self.assertEqual([], retired_top_levels(REPO / "skills"))

    def test_local_build_audit_output_and_package_actions_exist(self) -> None:
        required = (
            "avereth_core/build/run.py",
            "avereth_core/audit/run_all.py",
            "avereth_core/output/run.py",
            "avereth_core/output/translation.py",
            "avereth_core/output/submission.py",
            "avereth_core/output/response.py",
        )
        for relative in required:
            self.assertTrue((SCRIPTS / relative).is_file(), relative)

    def test_installers_delegate_retirement_and_contain_no_live_legacy_identity(self) -> None:
        for name in ("install.ps1", "install.sh"):
            content = (REPO / name).read_text(encoding="utf-8-sig")
            self.assertIn("install_runtime.py", content)
            self.assertIn("-B", content)
            self.assertIn("-X", content)
            self.assertIn("utf8", content)
            self.assertIn("Avereth / CNKI-Paper v7", content)
            self.assertNotIn("Avereth v6", content)
            self.assertFalse(contains_legacy_identity(content), name)
        installer = (REPO / "tools/install_runtime.py").read_text(encoding="utf-8")
        self.assertIn("legacy_runtime_retirement", installer)
        self.assertIn('"backups" / "avereth-v7"', installer)

    def test_output_documentation_requires_two_phase_visual_review(self) -> None:
        skill = (REPO / "skills/cnki-paper/SKILL.source.md").read_text(encoding="utf-8")
        codex_bootstrap = (REPO / "hosts/codex/fragments/skill-bootstrap.md").read_text(
            encoding="utf-8"
        )
        playbook = (REPO / "skills/cnki-paper/references/workflow-playbook.md").read_text(encoding="utf-8")
        for token in ("OUTPUT.QA_REQUIRED", "record-render-qa", "逐页检查", "output_receipt.json"):
            self.assertIn(token, playbook)
        self.assertIn("{{SKILL_HOST_BOOTSTRAP}}", skill)
        self.assertIn("$BundledPython", codex_bootstrap)
        self.assertIn("{{WORKFLOW_PYTHON_CANDIDATES}}", playbook)
        for content in (codex_bootstrap, playbook):
            self.assertIn("$Python", content)
            self.assertNotIn("& python -X utf8", content)
            self.assertNotIn("python $Controller", content)
        self.assertNotIn("python scripts/word_guard.py", playbook)
        self.assertNotIn("final_paper/paper.zh.docx", playbook)


if __name__ == "__main__":
    unittest.main()
