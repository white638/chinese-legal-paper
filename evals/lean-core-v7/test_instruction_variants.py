import tempfile
import unittest
from pathlib import Path

from instruction_variants import apply_variant, project

ROOT = Path(__file__).resolve().parents[2]


class InstructionVariantTests(unittest.TestCase):
    def test_current_is_exact_and_lean_preserves_current_hard_contract(self):
        text = (ROOT / "skills/cnki-paper/SKILL.source.md").read_text(encoding="utf-8")
        self.assertEqual(text, project(text, "current"))
        lean = project(text, "lean")
        hard = text.split("## 4.", 1)[1].split("## 5.", 1)[0]
        self.assertIn(hard, lean)
        self.assertIn("reference_requests", lean)
        self.assertIn("topic-selection-protocol.md", lean)
        self.assertLess(len(lean.encode()), len(text.encode()))

    def test_minimal_keeps_integrity_permission_and_completion_boundaries(self):
        text = project("", "minimal")
        for token in ("Direct", "Workspace", "allowed_writes", "ProsePacket", "protected atoms",
                      "negative findings", "user authorization", "current compiler", "transactional output gate"):
            self.assertIn(token, text)

    def test_projection_changes_only_instruction_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill = root / "skills/cnki-paper/SKILL.md"
            skill.parent.mkdir(parents=True)
            source = (ROOT / "skills/cnki-paper/SKILL.source.md").read_bytes()
            skill.write_bytes(source)
            controller = skill.with_name("controller.py")
            controller.write_bytes(b"canonical state unchanged")
            result = apply_variant(root, "lean")
            self.assertNotEqual(result["source_sha256"], result["effective_sha256"])
            self.assertEqual(b"canonical state unchanged", controller.read_bytes())
            self.assertFalse(result["controller_modified"])

    def test_unknown_variant_and_unrecognized_source_fail_closed(self):
        with self.assertRaises(ValueError):
            project("anything", "unreviewed")
        with self.assertRaises(ValueError):
            project("unrecognized skill", "lean")


if __name__ == "__main__":
    unittest.main()
