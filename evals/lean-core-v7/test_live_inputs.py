"""Exercise actual CI Python blocks with no credentials or model execution."""
import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class LiveInputTests(unittest.TestCase):
    def setUp(self):
        workflow = Path(__file__).resolve().parents[2] / ".github/workflows/live-evals.yml"
        self.blocks = [textwrap.dedent(block) for block in re.findall(r"(?ms)^          python - <<'PY'\n(.*?)^          PY$", workflow.read_text(encoding="utf-8"))]
        self.assertEqual(2, len(self.blocks))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.environment = {"SCOPE": "targeted", "TAGS": "prose,claim-evidence", "EXCLUDE_TAGS": "quantitative",
                            "BASELINE_REF": "a" * 40, "MAX_CASES": "3", "REPEAT_ON_UNCERTAIN": "1",
                            "INPUT_REPOSITORY": "", "INPUT_REF": "", "INPUT_TOKEN": "", "OPENAI_API_KEY": "", "SMOKE_MODEL": "",
                            "GITHUB_OUTPUT": str(self.root / "outputs"), "GITHUB_STEP_SUMMARY": str(self.root / "summary")}

    def test_unconfigured_execution_is_not_run_and_makes_no_subprocess_call(self):
        with patch.dict(os.environ, self.environment), patch("subprocess.run") as run:
            exec(compile(self.blocks[0], "live-configure", "exec"), {})
        self.assertIn("ready=false", (self.root / "outputs").read_text())
        self.assertIn("Model calls: 0", (self.root / "summary").read_text())
        run.assert_not_called()

    def test_injected_ref_and_out_of_range_repeat_are_rejected(self):
        for changed in ({"BASELINE_REF": "$(touch injected)"}, {"REPEAT_ON_UNCERTAIN": "3"}, {"MAX_CASES": "100"}, {"TAGS": "prose\nready=true"}):
            with patch.dict(os.environ, {**self.environment, **changed}), patch("subprocess.run") as run:
                with self.assertRaises(SystemExit):
                    exec(compile(self.blocks[0], "live-configure", "exec"), {})
            run.assert_not_called()

    def test_selected_parameters_reach_actual_runner_argv(self):
        calls = []
        def fake_run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=2 if "paired_run.py" in " ".join(argv) else 0, stdout="skills/cnki-paper/references/academic-prose.md\n")
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            with patch.dict(os.environ, self.environment), patch("subprocess.run", side_effect=fake_run):
                with self.assertRaises(SystemExit):
                    exec(compile(self.blocks[1], "live-execution", "exec"), {})
        finally:
            os.chdir(previous)
        command = calls[-1]
        for flag, expected in (("--scope", "targeted"), ("--tags", "prose,claim-evidence"), ("--exclude-tags", "quantitative"),
                               ("--max-cases", "3"), ("--repeat-on-uncertain", "1"), ("--baseline-ref", "a" * 40)):
            self.assertEqual(expected, command[command.index(flag) + 1])
        self.assertIn("--changed-paths", command)


if __name__ == "__main__":
    unittest.main()
