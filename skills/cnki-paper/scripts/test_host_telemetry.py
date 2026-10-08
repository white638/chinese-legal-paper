"""Synthetic host streams verify diagnostic preservation and authority isolation."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from avereth_core.hosts import claude, codex
from avereth_core.hosts.base import HostCapture
from avereth_core.hosts.runtime_observation import observe_controller, observe_gate
from avereth_core.hosts.telemetry import HostObservation, host_measurements


EVENTS = [
    {"type": "thread.started", "thread_id": "test-context"},
    {"type": "turn.completed", "usage": {"input_tokens": 15, "output_tokens": 4}},
]


class HostTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("AVERETH_TELEMETRY_DIR", None)
        self.addCleanup(self.env.stop)

    def run_codex(self, events=EVENTS, raw=None):
        def run(command, **kwargs):
            Path(command[command.index("--output-last-message") + 1]).write_text('{"ok":true}', encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, raw if raw is not None else "\n".join(map(json.dumps, events)), "host warning")
        with mock.patch.object(codex.subprocess, "run", side_effect=run):
            return codex.run_codex_exec_isolated(prompt="test", output_schema={"type": "object"}, model_revision="test-model")

    def test_capture_compatibility_and_no_default_files(self):
        self.assertIsNone(HostCapture(b"{}", "run", "model", "context").telemetry)
        with mock.patch("avereth_core.hosts.telemetry.Path.mkdir") as mkdir:
            capture = self.run_codex()
        mkdir.assert_not_called()
        self.assertEqual(EVENTS, capture.telemetry.events)
        self.assertEqual(capture.run_id, capture.telemetry.run_id)
        self.assertEqual("test-context", capture.telemetry.context_id)
        self.assertEqual(15, capture.telemetry.measurements["input_tokens"])
        self.assertIsNone(capture.telemetry.measurements["context_bytes_loaded"])

    def test_opt_in_keeps_raw_stream_and_distinct_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AVERETH_TELEMETRY_DIR"] = tmp
            first = self.run_codex()
            self.run_codex()
            records = [json.loads(p.read_text()) for p in Path(tmp).glob("*.json")]
            self.assertEqual(2, len(records))
            saved = next(r for r in records if r["run_id"] == first.run_id)
            self.assertEqual(first.telemetry.raw_stdout, saved["raw_stdout"])
            self.assertEqual("host warning", saved["raw_stderr"])
            self.assertEqual("diagnostic_only", saved["authority"])

    def test_failure_keeps_forbidden_tool_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AVERETH_TELEMETRY_DIR"] = tmp
            events = EVENTS + [{"type": "item.completed", "item": {"type": "command_execution", "id": "tool-1"}}]
            with self.assertRaisesRegex(ValueError, "used a tool"):
                self.run_codex(events)
            saved = json.loads(next(Path(tmp).glob("*.json")).read_text())
            self.assertEqual("failed", saved["status"])
            self.assertEqual(events, saved["events"])
            self.assertIsNone(saved["measurements"]["tool_calls"])

    def test_malformed_stream_is_retained_and_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AVERETH_TELEMETRY_DIR"] = tmp
            with self.assertRaisesRegex(ValueError, "non-JSON"):
                self.run_codex(raw='{"type":"thread.started"}\nnot-json')
            saved = json.loads(next(Path(tmp).glob("*.json")).read_text())
            self.assertEqual(1, saved["invalid_event_lines"])
            self.assertTrue(saved["raw_stdout"].endswith("not-json"))

    def test_timeout_keeps_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AVERETH_TELEMETRY_DIR"] = tmp
            timeout = subprocess.TimeoutExpired("codex", 1, output=b'{"partial":true}', stderr=b'waiting')
            with mock.patch.object(codex.subprocess, "run", side_effect=timeout):
                with self.assertRaisesRegex(ValueError, "timed out"):
                    codex.run_codex_exec_isolated(prompt="test", output_schema={}, model_revision="test-model", timeout_seconds=1)
            saved = json.loads(next(Path(tmp).glob("*.json")).read_text())
            self.assertEqual("interrupted", saved["status"])
            self.assertEqual("timeout", saved["failure_type"])
            self.assertEqual("waiting", saved["raw_stderr"])
            self.assertIsNone(saved["measurements"]["input_tokens"])

    def test_sink_failure_preserves_success(self):
        os.environ["AVERETH_TELEMETRY_DIR"] = "unused"
        with mock.patch("avereth_core.hosts.telemetry.save_observation", side_effect=OSError("disk full")), contextlib.redirect_stderr(io.StringIO()) as stderr:
            capture = self.run_codex()
        self.assertEqual(b'{"ok":true}', capture.raw_output)
        self.assertIn("not saved", stderr.getvalue())

    def test_failure_to_start_is_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AVERETH_TELEMETRY_DIR"] = tmp
            with mock.patch.object(codex.subprocess, "run", side_effect=FileNotFoundError("missing")):
                with self.assertRaisesRegex(ValueError, "could not be launched"):
                    codex.run_codex_exec_isolated(prompt="test", output_schema={}, model_revision="test-model")
            saved = json.loads(next(Path(tmp).glob("*.json")).read_text())
            self.assertEqual("FileNotFoundError", saved["failure_type"])
            self.assertEqual([], saved["events"])

    def test_service_error_is_not_hidden_by_stderr_warning(self):
        result = subprocess.CompletedProcess(['codex'], 1,
            json.dumps({'type': 'error', 'message': 'invalid_json_schema: unsupported constraint'}),
            'unrelated host warning')
        with mock.patch.object(codex.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(ValueError, 'invalid_json_schema'):
                codex.run_codex_exec_isolated(prompt='test', output_schema={}, model_revision='test-model')

    def test_claude_usage_is_not_double_counted(self):
        events = [
            {"type": "assistant", "message": {"usage": {"input_tokens": 8}, "content": []}},
            {"type": "assistant", "message": "unrecognized host extension"},
            {"type": "result", "session_id": "claude-test", "result": "{}", "usage": {"input_tokens": 8, "output_tokens": 3}},
        ]
        result = subprocess.CompletedProcess(["claude"], 0, "\n".join(map(json.dumps, events)), "")
        with mock.patch.object(claude.subprocess, "run", return_value=result):
            capture = claude.run_claude_exec_isolated(prompt="test", output_schema={}, model_revision="test-model")
        self.assertEqual(8, capture.telemetry.measurements["input_tokens"])
        self.assertEqual(events, capture.telemetry.events)

    def test_usage_missing_or_interrupted_is_unknown(self):
        self.assertIsNone(host_measurements("codex", [], complete=True)["tool_calls"])
        self.assertIsNone(host_measurements("codex", EVENTS, complete=False)["input_tokens"])
        invalid = [{"type": "turn.completed", "usage": {"input_tokens": True, "output_tokens": -1}}]
        self.assertIsNone(host_measurements("codex", invalid, complete=True)["input_tokens"])

    def test_repeated_tool_lifecycle_counts_once(self):
        tool = {"id": "tool-1", "type": "command_execution"}
        events = EVENTS + [{"type": "item.started", "item": tool}, {"type": "item.completed", "item": tool}, {"type": "item.completed", "item": tool}]
        self.assertEqual(1, host_measurements("codex", events, complete=True)["tool_calls"])

    def test_controller_observation_preserves_output_and_exit(self):
        @observe_controller
        def command():
            print("original output")
            return 2
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as output:
            os.environ["AVERETH_TELEMETRY_DIR"] = tmp
            self.assertEqual(2, command())
            records = [json.loads(p.read_text()) for p in Path(tmp).glob("*.json")]
        self.assertEqual("original output\n", output.getvalue())
        completed = next(r for r in records if r["type"] == "controller.completed")
        self.assertEqual(2, completed["exit_code"])
        self.assertEqual(output.getvalue(), completed["stdout"])

    def test_gate_exit_success_does_not_invent_unique_catch(self):
        @observe_gate
        def gate(outdir, stage):
            return 0
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AVERETH_TELEMETRY_DIR"] = tmp
            self.assertEqual(0, gate(Path(tmp), "audit"))
            record = json.loads(next(Path(tmp).glob("*.json")).read_text())
        self.assertIsNone(record["unique_catch"])
        self.assertNotIn("pass", record)


if __name__ == "__main__":
    unittest.main()
