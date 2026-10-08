from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import threading
import unittest
from unittest import mock

from avereth_core import cli
from avereth_core.application.delegation import (
    BRIEF_SCHEMA, RESULT_SCHEMA, capture_candidates, delegation_policy, digest,
    load_discovery_context, public_url, validate_candidate_result)
from avereth_core.application.plan_service import build_plan, plan_markdown
from avereth_core.hosts.discovery import PublicDiscoveryBroker


class DelegationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = {"delegation_policy": {"scout_enabled": True}}
        self.status = {"next_stage": "acquisition", "publication_track": "mixed"}
        self.brief = {"schema_version": BRIEF_SCHEMA, "public_query_authorized": True,
            "question": "Why do comparable public institutions diverge?",
            "partitions": [{"id": "counterexamples", "objective": "Find published counterexamples",
                "purpose": "counterevidence", "queries": ["public institutions divergence counterexamples"],
                "tool": "exa.search"}]}
        self.write_brief()
        (self.root / "workflow_config.json").write_text(json.dumps(self.config), encoding="utf-8")

    def write_brief(self):
        (self.root / "brief.json").write_text(json.dumps(self.brief), encoding="utf-8")

    def plan(self, **kwargs):
        return build_plan(kwargs.pop("status", self.status), kwargs.pop("config", self.config),
                          discovery_context=load_discovery_context(self.root, "brief.json"), **kwargs)

    def request(self):
        return self.plan()["delegation_requests"][0]

    def result(self, request=None):
        request = request or self.request()
        return PublicDiscoveryBroker({"exa.search": lambda query: [
            {"url": "https://example.org/paper", "title": "A counterexample", "snippet": "Search summary only."}
        ]}).discover(request)

    def test_plan_is_pure_stable_and_default_off(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(self.plan(), self.plan())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        off = self.plan(config={})
        self.assertEqual([], off["delegation_requests"])
        self.assertNotIn("cnki-paper/references/delegation.md", off["required_references"])
        self.assertEqual([], build_plan({"next_stage": "intake"})["delegation_requests"])
        self.assertIn("counterexamples", plan_markdown(self.plan()))

    def test_only_public_payload_enters_scout_context(self):
        request = self.request()
        self.assertNotIn("authority_hashes", request["public_task"])
        self.assertNotIn("workflow_config.json", json.dumps(request["public_task"]))
        self.assertEqual([], request["allowed_writes"])
        self.assertEqual("primary_search_broker_only", request["isolation"]["tool_access"])

    def test_checkpoint_and_later_stages_do_not_delegate(self):
        for stage in ("intake", "design", "build", "audit", "output", "blocked", "complete"):
            self.assertEqual([], self.plan(status={"next_stage": stage})["delegation_requests"])
        self.assertEqual([], self.plan(status={"next_stage": "research",
            "next_checkpoint": "question_confirmation"})["delegation_requests"])
        self.assertEqual([], self.plan(status={"next_stage": "research"},
            reference_action="critical-reading")["delegation_requests"])

    def test_invalid_policy_fails_closed(self):
        for raw in ({"scout_enabled": "false"}, {"max_active": 4}, {"max_active": True},
                    {"max_tool_retries": 2}, {"max_candidates": 0}, {"other": True}, []):
            with self.subTest(policy=raw), self.assertRaises(ValueError):
                delegation_policy({"delegation_policy": raw})

    def test_missing_public_authorization_blocks(self):
        self.brief["public_query_authorized"] = False
        self.write_brief()
        with self.assertRaisesRegex(ValueError, "authorization"):
            self.plan()

    def test_duplicate_partitions_queries_and_unknown_tools_block(self):
        self.brief["partitions"].append({**self.brief["partitions"][0], "id": "different"})
        self.write_brief()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.plan()
        self.brief["partitions"].pop()
        self.brief["partitions"][0]["tool"] = "shell"
        self.write_brief()
        with self.assertRaisesRegex(ValueError, "approved"):
            self.plan()

    def test_paths_cannot_escape(self):
        for path in ("../brief.json", str(self.root / "brief.json"), "C:/private.txt"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                load_discovery_context(self.root, path)

    def test_input_hash_changes_invalidate_request_identity_and_acceptance(self):
        request = self.request()
        result = self.result(request)
        # Creation of a formerly absent source registry also counts as drift.
        (self.root / "literature_registry.json").write_text("{}", encoding="utf-8")
        current = self.request()
        self.assertNotEqual(current["request_id"], request["request_id"])
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_candidate_result(current, result)
        with self.assertRaisesRegex(ValueError, "drift"):
            capture_candidates(self.root, request, result)

    def test_brief_drift_blocks_capture(self):
        request = self.request()
        result = self.result(request)
        self.brief["question"] += " Changed scope."
        self.write_brief()
        with self.assertRaisesRegex(ValueError, "brief changed"):
            capture_candidates(self.root, request, result)

    def test_capture_is_idempotent_and_preserves_canonical_files(self):
        request, result = self.request(), self.result()
        before = (self.root / "workflow_config.json").read_bytes()
        first = capture_candidates(self.root, request, result)
        second = capture_candidates(self.root, request, result)
        self.assertEqual("captured_candidates", first["status"])
        self.assertEqual("already_captured", second["status"])
        self.assertEqual(1, len(list((self.root / "discovery_candidates").glob("*.json"))))
        self.assertEqual(before, (self.root / "workflow_config.json").read_bytes())
        self.assertFalse((self.root / "literature_registry.json").exists())
        altered = deepcopy(result)
        altered["gaps"] = ["Full text not acquired."]
        with self.assertRaisesRegex(ValueError, "different result"):
            capture_candidates(self.root, request, altered)

    def test_candidate_cannot_be_promoted_or_fabricated(self):
        for edit in ("status", "url", "extra", "query"):
            request, result = self.request(), self.result()
            if edit == "status":
                result["candidates"][0]["evidence_status"] = "verified"
            elif edit == "extra":
                result["trace_id"] = "not part of candidate artifact"
            else:
                result["candidates"][0][edit] = "https://fabricated.example/paper"
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                validate_candidate_result(request, result)

    def test_invalid_tool_transcript_and_excessive_retry_are_rejected(self):
        request, result = self.request(), self.result()
        result["search_log"][0]["tool"] = "write"
        with self.assertRaisesRegex(ValueError, "unauthorized"):
            validate_candidate_result(request, result)
        result = self.result()
        result["search_log"] *= 3
        with self.assertRaises(ValueError):
            validate_candidate_result(request, result)

    def test_empty_search_is_valid_but_unattempted_query_needs_gap(self):
        request = self.request()
        result = PublicDiscoveryBroker({"exa.search": lambda query: []}).discover(request)
        self.assertEqual([], result["candidates"])
        validate_candidate_result(request, result)
        result["search_log"] = []
        with self.assertRaisesRegex(ValueError, "gap"):
            validate_candidate_result(request, result)

    def test_temporary_error_retries_once_and_preserves_failure(self):
        calls = []
        def search(query):
            calls.append(query)
            if len(calls) == 1:
                raise TimeoutError()
            return []
        result = PublicDiscoveryBroker({"exa.search": search}).discover(self.request())
        self.assertEqual(2, len(calls))
        self.assertEqual(["temporary_error", "success"], [e["status"] for e in result["search_log"]])

    def test_retry_exhaustion_and_permanent_failure_return_gaps(self):
        for error, expected in ((TimeoutError, 2), (PermissionError, 1)):
            with self.subTest(error=error):
                search = mock.Mock(side_effect=error())
                result = PublicDiscoveryBroker({"exa.search": search}).discover(self.request())
                self.assertEqual(expected, search.call_count)
                self.assertTrue(result["gaps"])

    def test_bad_adapter_hit_preserves_failure_without_partial_candidates(self):
        search = lambda query: [{"url": "https://example.org/a", "title": "A", "snippet": ""},
                                {"url": "file:///private", "title": "B", "snippet": ""}]
        result = PublicDiscoveryBroker({"exa.search": search}).discover(self.request())
        self.assertEqual([], result["candidates"])
        self.assertEqual("blocked", result["search_log"][0]["status"])
        self.assertTrue(result["gaps"])

    def test_no_adapter_no_recursion_and_unauthorized_capability(self):
        request = self.request()
        with self.assertRaisesRegex(ValueError, "unavailable"):
            PublicDiscoveryBroker({}).discover(request)
        with self.assertRaisesRegex(ValueError, "recursive"):
            PublicDiscoveryBroker({}).discover(request, parent_depth=1)
        request["public_task"]["tool"] = "delete"
        request["allowed_tools"] = ["delete"]
        request.pop("request_id")
        request["request_id"] = "scout-" + digest(request)
        search = mock.Mock()
        with self.assertRaisesRegex(ValueError, "tool scope"):
            PublicDiscoveryBroker({"delete": search}).discover(request)
        search.assert_not_called()

    def test_concurrency_cap_does_not_silently_discard_tasks(self):
        entered = threading.Event()
        release = threading.Event()
        def search(query):
            entered.set()
            if not release.wait(timeout=5):
                raise TimeoutError()
            return []
        self.config["delegation_policy"]["max_active"] = 1
        request = self.request()
        broker = PublicDiscoveryBroker({"exa.search": search})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(broker.discover, request)
            self.assertTrue(entered.wait(timeout=5))
            try:
                with self.assertRaisesRegex(ValueError, "concurrency"):
                    broker.discover(request)
            finally:
                release.set()
            self.assertEqual([], future.result()["candidates"])
        self.assertEqual([], broker.discover(request)["candidates"])

    def test_host_factory_requires_explicit_supported_channel(self):
        channel = {"mode": "primary_search_broker", "allowed_tools": ["exa.search", "web.search"],
                   "direct_agent_tools": False, "context": "fresh_no_parent_history"}
        for host in ("codex", "claude"):
            with self.subTest(host=host), mock.patch("avereth_core.hosts.discovery.active_host_profile",
                    return_value={"host_id": host, "discovery_channel": channel}):
                broker = PublicDiscoveryBroker.from_host({"exa.search": lambda query: []})
                self.assertEqual([], broker.discover(self.request())["candidates"])
                with self.assertRaisesRegex(ValueError, "approved"):
                    PublicDiscoveryBroker.from_host({"shell": lambda query: []})
        for invalid in (None, {**channel, "direct_agent_tools": True}, {**channel, "context": "fork"}):
            with self.subTest(channel=invalid), mock.patch("avereth_core.hosts.discovery.active_host_profile",
                    return_value={"discovery_channel": invalid}), self.assertRaisesRegex(ValueError, "channel"):
                PublicDiscoveryBroker.from_host({"exa.search": lambda query: []})

    def test_invalid_budget_is_rejected_before_search(self):
        for edit in ("calls", "query", "duplicate"):
            request = self.request()
            if edit == "calls":
                request["budget"]["max_tool_calls"] = 0
            elif edit == "query":
                request["public_task"]["queries"] = [[]]
            else:
                request["public_task"]["queries"] *= 2
            request.pop("request_id")
            request["request_id"] = "scout-" + digest(request)
            search = mock.Mock()
            with self.subTest(edit=edit), self.assertRaisesRegex(ValueError, "budget"):
                PublicDiscoveryBroker({"exa.search": search}).discover(request)
            search.assert_not_called()

    def test_capture_bounds_apply_to_logs_and_gaps(self):
        request, result = self.request(), self.result()
        result["gaps"] = ["x" * 2001]
        with self.assertRaisesRegex(ValueError, "gaps"):
            validate_candidate_result(request, result)
        result = self.result()
        result["search_log"][0]["hits"] *= request["budget"]["max_candidates"] + 1
        with self.assertRaisesRegex(ValueError, "capture"):
            validate_candidate_result(request, result)

    def test_risk_route_is_referenced_not_recomputed_or_reduced(self):
        dispatch = {"mode": "isolated_multi", "minimum_runs": 5, "reason_codes": ["high_risk"]}
        protocol = {"valid": True, "design_sha256": "a" * 64, "runnable_action_ids": ["STEP-001"],
            "work_items": [{"id": "STEP-001", "runnable": True, "researcher_dispatch": dispatch,
                "read_set": ["frozen.csv"], "preconditions": [{"step_id": "STEP-000"}],
                "failure_route": "reopen_design"}]}
        plan = build_plan({"next_stage": "execution"}, {}, protocol=protocol, granularity="operation")
        request = plan["delegation_requests"][0]
        self.assertEqual(dispatch, request["researcher_dispatch"])
        self.assertIsNot(dispatch, request["researcher_dispatch"])
        self.assertEqual(["frozen.csv"], request["input_artifacts"])
        self.assertFalse(request["dispatch_ready"])
        protocol["valid"] = False
        self.assertEqual([], build_plan({"next_stage": "execution"}, {}, protocol=protocol,
            granularity="operation")["delegation_requests"])

    def test_urls_reject_local_credentials_and_nonweb_schemes(self):
        for url in ("file:///secret", "https://localhost/x", "https://127.0.0.1",
                    "https://10.0.0.1", "https://user:pass@example.org", "https://server"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                public_url(url)

    def test_cli_dry_run_apply_replay_and_stage_drift(self):
        request, result = self.request(), self.result()
        path = self.root / "result.json"
        path.write_text(json.dumps(result), encoding="utf-8")
        skills = Path(cli.__file__).resolve().parents[3]
        argv = ["avereth", "--skills-dir", str(skills), "scout-capture", str(self.root),
                "--discovery-brief", "brief.json", "--request-id", request["request_id"],
                "--result", str(path)]
        def invoke(args, status):
            with mock.patch.object(sys, "argv", args), mock.patch.object(cli, "status_payload", return_value=(status, 0)), \
                 mock.patch.object(cli, "read_config", return_value=SimpleNamespace(payload=self.config)), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return cli.main()
        self.assertEqual(0, invoke(argv, self.status))
        self.assertFalse((self.root / "discovery_candidates").exists())
        self.assertEqual(0, invoke(argv + ["--apply"], self.status))
        self.assertEqual(0, invoke(argv + ["--apply"], self.status))
        self.assertEqual(2, invoke(argv + ["--apply"], {"next_stage": "design"}))

    def test_cli_missing_brief_reports_failure_without_writes(self):
        skills = Path(cli.__file__).resolve().parents[3]
        argv = ["avereth", "--skills-dir", str(skills), "plan", str(self.root),
                "--discovery-brief", "missing.json", "--json"]
        before = set(self.root.iterdir())
        with mock.patch.object(sys, "argv", argv), mock.patch.object(cli, "status_payload", return_value=(self.status, 0)), \
             mock.patch.object(cli, "read_config", return_value=SimpleNamespace(payload=self.config, path=self.root)), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, cli.main())
        self.assertEqual(before, set(self.root.iterdir()))

if __name__ == "__main__":
    unittest.main()
