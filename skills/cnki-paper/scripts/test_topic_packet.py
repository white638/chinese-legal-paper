#!/usr/bin/env python3
"""Executable counterfactual tests for topic-selection intake and packets."""

from __future__ import annotations

import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
INTAKE_WIZARD = HERE / "avereth_core" / "tools" / "intake_wizard.py"
TOPIC_PACKET = HERE / "topic_packet.py"
WORKFLOW_SCHEMA = (
    HERE.parent / "references" / "schemas" / "avereth-workflow-config-v1.schema.json"
)
PACKET_SCHEMA = (
    HERE.parent / "references" / "schemas" / "avereth-topic-packet-v1.schema.json"
)

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import topic_packet as topic_packet_runtime  # noqa: E402
from test_topic_packet_recon import synthetic_recon  # noqa: E402
from avereth_core.hosts import claude as claude_host  # noqa: E402
from avereth_core.config import (  # noqa: E402
    DIRECTION_CONTRACT_FIELDS,
    validate_workflow_config,
)


class TopicPacketCounterfactualTests(unittest.TestCase):
    maxDiff = None

    def _run(self, *args: object, expected: int = 0) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, *(str(item) for item in args)],
            cwd=HERE,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            expected,
            completed.returncode,
            f"command failed: {completed.args}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        return completed

    def _intake(
        self,
        workspace: Path,
        *,
        core_problem: str = "Why accountability reforms produce divergent institutional responses",
        origin_mode: str | None = None,
        materials_dir: str = "",
        brainstorm_depth: str = "broad",
    ) -> dict:
        args: list[object] = [
            INTAKE_WIZARD,
            "--output-dir",
            workspace,
            "--workflow",
            "build_from_materials",
            "--task-profile",
            "topic_selection",
            "--publication-track",
            "international-ssci",
            "--word-output",
            "none",
            "--pdf-output",
            "none",
            "--current-user-goal",
            "Explore institutional accountability as a sustained research agenda",
            "--direction-field",
            "comparative political economy and public administration",
            "--core-problem",
            core_problem,
            "--preferred-contribution",
            "mechanism explanation",
            "--preferred-contribution",
            "theory revision",
            "--object-scope",
            "public organizations across comparable reforms and periods",
            "--must-avoid",
            "dataset-led variable fishing",
            "--acceptable-adjacency",
            "medium",
            "--method-role",
            "open",
            "--brainstorm-depth",
            brainstorm_depth,
            "--no-interactive",
        ]
        if origin_mode is not None:
            args.extend(["--topic-origin-mode", origin_mode])
        if materials_dir:
            args.extend(["--materials-dir", materials_dir])
        self._run(*args)
        return json.loads((workspace / "workflow_config.json").read_text(encoding="utf-8"))

    def _compile_packet(
        self,
        workspace: Path,
        *,
        output_name: str = "topic_packet.json",
        scope: tuple[str, ...] = (),
        expected: int = 0,
        include_recon: bool = True,
    ) -> dict | None:
        output = workspace / output_name
        args: list[object] = [
            TOPIC_PACKET,
            "compile",
            workspace,
            "--current-user-request",
            "Generate a genuinely diverse portfolio for this research direction",
            "--compiled-at",
            "2026-08-28T12:00:00+00:00",
            "--output",
            output,
        ]
        for item in scope:
            args.extend(["--declared-workspace-scope", item])
        if include_recon:
            recon_path = workspace / "recon-fixture.json"
            recon_path.write_text(json.dumps(synthetic_recon()), encoding="utf-8")
            args.extend(["--recon", recon_path])
        self._run(*args, expected=expected)
        if expected != 0:
            self.assertFalse(output.exists())
            return None
        self._run(TOPIC_PACKET, "validate", output, "--workspace", workspace)
        return json.loads(output.read_text(encoding="utf-8"))

    @staticmethod
    def _plant_anchoring_materials(workspace: Path, suffix: str) -> list[str]:
        sentinels = [
            f"LEAK_PATH_{suffix}",
            f"LEAK_OLD_TOPIC_{suffix}",
            f"LEAK_SOURCE_{suffix}",
            f"LEAK_METHOD_{suffix}",
        ]
        files = {
            workspace / "materials" / f"{sentinels[0]}.csv": f"id,value\n1,{sentinels[2]}\n",
            workspace / "prior_topics" / f"{sentinels[1]}.md": f"# {sentinels[1]}\n",
            workspace / "reference_materials" / f"{sentinels[2]}.txt": sentinels[2],
            workspace / "models" / f"{sentinels[3]}.do": f"* {sentinels[3]}\n",
        }
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return sentinels

    @staticmethod
    def _string_leaves(value: object) -> list[str]:
        if isinstance(value, dict):
            return [
                item
                for key, child in value.items()
                for item in [str(key), *TopicPacketCounterfactualTests._string_leaves(child)]
            ]
        if isinstance(value, list):
            return [
                item
                for child in value
                for item in TopicPacketCounterfactualTests._string_leaves(child)
            ]
        return [value] if isinstance(value, str) else []

    @staticmethod
    def _legacy_packet(packet: dict) -> dict:
        legacy = copy.deepcopy(packet)
        legacy.pop(topic_packet_runtime.RECON_INPUT_KEY)
        legacy["allowed_inputs"].remove(topic_packet_runtime.RECON_INPUT_KEY)
        legacy["packet_sha256"] = topic_packet_runtime.canonical_digest(
            topic_packet_runtime.packet_projection(legacy)
        )
        return legacy

    def test_new_direction_packet_requires_retrieval_before_compile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            config = self._intake(workspace)
            for recon in (None, [], ["not a retrieval entry"]):
                with self.subTest(recon=recon), self.assertRaisesRegex(
                    ValueError, "literature.reconnaissance"
                ):
                    topic_packet_runtime.build_packet(
                        config,
                        current_user_request="Explore the declared research direction",
                        compiled_at="2026-08-28T12:00:00+00:00",
                        literature_reconnaissance=recon,
                    )
            self._compile_packet(workspace, include_recon=False, expected=2)

    def test_compile_rejects_untraceable_or_future_reconnaissance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = self._intake(Path(tmp))
            for field in ("identifier", "retrieved_at"):
                for value in (None, ""):
                    recon = synthetic_recon()
                    recon[0][field] = value
                    with self.subTest(field=field, value=value), self.assertRaisesRegex(
                        ValueError, field
                    ):
                        topic_packet_runtime.build_packet(
                            config,
                            current_user_request="Explore the declared research direction",
                            compiled_at="2026-08-28T12:00:00+00:00",
                            literature_reconnaissance=recon,
                        )
            recon = synthetic_recon()
            recon[0]["retrieved_at"] = "2026-08-29T00:00:00+00:00"
            with self.assertRaisesRegex(ValueError, "cannot follow packet compilation"):
                topic_packet_runtime.build_packet(
                    config,
                    current_user_request="Explore the declared research direction",
                    compiled_at="2026-08-28T12:00:00+00:00",
                    literature_reconnaissance=recon,
                )

    def test_compile_does_not_silently_discard_malformed_retrieval_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._intake(workspace)
            recon_path = workspace / "invalid-recon.json"
            recon_path.write_text(json.dumps([*synthetic_recon(), 7]), encoding="utf-8")
            output = workspace / "topic_packet.json"
            result = self._run(
                TOPIC_PACKET, "compile", workspace,
                "--current-user-request", "Explore the declared research direction",
                "--recon", recon_path, "--output", output, expected=2,
            )
            self.assertIn("must be an object", result.stdout)
            self.assertFalse(output.exists())

    def test_legacy_v1_is_readable_but_cannot_authorize_a_new_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            config = self._intake(workspace)
            packet = self._compile_packet(workspace)
            assert packet is not None
            legacy = self._legacy_packet(packet)
            serialized = json.dumps(legacy, sort_keys=True)
            legacy = json.loads(serialized)
            self.assertEqual([], topic_packet_runtime.validate_packet(legacy, config))
            self.assertEqual(serialized, json.dumps(legacy, sort_keys=True))
            self.assertTrue(topic_packet_runtime.validate_packet(legacy, for_generation=True))

            with self.assertRaisesRegex(ValueError, "legacy packets are read-only"):
                topic_packet_runtime.build_generation_dispatch(
                    legacy, lane_id="core_problem", run_id="fixture-run",
                    model_revision="fixture-model", context_id="fixture-context",
                    dispatched_at="2026-08-28T12:01:00+00:00",
                )
            capture = mock.Mock()
            with self.assertRaisesRegex(ValueError, "legacy packets are read-only"):
                topic_packet_runtime.TopicGenerationScheduler._for_test(
                    legacy, test_capture=capture,
                )
            capture.assert_not_called()
            with self.assertRaisesRegex(ValueError, "legacy packets are read-only"):
                topic_packet_runtime._assemble_seed_seal(
                    legacy, generation_receipts=[], sealed_at="2026-08-28T12:02:00+00:00",
                    scheduler_session_id="fixture-session", scheduler_key_id="fixture-key",
                    key_store=topic_packet_runtime.TopicSchedulerKeyStore(), material_projection=[],
                )

            legacy_path = workspace / "legacy-packet.json"
            legacy_path.write_text(serialized, encoding="utf-8")
            result = self._run(TOPIC_PACKET, "validate", legacy_path)
            self.assertIn("READ_ONLY", result.stdout)
            self._run(TOPIC_PACKET, "validate", legacy_path, "--for-generation", expected=1)
            with mock.patch.object(topic_packet_runtime, "run_codex_exec_isolated") as host_run:
                with redirect_stdout(io.StringIO()) as output:
                    code = topic_packet_runtime.main([
                        "host-seal", str(legacy_path), "--runner", "codex-exec",
                        "--model-revision", "fixture-model", "--lane-id", "core_problem",
                    ])
                self.assertEqual(2, code, output.getvalue())
                host_run.assert_not_called()

    def test_legacy_recon_without_provenance_remains_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._intake(workspace)
            packet = self._compile_packet(workspace)
            assert packet is not None
            for field in ("identifier", "retrieved_at"):
                packet[topic_packet_runtime.RECON_INPUT_KEY][0].pop(field)
            packet["packet_sha256"] = topic_packet_runtime.canonical_digest(
                topic_packet_runtime.packet_projection(packet)
            )
            self.assertEqual([], topic_packet_runtime.validate_packet(json.loads(json.dumps(packet))))
            self.assertTrue(topic_packet_runtime.validate_packet(packet, for_generation=True))

    def test_recon_changes_invalidate_packet_and_dispatch_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            config = self._intake(workspace)
            packet = self._compile_packet(workspace)
            assert packet is not None
            dispatch = topic_packet_runtime.build_generation_dispatch(
                packet, lane_id="core_problem", run_id="fixture-run",
                model_revision="fixture-model", context_id="fixture-context",
                dispatched_at="2026-08-28T12:01:00+00:00",
            )
            self.assertIn(topic_packet_runtime.RECON_INPUT_KEY, dispatch["input_scope"])
            self.assertIn(synthetic_recon()[0]["identifier"], dispatch["prompt"])
            self.assertEqual([], topic_packet_runtime.validate_generation_dispatch(packet, dispatch))
            changed_recon = synthetic_recon()
            changed_recon[0]["claim"] = "A different synthetic conclusion for the same protocol test."
            changed = topic_packet_runtime.build_packet(
                config, current_user_request=packet["current_user_request"],
                compiled_at=packet["compiled_at"], literature_reconnaissance=changed_recon,
            )
            self.assertNotEqual(packet["packet_sha256"], changed["packet_sha256"])
            self.assertTrue(topic_packet_runtime.validate_generation_dispatch(changed, dispatch))

    def test_scheduler_checks_packet_again_before_host_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._intake(workspace)
            packet = self._compile_packet(workspace)
            assert packet is not None
            capture = mock.Mock()
            scheduler = topic_packet_runtime.TopicGenerationScheduler._for_test(
                packet, test_capture=capture,
            )
            scheduler.packet = self._legacy_packet(packet)
            with self.assertRaisesRegex(ValueError, "legacy packets are read-only"):
                scheduler.run(
                    lane_id="core_problem", dispatched_at="2026-08-28T12:01:00+00:00",
                    issued_at="2026-08-28T12:02:00+00:00",
                )
            capture.assert_not_called()

    def test_packet_schema_covers_new_and_legacy_serialized_input_shapes(self) -> None:
        schema = json.loads(PACKET_SCHEMA.read_text(encoding="utf-8"))
        entry_schema = schema["$defs"]["reconEntry"]
        self.assertEqual(topic_packet_runtime.RECON_ENTRY_REQUIRED_KEYS, set(entry_schema["required"]))
        self.assertEqual(
            topic_packet_runtime.RECON_ENTRY_REQUIRED_KEYS | topic_packet_runtime.RECON_ENTRY_OPTIONAL_KEYS,
            set(entry_schema["properties"]),
        )
        self.assertEqual(topic_packet_runtime.RECON_MAX_ENTRIES, schema["properties"]["literature_reconnaissance"]["maxItems"])
        with tempfile.TemporaryDirectory() as tmp:
            for origin in topic_packet_runtime.ORIGIN_MODES:
                with self.subTest(origin=origin):
                    workspace = Path(tmp) / origin
                    config = self._intake(workspace, origin_mode=origin)
                    packet = self._compile_packet(
                        workspace, scope=() if origin == "direction_first" else ("declared.txt",),
                    )
                    assert packet is not None
                    branch = "then" if origin == "direction_first" else "else"
                    input_choices = schema["allOf"][0][branch]["properties"]["allowed_inputs"]["oneOf"]
                    for candidate in (packet, self._legacy_packet(packet)):
                        decoded = json.loads(json.dumps(candidate))
                        self.assertEqual([], topic_packet_runtime.validate_packet(decoded, config))
                        self.assertLessEqual(set(decoded), set(schema["properties"]))
                        self.assertIn({"const": decoded["allowed_inputs"]}, input_choices)

    def test_direction_first_intake_and_packet_ignore_conflicting_workspaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace_a = root / "workspace-alpha"
            workspace_b = root / "workspace-beta"
            sentinels = [
                *self._plant_anchoring_materials(workspace_a, "ALPHA"),
                *self._plant_anchoring_materials(workspace_b, "BETA"),
            ]

            config_a = self._intake(workspace_a)
            config_b = self._intake(workspace_b)
            packet_a = self._compile_packet(workspace_a)
            packet_b = self._compile_packet(workspace_b)

            self.assertEqual(config_a, config_b)
            self.assertIsNotNone(packet_a)
            self.assertIsNotNone(packet_b)
            assert packet_a is not None and packet_b is not None
            self.assertEqual("direction_first", packet_a["origin_mode"])
            self.assertEqual("quarantined", packet_a["material_visibility"])
            self.assertEqual([], packet_a["declared_workspace_scope"])
            self.assertEqual(packet_a, packet_b)
            self.assertEqual(packet_a["packet_sha256"], packet_b["packet_sha256"])

            leak_surface = [
                *self._string_leaves(config_a),
                *self._string_leaves(config_b),
                *self._string_leaves(packet_a),
                *self._string_leaves(packet_b),
            ]
            for forbidden in [*sentinels, str(workspace_a), str(workspace_b)]:
                self.assertFalse(
                    any(forbidden in value for value in leak_surface),
                    f"direction-first intake or packet leaked {forbidden!r}",
                )

    def test_material_opportunity_requires_an_explicit_origin_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            default_workspace = root / "default"
            explicit_workspace = root / "explicit"
            for workspace in (default_workspace, explicit_workspace):
                material = workspace / "reference_materials" / "cfps-sample.csv"
                material.parent.mkdir(parents=True, exist_ok=True)
                material.write_text("pid,wave,outcome\n1,2024,1\n", encoding="utf-8")

            self._intake(default_workspace, materials_dir="reference_materials")
            default_packet = self._compile_packet(default_workspace)
            assert default_packet is not None
            self.assertEqual("direction_first", default_packet["origin_mode"])
            self.assertEqual("quarantined", default_packet["material_visibility"])
            self._compile_packet(
                default_workspace,
                output_name="forbidden_scoped_packet.json",
                scope=("reference_materials/cfps-sample.csv",),
                expected=2,
            )

            self._intake(
                explicit_workspace,
                origin_mode="material_opportunity",
                materials_dir="reference_materials",
            )
            explicit_packet = self._compile_packet(
                explicit_workspace,
                scope=("reference_materials/cfps-sample.csv",),
            )
            assert explicit_packet is not None
            self.assertEqual("material_opportunity", explicit_packet["origin_mode"])
            self.assertEqual("declared_source_from_start", explicit_packet["workspace_policy"])
            self.assertEqual("declared-source", explicit_packet["material_visibility"])
            self.assertEqual(
                ["reference_materials/cfps-sample.csv"],
                explicit_packet["declared_workspace_scope"],
            )

    def test_changing_only_the_direction_changes_packet_semantics_and_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            direction_a = root / "direction-a"
            direction_b = root / "direction-b"
            shared_material = "same-material-sentinel"
            for workspace in (direction_a, direction_b):
                material = workspace / "materials" / "shared.txt"
                material.parent.mkdir(parents=True, exist_ok=True)
                material.write_text(shared_material, encoding="utf-8")

            self._intake(
                direction_a,
                core_problem="Why accountability reforms produce divergent institutional responses",
            )
            self._intake(
                direction_b,
                core_problem="How climate adaptation reorganizes intergovernmental authority",
            )
            packet_a = self._compile_packet(direction_a)
            packet_b = self._compile_packet(direction_b)
            assert packet_a is not None and packet_b is not None

            self.assertNotEqual(
                packet_a["direction_contract_digest"],
                packet_b["direction_contract_digest"],
            )
            self.assertNotEqual(packet_a["packet_sha256"], packet_b["packet_sha256"])
            self.assertNotEqual(packet_a["direction_contract"], packet_b["direction_contract"])

    def test_direction_contract_runtime_and_schemas_share_one_exact_allowlist(self) -> None:
        planted_field = "raw_workspace_material"
        planted_value = "LEAK_PLANTED_MATERIAL_NOT_AUTHORIZED"
        authorized_fields = set(DIRECTION_CONTRACT_FIELDS)

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            config = self._intake(workspace)
            poisoned = copy.deepcopy(config)
            poisoned["direction_contract"][planted_field] = planted_value

            self.assertIn(
                f"direction_contract contains unauthorized fields: {planted_field}",
                validate_workflow_config(poisoned),
            )
            (workspace / "workflow_config.json").write_text(
                json.dumps(poisoned, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self._compile_packet(
                workspace,
                output_name="poisoned-topic-packet.json",
                expected=2,
            )

            for schema_path in (WORKFLOW_SCHEMA, PACKET_SCHEMA):
                with self.subTest(schema=schema_path.name):
                    schema = json.loads(schema_path.read_text(encoding="utf-8"))
                    direction_schema = schema["properties"]["direction_contract"]
                    self.assertFalse(direction_schema["additionalProperties"])
                    self.assertEqual(
                        authorized_fields,
                        set(direction_schema["properties"]),
                    )
                    self.assertEqual(
                        authorized_fields,
                        set(direction_schema["required"]),
                    )

            bounded = topic_packet_runtime.direction_contract_projection(
                poisoned["direction_contract"]
            )
            self.assertEqual(authorized_fields, set(bounded))
            self.assertNotIn(planted_field, bounded)
            self.assertNotIn(planted_value, self._string_leaves(bounded))

            packet = topic_packet_runtime.build_packet(
                config,
                current_user_request="Generate a bounded direction-first portfolio",
                compiled_at="2026-08-28T12:00:00+00:00",
                literature_reconnaissance=synthetic_recon(),
            )
            self.assertNotIn(
                planted_value,
                self._string_leaves(topic_packet_runtime.packet_projection(packet)),
            )
            tampered_packet = copy.deepcopy(packet)
            tampered_packet["direction_contract"][planted_field] = planted_value
            tampered_packet["direction_contract_digest"] = (
                topic_packet_runtime.canonical_digest(
                    tampered_packet["direction_contract"]
                )
            )
            tampered_packet["packet_sha256"] = topic_packet_runtime.canonical_digest(
                topic_packet_runtime.packet_projection(tampered_packet)
            )
            self.assertIn(
                f"direction_contract contains unauthorized fields: {planted_field}",
                topic_packet_runtime.validate_packet(tampered_packet),
            )

    def test_seed_seal_requires_scheduler_receipts_and_rejects_forgery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            config = self._intake(workspace)
            packet = topic_packet_runtime.build_packet(
                config,
                current_user_request="Generate direction-only problem seeds",
                compiled_at="2026-08-28T12:00:00+00:00",
                literature_reconnaissance=synthetic_recon(),
            )
            seeds = [
                {
                    "seed_id": "SEED-01",
                    "candidate_family": "core-mechanism",
                    "problem": "Equivalent reforms produce divergent organizational responses",
                    "anomaly_or_unknown": "Uniform mandates do not explain the observed divergence",
                    "why_it_matters": "The answer changes how accountability reform should be understood",
                    "potential_disconfirmation": "Responses converge once enforcement discretion is measured",
                },
                {
                    "seed_id": "SEED-02",
                    "candidate_family": "boundary-comparison",
                    "problem": "Accountability effects may reverse across administrative levels",
                    "anomaly_or_unknown": "A shared rule can centralize one level and decentralize another",
                    "why_it_matters": "The boundary determines whether the proposed mechanism travels",
                    "potential_disconfirmation": "Comparable levels exhibit the same authority shift",
                },
            ]
            captured_runner_inputs: list[dict[str, object]] = []

            def runner(runner_input: object) -> str:
                self.assertIsInstance(runner_input, dict)
                assert isinstance(runner_input, dict)
                captured_runner_inputs.append(copy.deepcopy(runner_input))
                return json.dumps(seeds, ensure_ascii=False)

            key_store = topic_packet_runtime.TopicSchedulerKeyStore()
            scheduler = topic_packet_runtime.TopicGenerationScheduler._for_test(
                packet,
                test_capture=runner,
                key_store=key_store,
                test_run_id="RUN-DIRECTION-001",
                test_model_revision="fixture-model-v1",
                test_context_id="CTX-DIRECTION-001",
            )
            receipt = scheduler.run(
                lane_id="core_mechanism_boundary",
                dispatched_at="2026-08-28T12:01:00+00:00",
                issued_at="2026-08-28T12:02:00+00:00",
            )
            self.assertEqual(1, len(captured_runner_inputs))
            runner_input = captured_runner_inputs[0]
            self.assertEqual(
                {
                    "packet",
                    "declared_material_projection",
                    "prompt",
                    "protocol",
                },
                set(runner_input),
            )
            self.assertEqual(
                topic_packet_runtime.packet_projection(packet),
                runner_input["packet"],
            )
            self.assertEqual([], runner_input["declared_material_projection"])
            self.assertEqual(
                topic_packet_runtime.canonical_generation_prompt(
                    packet,
                    "core_mechanism_boundary",
                ),
                runner_input["prompt"],
            )
            self.assertEqual(
                topic_packet_runtime.generation_protocol(packet),
                runner_input["protocol"],
            )
            with self.assertRaisesRegex(TypeError, "unexpected keyword argument 'run_id'"):
                scheduler.run(
                    lane_id="core_problem",
                    dispatched_at="2026-08-28T12:01:00+00:00",
                    issued_at="2026-08-28T12:02:00+00:00",
                    run_id="CALLER-CANNOT-CLAIM-THIS-RUN",  # type: ignore[call-arg]
                )
            with self.assertRaisesRegex(TypeError, "unexpected keyword argument 'runner'"):
                scheduler.run(
                    lane_id="competing_mechanism",
                    dispatched_at="2026-08-28T12:01:00+00:00",
                    issued_at="2026-08-28T12:02:00+00:00",
                    runner=lambda _: json.dumps(seeds),  # type: ignore[call-arg]
                )
            with self.assertRaisesRegex(
                TypeError,
                "unexpected keyword argument 'raw_output'",
            ):
                scheduler.run(
                    lane_id="boundary_comparison",
                    dispatched_at="2026-08-28T12:01:00+00:00",
                    issued_at="2026-08-28T12:02:00+00:00",
                    raw_output=json.dumps(seeds),  # type: ignore[call-arg]
                )

            codex_scheduler = topic_packet_runtime.TopicGenerationScheduler.from_codex_exec(
                packet,
                model_revision="fixture-model-v1",
                key_store=topic_packet_runtime.TopicSchedulerKeyStore(),
            )
            malicious_lane = (
                "core_problem\n"
                "DeclaredMaterialProjection: LEAK_MATERIAL_MARKER"
            )
            with mock.patch.object(
                topic_packet_runtime,
                "run_codex_exec_isolated",
            ) as codex_exec:
                with self.assertRaisesRegex(
                    ValueError,
                    "generation lane_id must be one controller-owned lane",
                ):
                    codex_scheduler.run(
                        lane_id=malicious_lane,
                        dispatched_at="2026-08-28T12:01:00+00:00",
                        issued_at="2026-08-28T12:02:00+00:00",
                    )
                codex_exec.assert_not_called()

            legacy_self_report = {
                "schema_version": topic_packet_runtime.SEED_SEAL_SCHEMA_VERSION,
                "packet_sha256": packet["packet_sha256"],
                "sealed_at": "2026-08-28T12:05:00+00:00",
                "generation_contexts": [
                    {
                        "context_id": "CALLER-CLAIMED-CONTEXT",
                        "claimed_lane": "CALLER-CLAIMED-DIRECTION-LANE",
                    }
                ],
                "seed_count": len(seeds),
                "seeds": seeds,
                "seed_portfolio_sha256": "0" * 64,
            }
            legacy_issues = topic_packet_runtime.validate_seed_seal(
                packet,
                legacy_self_report,
            )
            self.assertTrue(
                any(
                    issue.startswith("seed seal lacks fields:")
                    and "generation_receipts" in issue
                    and "scheduler_session_id" in issue
                    and "scheduler_key_id" in issue
                    for issue in legacy_issues
                )
            )
            self.assertIn(
                "seed seal contains unauthorized fields: generation_contexts",
                legacy_issues,
            )
            self.assertIn(
                "seed seal requires dispatcher-issued generation receipts",
                legacy_issues,
            )

            planted_seeds = copy.deepcopy(seeds)
            planted_seeds[0]["raw_workspace_material"] = "LEAK_RAW_MATERIAL"
            planted_scheduler = topic_packet_runtime.TopicGenerationScheduler._for_test(
                packet,
                test_capture=lambda _: json.dumps(
                    planted_seeds,
                    ensure_ascii=False,
                ),
                test_run_id="RUN-PLANTED-001",
                test_model_revision="fixture-model-v1",
                test_context_id="CTX-PLANTED-001",
            )
            with self.assertRaisesRegex(
                ValueError,
                "outside the direction-only seed contract",
            ):
                planted_scheduler.run(
                    lane_id="anomaly_negative_case",
                    dispatched_at="2026-08-28T12:01:00+00:00",
                    issued_at="2026-08-28T12:02:00+00:00",
                )

            foreign_scheduler = topic_packet_runtime.TopicGenerationScheduler._for_test(
                packet,
                test_capture=lambda _: "[]",
            )
            with self.assertRaisesRegex(
                ValueError,
                "unknown to this scheduler ledger",
            ):
                foreign_scheduler.seal(
                    generation_receipts=[receipt],
                    sealed_at="2026-08-28T12:05:00+00:00",
                )

            tampered_receipt = copy.deepcopy(receipt)
            signature = tampered_receipt["signature"]
            tampered_receipt["signature"] = (
                ("0" if signature[0] != "0" else "1") + signature[1:]
            )
            with self.assertRaisesRegex(
                ValueError,
                "scheduler signature does not match",
            ):
                scheduler.seal(
                    generation_receipts=[tampered_receipt],
                    sealed_at="2026-08-28T12:05:00+00:00",
                )

            seal = scheduler.seal(
                generation_receipts=[receipt],
                sealed_at="2026-08-28T12:05:00+00:00",
            )
            self.assertNotIn("scheduler_replay_key", seal)
            self.assertNotIn("key_b64", self._string_leaves(seal))
            self.assertEqual(
                [],
                topic_packet_runtime.validate_seed_seal(
                    packet,
                    seal,
                    key_store=key_store,
                ),
            )
            unknown_key_seal = copy.deepcopy(seal)
            unknown_key_seal["scheduler_key_id"] = "TOPIC-KEY-" + ("0" * 32)
            unknown_key_seal["seed_portfolio_sha256"] = (
                topic_packet_runtime.canonical_digest(
                    topic_packet_runtime.seed_seal_projection(unknown_key_seal)
                )
            )
            unknown_key_issues = topic_packet_runtime.validate_seed_seal(
                packet,
                unknown_key_seal,
                key_store=topic_packet_runtime.TopicSchedulerKeyStore(),
            )
            self.assertIn(
                "seed seal scheduler key is unavailable from the controlled key store",
                unknown_key_issues,
            )
            self.assertIn(
                "generation_receipts[0] belongs to a different scheduler key",
                unknown_key_issues,
            )
            with self.assertRaisesRegex(ValueError, "already been consumed"):
                scheduler.seal(
                    generation_receipts=[receipt],
                    sealed_at="2026-08-28T12:06:00+00:00",
                )

    def test_seed_seal_renumbers_colliding_lane_seed_identities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            config = self._intake(workspace)
            packet = topic_packet_runtime.build_packet(
                config,
                current_user_request="Generate direction-only problem seeds",
                compiled_at="2026-08-28T12:00:00+00:00",
                literature_reconnaissance=synthetic_recon(),
            )

            def lane_seeds(family: str, marker: str) -> list[dict[str, str]]:
                return [
                    {
                        "seed_id": f"SEED-{index:02d}",
                        "candidate_family": family,
                        "problem": f"{marker} problem statement number {index}",
                        "anomaly_or_unknown": f"{marker} anomaly awaiting explanation {index}",
                        "why_it_matters": f"{marker} stakes for the declared direction {index}",
                        "potential_disconfirmation": f"{marker} observation that refutes it {index}",
                    }
                    for index in (1, 2)
                ]

            lane_order = ["core_problem", "competing_mechanism"]
            outputs = {
                "core_problem": lane_seeds("core-problem", "Core"),
                "competing_mechanism": lane_seeds("competing-mechanism", "Rival"),
            }
            dispatched: list[str] = []

            def capture(bounded_input: Mapping[str, object]) -> object:
                lane = lane_order[len(dispatched)]
                dispatched.append(lane)
                return topic_packet_runtime.HostCapture(
                    raw_output=json.dumps(
                        outputs[lane],
                        ensure_ascii=False,
                    ).encode("utf-8"),
                    run_id=f"RUN-{lane}",
                    model_revision="fixture-model-v1",
                    context_id=f"CTX-{lane}",
                )

            key_store = topic_packet_runtime.TopicSchedulerKeyStore()
            scheduler = topic_packet_runtime.TopicGenerationScheduler(
                packet,
                capability=topic_packet_runtime._ControlledGenerationCapability(
                    capture,
                    _token=topic_packet_runtime._CAPABILITY_TOKEN,
                ),
                key_store=key_store,
                material_projection=[],
                _token=topic_packet_runtime._SCHEDULER_CONSTRUCTION_TOKEN,
            )
            receipts = [
                scheduler.run(
                    lane_id=lane,
                    dispatched_at="2026-08-28T12:01:00+00:00",
                    issued_at="2026-08-28T12:02:00+00:00",
                )
                for lane in lane_order
            ]
            for receipt, lane in zip(receipts, lane_order):
                self.assertEqual(
                    ["SEED-01", "SEED-02"],
                    [seed["seed_id"] for seed in receipt["seeds"]],
                    f"receipt for {lane} must keep the lane's raw seed identities",
                )

            seal = scheduler.seal(
                generation_receipts=receipts,
                sealed_at="2026-08-28T12:05:00+00:00",
            )
            self.assertEqual(
                ["SEED-01", "SEED-02", "SEED-03", "SEED-04"],
                [seed["seed_id"] for seed in seal["seeds"]],
            )
            receipt_union = [
                dict(seed)
                for receipt in receipts
                for seed in receipt["seeds"]
            ]
            for sealed_seed, receipt_seed in zip(seal["seeds"], receipt_union):
                expected = dict(receipt_seed)
                expected["seed_id"] = sealed_seed["seed_id"]
                self.assertEqual(expected, sealed_seed)
            self.assertEqual(
                [],
                topic_packet_runtime.validate_seed_seal(
                    packet,
                    seal,
                    key_store=key_store,
                ),
            )

            unrenumbered = copy.deepcopy(seal)
            unrenumbered["seeds"] = receipt_union
            unrenumbered["seed_portfolio_sha256"] = (
                topic_packet_runtime.canonical_digest(
                    topic_packet_runtime.seed_seal_projection(unrenumbered)
                )
            )
            self.assertIn(
                "seed seal seeds must be derived exactly from its generation receipts",
                topic_packet_runtime.validate_seed_seal(
                    packet,
                    unrenumbered,
                    key_store=key_store,
                ),
            )

    def test_agent_capture_round_trip_binds_prompt_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "captures"
            prompt = "Generate direction-only question seeds for one controlled lane."
            topic_packet_runtime.write_agent_capture_request(
                directory,
                step="core_mechanism_boundary",
                prompt=prompt,
                output_schema={"type": "array"},
                model_revision="declared-session-model-v1",
            )
            manifest = json.loads(
                (directory / "manifest.json").read_text(encoding="utf-8")
            )
            entry = manifest["steps"]["core_mechanism_boundary"]
            prompt_text = (directory / entry["prompt_path"]).read_text(encoding="utf-8")
            self.assertIn(prompt, prompt_text)
            self.assertIn("ONLY a JSON value", prompt_text)
            with self.assertRaisesRegex(ValueError, "response is missing"):
                topic_packet_runtime.read_agent_capture(
                    directory,
                    prompt=prompt,
                    model_revision="declared-session-model-v1",
                )
            (directory / entry["response_path"]).write_text(
                '```json\n[{"seed_id": "SEED-01"}]\n```',
                encoding="utf-8",
            )
            (directory / entry["context_path"]).write_text(
                "agent-context-01",
                encoding="utf-8",
            )
            capture = topic_packet_runtime.read_agent_capture(
                directory,
                prompt=prompt,
                model_revision="declared-session-model-v1",
            )
            self.assertEqual(
                [{"seed_id": "SEED-01"}],
                json.loads(capture.raw_output.decode("utf-8")),
            )
            self.assertEqual("agent-context-01", capture.context_id)
            self.assertTrue(capture.run_id.startswith("AGENT-DECLARED-"))
            with self.assertRaisesRegex(ValueError, "different model revision"):
                topic_packet_runtime.read_agent_capture(
                    directory,
                    prompt=prompt,
                    model_revision="another-model-v2",
                )
            with self.assertRaisesRegex(
                ValueError, "do not cover the current canonical prompt"
            ):
                topic_packet_runtime.read_agent_capture(
                    directory,
                    prompt=prompt + " changed",
                    model_revision="declared-session-model-v1",
                )
            original_response_path = entry["response_path"]
            entry["response_path"] = "../outside.json"
            (directory / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "path binding is invalid"):
                topic_packet_runtime.read_agent_capture(
                    directory,
                    prompt=prompt,
                    model_revision="declared-session-model-v1",
                )
            entry["response_path"] = original_response_path
            (directory / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            (directory / entry["prompt_path"]).write_text(
                "tampered prompt\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "prompt no longer matches"):
                topic_packet_runtime.read_agent_capture(
                    directory,
                    prompt=prompt,
                    model_revision="declared-session-model-v1",
                )

    def test_claude_exec_adapter_is_schema_bound_and_tool_disabled(self) -> None:
        events = (
            {"type": "system", "session_id": "claude-context-01"},
            {
                "type": "result",
                "session_id": "claude-context-01",
                "is_error": False,
                "result": "```json\n[{\"seed_id\": \"SEED-01\"}]\n```",
            },
        )
        completed = subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout="\n".join(json.dumps(item) for item in events),
            stderr="",
        )
        with mock.patch.object(claude_host.shutil, "which", return_value="claude"), mock.patch.object(
            claude_host.subprocess, "run", return_value=completed
        ) as runner:
            capture = claude_host.run_claude_exec_isolated(
                prompt="Generate one seed.",
                output_schema={"type": "array"},
                model_revision="claude-model-v1",
            )
        command = runner.call_args.args[0]
        self.assertIn("--strict-mcp-config", command)
        self.assertIn("--disallowedTools", command)
        self.assertIn("Read", command[command.index("--disallowedTools") + 1])
        self.assertEqual("Generate one seed.", runner.call_args.kwargs["input"])
        self.assertEqual("claude-context-01", capture.context_id)
        self.assertEqual("claude-model-v1", capture.model_revision)
        self.assertTrue(capture.run_id.startswith("CLAUDE-RUN-"))
        self.assertEqual(
            [{"seed_id": "SEED-01"}],
            json.loads(capture.raw_output.decode("utf-8")),
        )


if __name__ == "__main__":
    unittest.main()
