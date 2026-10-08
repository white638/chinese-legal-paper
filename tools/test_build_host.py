from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.agent_bundle_check import validate_agent_bundle
from tools.build_host import build_host
from tools.host_leak_check import validate_host_bundle, validate_source_tree


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HostBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.codex = cls.root / "codex"
        cls.claude = cls.root / "claude"
        build_host(ROOT, "codex", cls.codex)
        build_host(ROOT, "claude", cls.claude)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_layouts_are_host_native(self) -> None:
        self.assertTrue((self.codex / "prompts" / "avereth.md").is_file())
        self.assertFalse((self.codex / "commands").exists())
        self.assertTrue((self.claude / "commands" / "avereth.md").is_file())
        self.assertFalse((self.claude / "prompts").exists())
        self.assertTrue((self.codex / "agents" / "avereth.toml").is_file())
        self.assertTrue((self.claude / "agents" / "avereth.md").is_file())
        self.assertTrue(list((self.codex / "skills").rglob("openai.yaml")))
        self.assertFalse(list((self.claude / "skills").rglob("openai.yaml")))
        self.assertFalse(list((self.codex / "skills").rglob("*.source.md")))
        self.assertFalse(list((self.claude / "skills").rglob("*.source.md")))
        self.assertFalse(list((self.codex / "skills").rglob("test_*.py")))
        self.assertFalse(list((self.claude / "skills").rglob("test_*.py")))

    def test_shared_control_kernel_is_byte_identical(self) -> None:
        relatives = (
            "cnki-paper/scripts/avereth_core/stages.py",
            "cnki-paper/scripts/topic_packet.py",
            "cnki-paper/scripts/research_decision.py",
            "empirical-research/scripts/researcher_dispatch.py",
        )
        for relative in relatives:
            with self.subTest(relative=relative):
                self.assertEqual(
                    digest(self.codex / "skills" / relative),
                    digest(self.claude / "skills" / relative),
                )

    def test_profiles_expose_only_supported_runners(self) -> None:
        codex = json.loads((self.codex / "host_profile.json").read_text(encoding="utf-8"))
        claude = json.loads((self.claude / "host_profile.json").read_text(encoding="utf-8"))
        self.assertEqual(["codex-exec"], codex["allowed_runners"])
        self.assertEqual(["claude-exec", "agent-declared"], claude["allowed_runners"])

    def test_scout_channel_does_not_enable_tools_in_isolated_generation(self) -> None:
        for bundle in (self.codex, self.claude):
            profile = json.loads((bundle / "host_profile.json").read_text(encoding="utf-8"))
            self.assertEqual("primary_search_broker", profile["discovery_channel"]["mode"])
            self.assertFalse(profile["discovery_channel"]["direct_agent_tools"])
            self.assertEqual(["exa.search", "web.search"], profile["discovery_channel"]["allowed_tools"])
            for host in ("codex", "claude"):
                relative = Path("cnki-paper/scripts/avereth_core/hosts") / (host + ".py")
                self.assertEqual(digest(ROOT / "skills" / relative), digest(bundle / "skills" / relative))

    def test_inline_host_fragments_do_not_split_sentences(self) -> None:
        for bundle in (self.codex, self.claude):
            protocol = (bundle / "skills/cnki-paper/references/topic-selection-protocol.md").read_text(encoding="utf-8")
            self.assertNotIn("{{", protocol)
            self.assertIn("host-seal", protocol)
        claude = (self.claude / "skills/cnki-paper/references/topic-selection-protocol.md").read_text(encoding="utf-8")
        self.assertIn("agent-declared", claude)

    def test_three_entries_route_before_workspace_setup(self) -> None:
        for bundle, agent_path, entry_path in (
            (self.codex, "agents/avereth.toml", "prompts/avereth.md"),
            (self.claude, "agents/avereth.md", "commands/avereth.md"),
        ):
            for relative in (agent_path, entry_path, "skills/cnki-paper/SKILL.md"):
                text = (bundle / relative).read_text(encoding="utf-8")
                with self.subTest(host=bundle.name, entry=relative):
                    self.assertLess(text.index("Direct"), text.index("Workspace"))
                    self.assertIn("cnki-paper", text)
            skill = (bundle / "skills/cnki-paper/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("topic-selection-protocol.md", skill)
            self.assertIn("reference_requests", skill)
            for relative in (agent_path, entry_path):
                self.assertIn("SKILL.md", (bundle / relative).read_text(encoding="utf-8"))

    def test_method_adapters_keep_parent_output_authority(self) -> None:
        for bundle in (self.codex, self.claude):
            for name in ("aers-prisma-slr", "aers-thematic-analysis"):
                text = (bundle / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn("only the delegated", text)
                self.assertIn("target-journal contract", text)
                self.assertNotIn("/mnt/", text)
                self.assertLess(len(text.split("description:", 1)[1].splitlines()[0]), 300)

    def test_generated_agent_and_host_contracts_pass(self) -> None:
        self.assertEqual([], validate_source_tree(ROOT))
        for host, bundle in (("codex", self.codex), ("claude", self.claude)):
            with self.subTest(host=host):
                self.assertEqual([], validate_agent_bundle(bundle / "agents", host=host))
                self.assertEqual([], validate_host_bundle(bundle, host))

    def test_output_safety_rejects_repository_root(self) -> None:
        with self.assertRaises(ValueError):
            build_host(ROOT, "codex", ROOT)

    def test_output_safety_preserves_unmanaged_existing_directory(self) -> None:
        unmanaged = self.root / "unmanaged"
        unmanaged.mkdir()
        sentinel = unmanaged / "keep.txt"
        sentinel.write_text("do not replace", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unmanaged non-empty build output"):
            build_host(ROOT, "codex", unmanaged)
        self.assertEqual("do not replace", sentinel.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
