"""Structured workspace locks with conservative, explicit stale recovery."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator


LOCK_SCHEMA = "avereth-lock/v1"
LOCK_NAMES = (
    ".avereth-transition.lock",
    ".avereth-build.lock",
    ".avereth-audit.lock",
    ".avereth-output.lock",
)
LOCK_CLEANUP_WARNING = (
    '{"status":"WARNING","code":"WORKSPACE_LOCK_CLEANUP_FAILED"}\n'
)
MAX_LOCK_BYTES = 4096
MAX_LOCK_FIELDS = 8
MAX_LOCK_HOSTNAME_CHARS = 255
MAX_LOCK_OPERATION_CHARS = 64
MAX_LOCK_TIMESTAMP_CHARS = 64
SAFE_LOCK_HOSTNAME = re.compile(r"^[A-Za-z0-9._:-]+$")
SAFE_LOCK_OPERATION = re.compile(r"^[A-Za-z0-9._:-]+$")


def _emit_lock_cleanup_warning() -> None:
    """Report a cleanup-only failure without exposing a machine-local path."""

    try:
        sys.stderr.write(LOCK_CLEANUP_WARNING)
    except BaseException:
        # Diagnostic delivery must never replace the operation's real result.
        pass


@dataclass(frozen=True)
class LockInspection:
    path: str
    state: str
    recoverable: bool
    pid: int | None = None
    hostname: str = ""
    operation: str = ""
    started_at: str = ""
    format: str = "unknown"
    reason: str = ""
    content_sha256: str = ""
    target_name: str = ""

    def as_dict(self) -> dict[str, object]:
        hostname_scope = ""
        if self.hostname:
            hostname_scope = "<remote>" if self.state == "remote" else "<local>"
        return {
            "path": self.path,
            "state": self.state,
            "recoverable": self.recoverable,
            "pid": self.pid,
            "hostname": hostname_scope,
            "operation": "<recorded>" if self.operation else "",
            "started_at": "<recorded>" if self.started_at else "",
            "format": self.format,
            "reason": self.reason,
        }


def local_hostname() -> str:
    return socket.gethostname().strip()


def _pid_alive_windows(pid: int) -> bool | None:
    try:
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error in {5}:  # Access denied still proves that a process owns the PID.
                return True
            if error in {87, 1168}:  # Invalid parameter / element not found.
                return False
            return None
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return None
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None


def pid_alive(pid: int) -> bool | None:
    """Return True/False only when process liveness is known."""

    if pid <= 0:
        return False
    if os.name == "nt":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _decode_lock(raw: bytes) -> tuple[dict[str, object], str, str]:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError, MemoryError):
        payload = None
    if isinstance(payload, dict) and payload.get("schema_version") == LOCK_SCHEMA:
        expected = {"schema_version", "pid", "hostname", "operation", "started_at"}
        if len(payload) > MAX_LOCK_FIELDS or not set(payload).issubset(expected):
            return {}, "unknown", "lock metadata does not match the bounded v1 contract"
        return payload, "json-v1", ""
    # v6.0 wrote one ASCII pid line.  Recognise it as a bounded local legacy
    # format; all other malformed content remains non-recoverable.
    try:
        text = raw.decode("ascii").strip()
    except UnicodeError:
        return {}, "unknown", "lock content is neither valid v1 JSON nor the v6.0 pid format"
    if text.startswith("pid=") and len(text[4:]) <= 10 and text[4:].isdigit():
        return {
            "pid": int(text[4:]),
            "hostname": local_hostname(),
            "operation": "legacy-v6-transition",
            "started_at": "",
        }, "legacy-pid", ""
    return {}, "unknown", "lock content is neither valid v1 JSON nor the v6.0 pid format"


def inspect_lock(path: Path) -> LockInspection:
    target_name = path.name
    relative = target_name if target_name in LOCK_NAMES else "workspace-lock"
    try:
        if path.stat().st_size > MAX_LOCK_BYTES:
            return LockInspection(
                relative,
                "unknown",
                False,
                reason="lock exceeds the bounded metadata limit",
                target_name=target_name,
            )
        with path.open("rb") as handle:
            raw = handle.read(MAX_LOCK_BYTES + 1)
    except FileNotFoundError:
        return LockInspection(relative, "absent", False, reason="lock does not exist", target_name=target_name)
    except OSError:
        return LockInspection(relative, "unknown", False, reason="lock cannot be read safely", target_name=target_name)
    if len(raw) > MAX_LOCK_BYTES:
        return LockInspection(
            relative,
            "unknown",
            False,
            reason="lock exceeds the bounded metadata limit",
            target_name=target_name,
        )
    digest = hashlib.sha256(raw).hexdigest()
    payload, format_name, decode_issue = _decode_lock(raw)
    if decode_issue:
        return LockInspection(relative, "unknown", False, format=format_name, reason=decode_issue, content_sha256=digest, target_name=target_name)
    raw_pid = payload.get("pid")
    if format_name == "json-v1" and (isinstance(raw_pid, bool) or not isinstance(raw_pid, int)):
        return LockInspection(relative, "unknown", False, format=format_name, reason="lock pid must be an integer", content_sha256=digest, target_name=target_name)
    try:
        pid = int(raw_pid)
    except (TypeError, ValueError):
        pid = None
    raw_hostname = payload.get("hostname")
    raw_operation = payload.get("operation")
    raw_started_at = payload.get("started_at")
    if format_name == "json-v1" and not all(
        isinstance(value, str) for value in (raw_hostname, raw_operation, raw_started_at)
    ):
        return LockInspection(relative, "unknown", False, pid=pid, format=format_name, reason="lock metadata fields must be strings", content_sha256=digest, target_name=target_name)
    hostname = str(raw_hostname or "").strip()
    operation = str(raw_operation or "").strip()
    started_at = str(raw_started_at or "").strip()
    if pid is None or pid <= 0 or pid > 2_147_483_647 or not hostname or not operation:
        return LockInspection(relative, "unknown", False, pid=pid, format=format_name, reason="lock metadata is incomplete", content_sha256=digest, target_name=target_name)
    if format_name == "json-v1":
        if (
            len(hostname) > MAX_LOCK_HOSTNAME_CHARS
            or len(operation) > MAX_LOCK_OPERATION_CHARS
            or len(started_at) > MAX_LOCK_TIMESTAMP_CHARS
            or SAFE_LOCK_HOSTNAME.fullmatch(hostname) is None
            or SAFE_LOCK_OPERATION.fullmatch(operation) is None
        ):
            return LockInspection(relative, "unknown", False, pid=pid, format=format_name, reason="lock metadata does not match the bounded v1 contract", content_sha256=digest, target_name=target_name)
        try:
            timestamp = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        except ValueError:
            timestamp = None
        if timestamp is None or timestamp.tzinfo is None:
            return LockInspection(relative, "unknown", False, pid=pid, format=format_name, reason="lock started_at must be an ISO-8601 timestamp with timezone", content_sha256=digest, target_name=target_name)
    if hostname.casefold() != local_hostname().casefold():
        return LockInspection(relative, "remote", False, pid=pid, hostname=hostname, operation=operation, started_at=started_at, format=format_name, reason="lock belongs to a different host", content_sha256=digest, target_name=target_name)
    alive = pid_alive(pid)
    if alive is True:
        return LockInspection(relative, "active", False, pid=pid, hostname=hostname, operation=operation, started_at=started_at, format=format_name, reason="owning process is still active", content_sha256=digest, target_name=target_name)
    if alive is None:
        return LockInspection(relative, "unknown", False, pid=pid, hostname=hostname, operation=operation, started_at=started_at, format=format_name, reason="process liveness could not be established", content_sha256=digest, target_name=target_name)
    return LockInspection(relative, "stale", True, pid=pid, hostname=hostname, operation=operation, started_at=started_at, format=format_name, reason="owning process no longer exists", content_sha256=digest, target_name=target_name)


def inspect_workspace_locks(outdir: Path, names: Iterable[str] = LOCK_NAMES) -> tuple[LockInspection, ...]:
    return tuple(
        inspection
        for name in names
        if name in LOCK_NAMES
        if (inspection := inspect_lock(outdir / name)).state != "absent"
    )


def recover_workspace_locks(
    outdir: Path,
    *,
    names: Iterable[str] = LOCK_NAMES,
    confirm: bool = False,
) -> dict[str, object]:
    """Diagnose by default; delete only confirmed, unchanged stale local locks."""

    inspections = inspect_workspace_locks(outdir, names)
    removed: list[str] = []
    refused: list[dict[str, object]] = []
    if confirm:
        for inspection in inspections:
            if not inspection.recoverable:
                refused.append(inspection.as_dict())
                continue
            path = outdir / inspection.target_name
            current = inspect_lock(path)
            if (
                not current.recoverable
                or current.content_sha256 != inspection.content_sha256
            ):
                refused.append(current.as_dict())
                continue
            try:
                path.unlink()
            except OSError:
                refused.append({**current.as_dict(), "reason": "stale lock could not be removed safely"})
            else:
                removed.append(inspection.path)
    status = "PASS"
    if confirm and refused:
        status = "REFUSED"
    elif not confirm and inspections:
        status = "DIAGNOSTIC"
    return {
        "schema_version": "avereth-lock-recovery/v1",
        "status": status,
        "mode": "recover" if confirm else "diagnose",
        "locks": [inspection.as_dict() for inspection in inspections],
        "removed": removed,
        "refused": refused,
    }


@contextmanager
def exclusive_lock(outdir: Path, filename: str, message: str, *, operation: str) -> Iterator[None]:
    if filename not in LOCK_NAMES:
        raise ValueError("unsupported workspace lock name")
    if (
        not isinstance(operation, str)
        or len(operation) > MAX_LOCK_OPERATION_CHARS
        or SAFE_LOCK_OPERATION.fullmatch(operation) is None
    ):
        raise ValueError("invalid workspace lock operation")
    lock_path = outdir / filename
    hostname = local_hostname()
    if (
        not hostname
        or len(hostname) > MAX_LOCK_HOSTNAME_CHARS
        or SAFE_LOCK_HOSTNAME.fullmatch(hostname) is None
    ):
        hostname = "local-host"
    metadata = {
        "schema_version": LOCK_SCHEMA,
        "pid": os.getpid(),
        "hostname": hostname,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "operation": operation,
    }
    encoded = (json.dumps(metadata, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        inspection = inspect_lock(lock_path)
        detail = f"{inspection.state} workspace lock pid={inspection.pid or 'unknown'}"
        if inspection.recoverable:
            detail += "; run recover-lock --confirm after reviewing the diagnostic"
        raise RuntimeError(f"{message}: {detail}") from exc
    try:
        os.write(descriptor, encoded)
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        cleanup_failed = False
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except BaseException:
                cleanup_failed = True
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        except BaseException:
            cleanup_failed = True
        if cleanup_failed:
            _emit_lock_cleanup_warning()


@contextmanager
def audit_gate_lock(outdir: Path) -> Iterator[None]:
    with exclusive_lock(outdir, ".avereth-transition.lock", "another audit or output transition is already in progress", operation="audit-transition"):
        with exclusive_lock(outdir, ".avereth-audit.lock", "another audit run is already in progress", operation="audit"):
            yield


@contextmanager
def build_gate_lock(outdir: Path) -> Iterator[None]:
    with exclusive_lock(outdir, ".avereth-transition.lock", "another build, audit, or output transition is already in progress", operation="build-transition"):
        with exclusive_lock(outdir, ".avereth-build.lock", "another build run is already in progress", operation="build"):
            yield


@contextmanager
def output_gate_lock(outdir: Path) -> Iterator[None]:
    with exclusive_lock(outdir, ".avereth-transition.lock", "another audit or output transition is already in progress", operation="output-transition"):
        with exclusive_lock(outdir, ".avereth-output.lock", "another output run is already in progress", operation="output"):
            yield
