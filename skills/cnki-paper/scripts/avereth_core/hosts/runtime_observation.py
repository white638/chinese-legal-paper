"""Opt-in controller observations with no effect on command output or authority."""

from __future__ import annotations

import contextlib
import functools
import io
import os
import sys
import time
import uuid
from datetime import datetime, timezone

from .telemetry import emit_observation


def record_runtime_event(kind: str, **details) -> None:
    if os.environ.get("AVERETH_TELEMETRY_DIR"):
        emit_observation({
            "schema_version": "avereth-runtime-observation/v1", "authority": "diagnostic_only",
            "type": kind, "observed_at": datetime.now(timezone.utc).isoformat(),
            "run_id": os.environ.get("AVERETH_TELEMETRY_RUN_ID"),
            "parent_operation": os.environ.get("AVERETH_TELEMETRY_PARENT_OPERATION"),
            **details,
        })


class _Tee:
    def __init__(self, target):
        self.target, self.buffer = target, io.StringIO()

    def write(self, value):
        self.buffer.write(value)
        return self.target.write(value)

    def flush(self):
        return self.target.flush()

    def __getattr__(self, name):
        return getattr(self.target, name)


def observe_controller(function):
    @functools.wraps(function)
    def run(*args, **kwargs):
        if not os.environ.get("AVERETH_TELEMETRY_DIR"):
            return function(*args, **kwargs)
        operation = uuid.uuid4().hex
        started = time.monotonic()
        stdout, stderr = _Tee(sys.stdout), _Tee(sys.stderr)
        exit_code, failure_type = None, None
        record_runtime_event("controller.started", operation=operation, argv=sys.argv[1:])
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = function(*args, **kwargs)
            return exit_code
        except BaseException as exc:
            failure_type = type(exc).__name__
            if isinstance(exc, SystemExit):
                exit_code = exc.code
            raise
        finally:
            record_runtime_event(
                "controller.completed", operation=operation, argv=sys.argv[1:], exit_code=exit_code,
                failure_type=failure_type, wall_time_seconds=time.monotonic() - started,
                stdout=stdout.buffer.getvalue(), stderr=stderr.buffer.getvalue(),
            )
    return run


def observe_gate(function):
    @functools.wraps(function)
    def run(outdir, stage, *args, **kwargs):
        if not os.environ.get("AVERETH_TELEMETRY_DIR"):
            return function(outdir, stage, *args, **kwargs)
        started = time.monotonic()
        code, failure = None, None
        try:
            code = function(outdir, stage, *args, **kwargs)
            return code
        except BaseException as exc:
            failure = type(exc).__name__
            raise
        finally:
            record_runtime_event("gate.executed", gate=stage, workspace=str(outdir), exit_code=code,
                                 failure_type=failure, wall_time_seconds=time.monotonic() - started,
                                 unique_catch=None, false_positive=None, repair_succeeded=None)
    return run
