"""Bounded ZIP manifest adapter.

The adapter reads central-directory metadata only. It never opens member
streams, extracts members, follows links, or recursively inspects nested
archives. Formats that need an external parser remain unsupported until that
parser is pinned and regression-tested as part of the runtime.
"""

from __future__ import annotations

import math
import re
import struct
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from .common import base_profile, unsupported_profile


ARCHIVE_SUFFIXES = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz"}
NESTED_ARCHIVE_SUFFIXES = ARCHIVE_SUFFIXES | {".bz2", ".xz"}

# These caps bound both the emitted receipt and the archive workload. They are
# policy limits, not claims that an archive below a limit is safe to extract.
MAX_ARCHIVE_MEMBERS = 10_000
MAX_ARCHIVE_CENTRAL_DIRECTORY_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_MEMBER_NAME_BYTES = 4096
MAX_ARCHIVE_MEMBER_NAME_TOTAL_BYTES = 4 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 10 * 1024 * 1024 * 1024
MAX_MEMBER_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200.0
MAX_EOCD_SEARCH_BYTES = 65_557


class ZipBoundaryError(ValueError):
    """A fixed-diagnostic ZIP preflight failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        blocked: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.blocked = blocked
        self.details = details or {}


def zip_central_directory_summary(
    path: Path,
    *,
    member_limit: int = MAX_ARCHIVE_MEMBERS,
    central_directory_limit: int = MAX_ARCHIVE_CENTRAL_DIRECTORY_BYTES,
    handle: BinaryIO | None = None,
    propagate_io_errors: bool = False,
) -> dict[str, int | bool]:
    """Read only the bounded EOCD tail before ``zipfile`` parses member metadata.

    ``zipfile.ZipFile`` constructs every ``ZipInfo`` while opening an archive.
    This preflight therefore rejects excessive member counts and central-
    directory bytes before that allocation occurs. ZIP64 EOCD records are read
    directly from their fixed locator rather than by scanning the archive.
    """

    if handle is None:
        try:
            with path.open("rb") as opened:
                return zip_central_directory_summary(
                    path,
                    member_limit=member_limit,
                    central_directory_limit=central_directory_limit,
                    handle=opened,
                    propagate_io_errors=propagate_io_errors,
                )
        except OSError:
            if propagate_io_errors:
                raise
            raise ZipBoundaryError(
                "ARCHIVE_MANIFEST_FAILED",
                "ZIP metadata could not be read",
                blocked=False,
            ) from None

    try:
        handle.seek(0, 2)
        size = int(handle.tell())
        tail_size = min(size, MAX_EOCD_SEARCH_BYTES)
        handle.seek(size - tail_size)
        tail = handle.read(tail_size)
    except OSError:
        if propagate_io_errors:
            raise
        raise ZipBoundaryError(
            "ARCHIVE_MANIFEST_FAILED",
            "ZIP metadata could not be read",
            blocked=False,
        ) from None
    signature = b"PK\x05\x06"
    index = tail.rfind(signature)
    if index < 0 or index + 22 > len(tail):
        raise ZipBoundaryError(
            "ARCHIVE_MANIFEST_FAILED",
            "ZIP end-of-central-directory metadata is invalid",
            blocked=False,
        )
    try:
        (
            _signature,
            disk_number,
            central_disk,
            entries_on_disk,
            entry_count,
            central_size,
            central_offset,
            comment_length,
        ) = struct.unpack_from("<4s4H2LH", tail, index)
    except struct.error:
        raise ZipBoundaryError(
            "ARCHIVE_MANIFEST_FAILED",
            "ZIP end-of-central-directory metadata is invalid",
            blocked=False,
        ) from None
    if index + 22 + int(comment_length) > len(tail):
        raise ZipBoundaryError(
            "ARCHIVE_MANIFEST_FAILED",
            "ZIP end-of-central-directory metadata is incomplete",
            blocked=False,
        )
    eocd_absolute = size - tail_size + index
    central_end = eocd_absolute
    zip64 = (
        entry_count == 0xFFFF
        or entries_on_disk == 0xFFFF
        or central_size == 0xFFFFFFFF
        or central_offset == 0xFFFFFFFF
    )
    if zip64:
        locator_offset = eocd_absolute - 20
        try:
            handle.seek(locator_offset)
            locator = handle.read(20)
            locator_signature, zip64_disk, zip64_offset, total_disks = struct.unpack(
                "<4sLQL", locator
            )
            if locator_signature != b"PK\x06\x07":
                raise struct.error
            handle.seek(int(zip64_offset))
            zip64_record = handle.read(56)
            (
                zip64_signature,
                _record_size,
                _version_made,
                _version_needed,
                disk_number,
                central_disk,
                entries_on_disk,
                entry_count,
                central_size,
                central_offset,
            ) = struct.unpack("<4sQHHIIQQQQ", zip64_record)
            central_end = int(zip64_offset)
        except OSError:
            if propagate_io_errors:
                raise
            raise ZipBoundaryError(
                "ARCHIVE_MANIFEST_FAILED",
                "ZIP64 central-directory metadata is invalid",
                blocked=False,
            ) from None
        except (struct.error, ValueError):
            raise ZipBoundaryError(
                "ARCHIVE_MANIFEST_FAILED",
                "ZIP64 central-directory metadata is invalid",
                blocked=False,
            ) from None
        if zip64_signature != b"PK\x06\x06" or zip64_disk != 0 or total_disks != 1:
            raise ZipBoundaryError(
                "ARCHIVE_MULTIDISK_UNSUPPORTED",
                "multi-disk ZIP archives are not supported",
            )
    if disk_number != 0 or central_disk != 0 or entries_on_disk != entry_count:
        raise ZipBoundaryError(
            "ARCHIVE_MULTIDISK_UNSUPPORTED",
            "multi-disk ZIP archives are not supported",
        )
    if int(entry_count) > member_limit:
        raise ZipBoundaryError(
            "ARCHIVE_MEMBER_LIMIT_EXCEEDED",
            "ZIP member count exceeds the manifest policy limit",
            details={"observed": int(entry_count), "allowed": int(member_limit)},
        )
    if int(central_size) > central_directory_limit:
        raise ZipBoundaryError(
            "ARCHIVE_CENTRAL_DIRECTORY_LIMIT_EXCEEDED",
            "ZIP central-directory bytes exceed the manifest policy limit",
            details={
                "observed": int(central_size),
                "allowed": int(central_directory_limit),
            },
        )
    if (
        int(central_offset) < 0
        or int(central_size) < 0
        or int(central_offset) + int(central_size) > size
        or central_end < int(central_size)
        or central_end > size
    ):
        raise ZipBoundaryError(
            "ARCHIVE_MANIFEST_FAILED",
            "ZIP central-directory metadata is invalid",
            blocked=False,
        )
    actual_count = 0
    consumed = 0
    central_start = central_end - int(central_size)
    try:
        handle.seek(central_start)
        while consumed < int(central_size):
            fixed = handle.read(46)
            if len(fixed) != 46 or fixed[:4] != b"PK\x01\x02":
                raise ValueError
            name_length, extra_length, member_comment_length = struct.unpack_from(
                "<HHH", fixed, 28
            )
            variable_bytes = (
                int(name_length) + int(extra_length) + int(member_comment_length)
            )
            consumed += 46 + variable_bytes
            if consumed > int(central_size):
                raise ValueError
            handle.seek(variable_bytes, 1)
            actual_count += 1
            if actual_count > member_limit:
                raise ZipBoundaryError(
                    "ARCHIVE_MEMBER_LIMIT_EXCEEDED",
                    "ZIP member count exceeds the manifest policy limit",
                    details={
                        "observed": actual_count,
                        "allowed": int(member_limit),
                    },
                )
    except ZipBoundaryError:
        raise
    except OSError:
        if propagate_io_errors:
            raise
        raise ZipBoundaryError(
            "ARCHIVE_MANIFEST_FAILED",
            "ZIP central-directory records are invalid",
            blocked=False,
        ) from None
    except (ValueError, struct.error):
        raise ZipBoundaryError(
            "ARCHIVE_MANIFEST_FAILED",
            "ZIP central-directory records are invalid",
            blocked=False,
        ) from None
    if consumed != int(central_size) or actual_count != int(entry_count):
        raise ZipBoundaryError(
            "ARCHIVE_MANIFEST_FAILED",
            "ZIP central-directory entry count is inconsistent",
            blocked=False,
        )
    return {
        "file_size_bytes": size,
        "member_count": actual_count,
        "central_directory_bytes": int(central_size),
        "zip64": bool(zip64),
    }


def _normalise_member_name(name: str) -> str:
    return name.replace("\\", "/")


def _unsafe_member_path(name: str) -> bool:
    normalised = _normalise_member_name(name)
    if not normalised or "\x00" in normalised:
        return True
    if normalised.startswith(("/", "//")) or re.match(r"^[A-Za-z]:", normalised):
        return True
    return ".." in PurePosixPath(normalised).parts


def _is_nested_archive(name: str) -> bool:
    lower = _normalise_member_name(name).casefold()
    return any(lower.endswith(suffix) for suffix in NESTED_ARCHIVE_SUFFIXES)


def _compression_ratio(uncompressed: int, compressed: int) -> float:
    if uncompressed <= 0:
        return 0.0
    if compressed <= 0:
        return math.inf
    return float(uncompressed) / float(compressed)


def _record(item: zipfile.ZipInfo) -> dict[str, Any]:
    name = _normalise_member_name(item.filename)
    ratio = _compression_ratio(int(item.file_size), int(item.compress_size))
    return {
        "path": name,
        "format": Path(name).suffix.casefold().lstrip(".") or "binary",
        "size_bytes": int(item.file_size),
        "compressed_size_bytes": int(item.compress_size),
        "compression_ratio": None if math.isinf(ratio) else round(ratio, 6),
        "crc": f"{item.CRC:08x}",
        "nested_archive": _is_nested_archive(name),
        "unsafe_path": _unsafe_member_path(name),
        "encrypted": bool(item.flag_bits & 0x1),
    }


def _violation(code: str, message: str, **details: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"code": code, "message": message}
    if details:
        row["details"] = details
    return row


def _profile_zip(path: Path) -> dict[str, Any]:
    profile = base_profile(path, adapter="archive/v1", backend="stdlib-zipfile-central-directory")
    profile.update(
        {
            "profile_scope": "archive-manifest",
            "archive_extracted": False,
            "archive_policy": {
                "member_limit": MAX_ARCHIVE_MEMBERS,
                "central_directory_limit_bytes": MAX_ARCHIVE_CENTRAL_DIRECTORY_BYTES,
                "member_name_limit_bytes": MAX_ARCHIVE_MEMBER_NAME_BYTES,
                "member_name_total_limit_bytes": MAX_ARCHIVE_MEMBER_NAME_TOTAL_BYTES,
                "total_uncompressed_limit_bytes": MAX_TOTAL_UNCOMPRESSED_BYTES,
                "member_uncompressed_limit_bytes": MAX_MEMBER_UNCOMPRESSED_BYTES,
                "compression_ratio_limit": MAX_COMPRESSION_RATIO,
                "nested_archives_allowed": False,
                "member_streams_opened": False,
            },
        }
    )
    try:
        with path.open("rb") as archive_source:
            preflight = zip_central_directory_summary(
                path,
                member_limit=MAX_ARCHIVE_MEMBERS,
                central_directory_limit=MAX_ARCHIVE_CENTRAL_DIRECTORY_BYTES,
                handle=archive_source,
                propagate_io_errors=True,
            )
            profile["archive_central_directory_bytes"] = preflight[
                "central_directory_bytes"
            ]
            with zipfile.ZipFile(archive_source) as archive:
                all_infos = archive.infolist()
                if len(all_infos) > MAX_ARCHIVE_MEMBERS:
                    raise ZipBoundaryError(
                        "ARCHIVE_MEMBER_LIMIT_EXCEEDED",
                        "ZIP member count exceeds the manifest policy limit",
                        details={
                            "observed": len(all_infos),
                            "allowed": MAX_ARCHIVE_MEMBERS,
                        },
                    )
                infos = [item for item in all_infos if not item.is_dir()]
        encoded_names = [
            _normalise_member_name(item.filename).encode("utf-8", errors="replace")
            for item in infos
        ]
        oversized_names = sum(
            1 for name in encoded_names if len(name) > MAX_ARCHIVE_MEMBER_NAME_BYTES
        )
        total_name_bytes = sum(len(name) for name in encoded_names)
        if oversized_names or total_name_bytes > MAX_ARCHIVE_MEMBER_NAME_TOTAL_BYTES:
            profile["parse_status"] = "BLOCKED"
            profile["errors"].append(
                _violation(
                    "ARCHIVE_MEMBER_NAME_LIMIT_EXCEEDED",
                    "ZIP member-name metadata exceeds the manifest policy limit",
                    oversized_members=oversized_names,
                    observed_total_bytes=total_name_bytes,
                    allowed_member_bytes=MAX_ARCHIVE_MEMBER_NAME_BYTES,
                    allowed_total_bytes=MAX_ARCHIVE_MEMBER_NAME_TOTAL_BYTES,
                )
            )
            profile["archive_member_count"] = len(infos)
            profile["archive_manifest_truncated"] = bool(infos)
            return profile

        records = [_record(item) for item in infos]
        profile["archive_manifest"] = records
        profile["observed_documents"] = len(records)
        profile["archive_member_count"] = len(infos)
        profile["archive_manifest_truncated"] = False

        total_uncompressed = sum(int(item.file_size) for item in infos)
        total_compressed = sum(int(item.compress_size) for item in infos)
        profile["total_uncompressed_bytes"] = total_uncompressed
        profile["total_compressed_bytes"] = total_compressed
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
            profile["errors"].append(
                _violation(
                    "ARCHIVE_TOTAL_SIZE_LIMIT_EXCEEDED",
                    "ZIP declared uncompressed size exceeds the policy limit",
                    observed=total_uncompressed,
                    allowed=MAX_TOTAL_UNCOMPRESSED_BYTES,
                )
            )
        oversized_count = sum(
            1 for item in infos if int(item.file_size) > MAX_MEMBER_UNCOMPRESSED_BYTES
        )
        if oversized_count:
            profile["errors"].append(
                _violation(
                    "ARCHIVE_MEMBER_SIZE_LIMIT_EXCEEDED",
                    "one or more ZIP members exceed the per-member size limit",
                    member_count=oversized_count,
                )
            )
        high_ratio_count = sum(
            1
            for item in infos
            if _compression_ratio(int(item.file_size), int(item.compress_size))
            > MAX_COMPRESSION_RATIO
        )
        global_ratio = _compression_ratio(total_uncompressed, total_compressed)
        profile["aggregate_compression_ratio"] = (
            None if math.isinf(global_ratio) else round(global_ratio, 6)
        )
        if high_ratio_count or global_ratio > MAX_COMPRESSION_RATIO:
            profile["errors"].append(
                _violation(
                    "ARCHIVE_COMPRESSION_RATIO_EXCEEDED",
                    "ZIP compression ratio exceeds the policy limit",
                    member_count=high_ratio_count,
                    aggregate_ratio=(
                        "infinite" if math.isinf(global_ratio) else round(global_ratio, 6)
                    ),
                    allowed=MAX_COMPRESSION_RATIO,
                )
            )

        unsafe = [row["path"] for row in records if row["unsafe_path"]]
        if unsafe:
            profile["errors"].append(
                _violation(
                    "ARCHIVE_PATH_TRAVERSAL",
                    "ZIP contains absolute, parent-traversing, or invalid member paths",
                    member_count=len(unsafe),
                )
            )
        nested = [row["path"] for row in records if row["nested_archive"]]
        if nested:
            profile["errors"].append(
                _violation(
                    "NESTED_ARCHIVE_UNSUPPORTED",
                    "nested archives are listed but are not recursively inspected",
                    member_count=len(nested),
                )
            )
        encrypted = [row["path"] for row in records if row["encrypted"]]
        if encrypted:
            profile["errors"].append(
                _violation(
                    "ENCRYPTED_ARCHIVE_MEMBER",
                    "encrypted ZIP members cannot be safely profiled",
                    member_count=len(encrypted),
                )
            )
        if profile["errors"]:
            profile["parse_status"] = "BLOCKED"
    except ZipBoundaryError as exc:
        profile["parse_status"] = "BLOCKED" if exc.blocked else "FAIL"
        if exc.code == "ARCHIVE_MEMBER_LIMIT_EXCEEDED":
            profile["archive_manifest"] = []
            profile["archive_member_count"] = int(exc.details.get("observed", 0))
            profile["archive_manifest_truncated"] = True
        profile["errors"].append(
            _violation(exc.code, exc.message, **exc.details)
        )
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError):
        profile["parse_status"] = "FAIL"
        profile["errors"].append(
            {
                "code": "ARCHIVE_MANIFEST_FAILED",
                "message": "ZIP metadata could not be parsed safely",
            }
        )
    return profile


def profile_archive(path: Path) -> dict[str, Any]:
    suffix = path.suffix.casefold()
    if suffix == ".zip":
        return _profile_zip(path)
    labels = {
        ".rar": "RAR",
        ".7z": "7z",
        ".tar": "TAR",
        ".gz": "gzip/TAR",
        ".tgz": "gzip/TAR",
    }
    return unsupported_profile(
        path,
        format_name=labels.get(suffix, suffix.lstrip(".") or "archive"),
        dependency_requirement="a pinned, manifest-only archive adapter",
    )
