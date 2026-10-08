from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from avereth_core import cli
from avereth_core.infrastructure import locks


class WorkspaceLockTests(unittest.TestCase):
    def test_lock_is_structured_and_released_normally(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / ".avereth-build.lock"
            with locks.exclusive_lock(root, path.name, "busy", operation="build"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(locks.LOCK_SCHEMA, payload["schema_version"])
                self.assertEqual(os.getpid(), payload["pid"])
                self.assertEqual("build", payload["operation"])
                self.assertEqual("active", locks.inspect_lock(path).state)
            self.assertFalse(path.exists())

    def test_recovery_is_diagnostic_by_default_then_removes_confirmed_stale_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / ".avereth-output.lock"
            path.write_text(json.dumps({"schema_version": locks.LOCK_SCHEMA, "pid": 99999999, "hostname": locks.local_hostname(), "started_at": "2026-01-01T00:00:00+00:00", "operation": "output"}), encoding="utf-8")
            with mock.patch.object(locks, "pid_alive", return_value=False):
                diagnostic = locks.recover_workspace_locks(root)
                self.assertEqual("diagnose", diagnostic["mode"])
                self.assertTrue(path.exists())
                recovered = locks.recover_workspace_locks(root, confirm=True)
            self.assertEqual([path.name], recovered["removed"])
            self.assertFalse(path.exists())

    def test_recover_lock_cli_requires_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / ".avereth-output.lock"
            path.write_text(json.dumps({"schema_version": locks.LOCK_SCHEMA, "pid": 99999999, "hostname": locks.local_hostname(), "started_at": "2026-01-01T00:00:00+00:00", "operation": "output"}), encoding="utf-8")
            with mock.patch.object(locks, "pid_alive", return_value=False):
                with mock.patch.object(sys, "argv", ["avereth.py", "recover-lock", str(root)]), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(0, cli.main())
                self.assertTrue(path.exists())
                with mock.patch.object(sys, "argv", ["avereth.py", "recover-lock", str(root), "--confirm"]), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(0, cli.main())
            self.assertFalse(path.exists())

    def test_live_remote_and_malformed_locks_are_refused(self) -> None:
        cases = (
            ({"schema_version": locks.LOCK_SCHEMA, "pid": os.getpid(), "hostname": locks.local_hostname(), "started_at": "2026-08-17T00:00:00+00:00", "operation": "audit"}, "active"),
            ({"schema_version": locks.LOCK_SCHEMA, "pid": 99999, "hostname": "another-host", "started_at": "2026-08-17T00:00:00+00:00", "operation": "audit"}, "remote"),
        )
        for payload, state in cases:
            with self.subTest(state=state), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                path = root / ".avereth-audit.lock"
                path.write_text(json.dumps(payload), encoding="utf-8")
                inspection = locks.inspect_lock(path)
                self.assertEqual(state, inspection.state)
                report = locks.recover_workspace_locks(root, confirm=True)
                self.assertTrue(report["refused"])
                self.assertTrue(path.exists())
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / ".avereth-output.lock"
            path.write_text(json.dumps({"schema_version": locks.LOCK_SCHEMA, "pid": 99999, "hostname": locks.local_hostname(), "operation": "output"}), encoding="utf-8")
            self.assertEqual("unknown", locks.inspect_lock(path).state)
            report = locks.recover_workspace_locks(root, confirm=True)
            self.assertTrue(report["refused"])
            self.assertTrue(path.exists())
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / ".avereth-transition.lock"
            path.write_text("not a lock contract", encoding="utf-8")
            self.assertEqual("unknown", locks.inspect_lock(path).state)
            report = locks.recover_workspace_locks(root, confirm=True)
            self.assertTrue(report["refused"])
            self.assertTrue(path.exists())

    def test_legacy_pid_lock_is_recoverable_only_when_owner_is_dead(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / ".avereth-transition.lock"
            path.write_text("pid=42424242\n", encoding="ascii")
            with mock.patch.object(locks, "pid_alive", return_value=False):
                inspection = locks.inspect_lock(path)
                self.assertEqual("legacy-pid", inspection.format)
                self.assertTrue(inspection.recoverable)
                report = locks.recover_workspace_locks(root, confirm=True)
            self.assertEqual([path.name], report["removed"])

    def test_oversized_lock_is_rejected_before_json_decode(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            marker = "PRIVATE-LOCK-CONTENT-MUST-NOT-LEAK"
            path = root / ".avereth-output.lock"
            path.write_text(marker * 10, encoding="utf-8")
            with (
                mock.patch.object(locks, "MAX_LOCK_BYTES", 32),
                mock.patch.object(
                    locks.json,
                    "loads",
                    side_effect=AssertionError("oversized lock was decoded"),
                ),
            ):
                inspection = locks.inspect_lock(path)
                report = locks.recover_workspace_locks(root, confirm=True)
            rendered = json.dumps(
                {"inspection": inspection.as_dict(), "report": report}
            )
            self.assertEqual("unknown", inspection.state)
            self.assertTrue(path.exists())
            self.assertNotIn(marker, rendered)

    def test_lock_reports_redact_recorded_host_operation_and_io_errors(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            marker = "PRIVATE-LOCK-METADATA"
            path = root / ".avereth-audit.lock"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": locks.LOCK_SCHEMA,
                        "pid": 99999999,
                        "hostname": marker,
                        "started_at": "2026-08-17T00:00:00+00:00",
                        "operation": marker,
                    }
                ),
                encoding="utf-8",
            )
            rendered = json.dumps(locks.inspect_lock(path).as_dict())
            self.assertNotIn(marker, rendered)

            original_open = Path.open

            def fail_lock_read(candidate: Path, *args: object, **kwargs: object):
                if candidate == path:
                    raise OSError(marker)
                return original_open(candidate, *args, **kwargs)

            with mock.patch.object(Path, "open", new=fail_lock_read):
                failed = json.dumps(locks.inspect_lock(path).as_dict())
            self.assertNotIn(marker, failed)

    def test_current_process_lock_is_visible_but_does_not_fail_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            skills_dir = Path(cli.__file__).resolve().parents[3]
            with locks.exclusive_lock(root, ".avereth-transition.lock", "busy", operation="test-status"):
                result = cli.run_doctor(skills_dir, outdir=root)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual("active", result.details["workspace_locks"][0]["state"])

    def test_inner_lock_conflict_releases_outer_transition_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with locks.exclusive_lock(root, ".avereth-build.lock", "busy", operation="existing-build"):
                with self.assertRaises(RuntimeError):
                    with locks.build_gate_lock(root):
                        self.fail("inner conflict should prevent entry")
                self.assertFalse((root / ".avereth-transition.lock").exists())
                self.assertTrue((root / ".avereth-build.lock").exists())

    def test_cleanup_failure_warns_without_overriding_success(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            lock_path = root / ".avereth-transition.lock"
            stderr = io.StringIO()
            original_unlink = Path.unlink

            def fail_lock_cleanup(path: Path, *args: object, **kwargs: object) -> None:
                if path == lock_path:
                    raise OSError("PRIVATE cleanup path must not escape")
                original_unlink(path, *args, **kwargs)

            completed = False
            with mock.patch.object(Path, "unlink", new=fail_lock_cleanup), contextlib.redirect_stderr(stderr):
                with locks.exclusive_lock(
                    root,
                    lock_path.name,
                    "busy",
                    operation="committed-operation",
                ):
                    completed = True

            self.assertTrue(completed)
            self.assertTrue(lock_path.exists())
            self.assertEqual(locks.LOCK_CLEANUP_WARNING, stderr.getvalue())
            self.assertNotIn(str(root), stderr.getvalue())
            self.assertNotIn("PRIVATE", stderr.getvalue())

    def test_cleanup_failure_preserves_body_exception(self) -> None:
        class BodyFailure(RuntimeError):
            pass

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            lock_path = root / ".avereth-transition.lock"
            stderr = io.StringIO()
            original_unlink = Path.unlink

            def fail_lock_cleanup(path: Path, *args: object, **kwargs: object) -> None:
                if path == lock_path:
                    raise OSError("cleanup failure")
                original_unlink(path, *args, **kwargs)

            with mock.patch.object(Path, "unlink", new=fail_lock_cleanup), contextlib.redirect_stderr(stderr):
                with self.assertRaisesRegex(BodyFailure, "original body failure"):
                    with locks.exclusive_lock(
                        root,
                        lock_path.name,
                        "busy",
                        operation="uncommitted-operation",
                    ):
                        raise BodyFailure("original body failure")

            self.assertTrue(lock_path.exists())
            self.assertEqual(locks.LOCK_CLEANUP_WARNING, stderr.getvalue())

    def test_research_material_commit_survives_lock_cleanup_failure(self) -> None:
        import research_materials

        with tempfile.TemporaryDirectory() as raw:
            # Some hosted runners expose the temporary directory through a
            # non-canonical alias.  init_command resolves its workspace before
            # acquiring the lock, so the injected cleanup failure must target
            # that same canonical path on every platform.
            root = Path(raw).resolve()
            lock_path = root / ".avereth-transition.lock"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_unlink = Path.unlink

            def fail_lock_cleanup(path: Path, *args: object, **kwargs: object) -> None:
                if path == lock_path:
                    raise OSError("cleanup failure")
                original_unlink(path, *args, **kwargs)

            with (
                mock.patch.object(Path, "unlink", new=fail_lock_cleanup),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                code = research_materials.init_command(
                    root,
                    not_applicable=False,
                    rationale="Material applicability requires explicit review before research.",
                    apply=True,
                )

            self.assertEqual(0, code)
            self.assertTrue(
                (root / research_materials.REGISTRY_REL).is_file()
            )
            self.assertEqual(
                1,
                len(
                    list(
                        (root / research_materials.MIGRATION_REL).rglob(
                            "mutation_manifest.json"
                        )
                    )
                ),
            )
            self.assertEqual(locks.LOCK_CLEANUP_WARNING, stderr.getvalue())
            self.assertEqual("init", json.loads(stdout.getvalue())["operation"])


if __name__ == "__main__":
    unittest.main()
