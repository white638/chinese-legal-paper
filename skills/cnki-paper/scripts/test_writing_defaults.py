"""New intake defaults are explicit; legacy workspaces remain opt-in."""
from __future__ import annotations

import copy
import sys
import unittest
from unittest.mock import patch

from avereth_core.config import validate_workflow_config
from avereth_core.application.plan_service import build_plan
from avereth_core.tools import intake_wizard


class WritingDefaultsTests(unittest.TestCase):
    def config(self, profile="full_paper", track="mixed", conditioning=None):
        argv = ["intake", "--no-interactive", "--task-profile", profile,
                "--publication-track", track]
        if conditioning is not None:
            argv += ["--prose-conditioning", conditioning]
        with patch.object(sys, "argv", argv):
            return intake_wizard.build_config(intake_wizard.parse_args())

    def test_new_prose_tasks_explicitly_enable_auto_on_all_tracks(self):
        for profile in ("full_paper", "manuscript_revision"):
            for track in ("cnki-cn", "international-ssci", "mixed"):
                with self.subTest(profile=profile, track=track):
                    config = self.config(profile, track)
                    self.assertEqual("auto", config["prose_conditioning"])
                    self.assertEqual([], validate_workflow_config(config))
                    for stage in ("research", "build", "audit"):
                        plan = build_plan({"next_stage": stage, "task_profile": profile,
                                           "publication_track": track}, config)
                        self.assertIn("cnki-paper/references/commonplace-writing.md",
                                      plan["required_references"])

    def test_explicit_modes_override_new_defaults(self):
        for mode in ("none", "commonplace", "auto"):
            config = self.config(conditioning=mode)
            self.assertEqual(mode, config["prose_conditioning"])
            self.assertEqual([], validate_workflow_config(config))

    def test_nonwriting_profile_does_not_acquire_writing_requirements(self):
        for profile in ("research_design", "manuscript_audit"):
            self.assertEqual("none", self.config(profile)["prose_conditioning"])

    def test_reading_legacy_missing_setting_does_not_migrate_it(self):
        config = self.config()
        config.pop("prose_conditioning")
        before = copy.deepcopy(config)
        self.assertEqual([], validate_workflow_config(config))
        plan = build_plan({"next_stage": "build", "task_profile": "full_paper"}, config)
        self.assertNotIn("cnki-paper/references/commonplace-writing.md", plan["required_references"])
        self.assertEqual(before, config)

    def test_none_disables_examples_but_keeps_writing_method(self):
        plan = build_plan({"next_stage": "build", "task_profile": "full_paper"},
                          self.config(conditioning="none"))
        self.assertIn("cnki-paper/references/academic-prose.md", plan["required_references"])
        self.assertIn("cnki-paper/references/rhetorical-architecture.md", plan["required_references"])
        self.assertIn("cnki-paper/references/title-design.md", plan["required_references"])


if __name__ == "__main__":
    unittest.main()
