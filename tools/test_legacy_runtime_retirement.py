from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import legacy_runtime_retirement as retirement


class LegacyRuntimeRetirementTests(unittest.TestCase):
    def test_all_current_agents_are_managed_for_each_host(self) -> None:
        for host, extension in (("codex", ".toml"), ("claude", ".md")):
            with self.subTest(host=host):
                names = retirement.managed_agent_names(host)
                manifest = json.loads((Path(__file__).resolve().parents[1] / "agent-specs/manifest.json").read_text(encoding="utf-8"))
                self.assertEqual({agent["name"] + extension for agent in manifest["agents"]}, set(names))
                self.assertIn("avereth_writer" + extension, names)
                self.assertIn("avereth_adjudicator" + extension, names)

    def test_exact_runtime_is_moved_to_host_specific_recoverable_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temporary = Path(tmp)
            for host, entrypoint_dir in (("codex", "prompts"), ("claude", "commands")):
                with self.subTest(host=host):
                    runtime_home = temporary / f"{host}-home"
                    backup = temporary / f"{host}-backup"
                    skill_name = retirement._RETIRED_TOP_LEVELS[0]
                    retired_skill = runtime_home / "skills" / skill_name
                    retired_entrypoint = runtime_home / entrypoint_dir / retirement._RETIRED_PROMPT
                    retired_agent_name = next(
                        name
                        for name in retirement.retired_agent_names()
                        if name.endswith(".toml" if host == "codex" else ".md")
                    )
                    retired_agent = runtime_home / "agents" / retired_agent_name
                    managed_agent_name = retirement.managed_agent_names(host)[0]
                    managed_agent = runtime_home / "agents" / managed_agent_name
                    scout_name = "avereth_scout" + (".toml" if host == "codex" else ".md")
                    scout_agent = runtime_home / "agents" / scout_name
                    managed_entrypoint = runtime_home / entrypoint_dir / "avereth.md"
                    retired_skill.mkdir(parents=True)
                    retired_entrypoint.parent.mkdir(parents=True)
                    retired_agent.parent.mkdir(parents=True)
                    (retired_skill / "marker.txt").write_text("recover me", encoding="utf-8")
                    retired_entrypoint.write_text("recover entrypoint", encoding="utf-8")
                    retired_agent.write_text("retired agent", encoding="utf-8")
                    managed_agent.write_text("previous managed agent", encoding="utf-8")
                    scout_agent.write_text("previous Scout agent", encoding="utf-8")
                    managed_entrypoint.write_text("previous managed entrypoint", encoding="utf-8")

                    payload = retirement.retire(runtime_home, backup, host)
                    self.assertEqual("PASS", payload["status"])
                    self.assertEqual(host, payload["host"])
                    self.assertEqual(6, len(payload["moved"]))
                    self.assertFalse(retired_skill.exists())
                    self.assertFalse(retired_entrypoint.exists())
                    self.assertFalse(retired_agent.exists())
                    self.assertFalse(managed_agent.exists())
                    self.assertFalse(scout_agent.exists())
                    self.assertEqual("previous Scout agent", (backup / "replaced-agents" / scout_name).read_text(encoding="utf-8"))
                    self.assertFalse(managed_entrypoint.exists())
                    self.assertEqual(
                        "recover me",
                        (backup / "retired-skills" / skill_name / "marker.txt").read_text(encoding="utf-8"),
                    )
                    self.assertEqual(
                        "previous managed entrypoint",
                        (backup / f"replaced-{entrypoint_dir}" / "avereth.md").read_text(encoding="utf-8"),
                    )


if __name__ == "__main__":
    unittest.main()
