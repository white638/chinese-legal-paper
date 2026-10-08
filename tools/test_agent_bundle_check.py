#!/usr/bin/env python3
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.agent_bundle_check import (
    DEFAULT_MANIFEST,
    expected_filenames,
    load_contracts,
    validate_agent_bundle,
)
from tools.build_host import _load_replacements, _load_tokens, _render_agents, load_profile
from tools.legacy_runtime_retirement import retired_agent_names


ROOT = Path(__file__).resolve().parents[1]


def render_agents(root: Path, host: str) -> Path:
    profile = load_profile(ROOT, host)
    _render_agents(
        ROOT,
        root,
        profile,
        _load_tokens(ROOT, profile),
        _load_replacements(ROOT, profile),
    )
    return root / "agents"


class AgentBundleCheckTests(unittest.TestCase):
    def test_canonical_contract_contains_all_boundary_agents(self) -> None:
        contracts = load_contracts(DEFAULT_MANIFEST)
        self.assertEqual(9, len(contracts))
        self.assertIn("protected atoms", contracts["avereth_writer"]["phrases"])
        self.assertIn("bridge", contracts["avereth_compressor"]["phrases"])
        self.assertIn("clean read", contracts["avereth_clarity"]["phrases"])

    def test_both_host_formats_and_installed_parity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temporary = Path(temp_dir)
            for host in ("codex", "claude"):
                with self.subTest(host=host):
                    bundle_agents = render_agents(temporary / f"bundle-{host}", host)
                    installed = temporary / f"installed-{host}"
                    shutil.copytree(bundle_agents, installed)
                    self.assertEqual(
                        [],
                        validate_agent_bundle(
                            bundle_agents,
                            installed,
                            host=host,
                            manifest_path=DEFAULT_MANIFEST,
                        ),
                    )
                    self.assertEqual(
                        set(expected_filenames(host)),
                        {path.name for path in bundle_agents.iterdir()},
                    )

    def test_retired_agent_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            agents = render_agents(root, "codex")
            retired = next(name for name in retired_agent_names() if name.endswith(".toml"))
            (agents / retired).write_text("retired", encoding="utf-8")
            errors = validate_agent_bundle(agents, host="codex")
            self.assertTrue(any(retired in item and "retired agent" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
