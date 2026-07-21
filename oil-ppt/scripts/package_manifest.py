#!/usr/bin/env python3
"""Create and verify a deterministic manifest for the installed oil-ppt skill."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_NAME = "manifest.json"
MANIFEST_SCHEMA = "oil-ppt.package/v1"
SCHEMA_VERSION = MANIFEST_SCHEMA
PACKAGE_VERSION = "1.0.0"
HASH_CHUNK_SIZE = 1024 * 1024


def _resolved(path: Path | str) -> Path:
    return Path(path).expanduser().resolve()


def _manifest_path(path: Path | str | None, root: Path) -> Path:
    return _resolved(path) if path is not None else root / DEFAULT_MANIFEST_NAME


def _is_excluded(relative: PurePosixPath, manifest_relative: str | None) -> bool:
    return (
        "__pycache__" in relative.parts
        or relative.name.endswith(".pyc")
        or relative.name == ".DS_Store"
        or (manifest_relative is not None and relative.as_posix() == manifest_relative)
    )


def _relative_manifest_path(root: Path, manifest_path: Path | None) -> str | None:
    if manifest_path is None:
        return None
    try:
        return manifest_path.relative_to(root).as_posix()
    except ValueError:
        return None


def _file_record(path: Path, relative: str) -> dict[str, object]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
            size += len(chunk)
    return {"path": relative, "sha256": digest.hexdigest(), "size": size}


def _raise_walk_error(error: OSError) -> None:
    raise error


def collect_files(
    root: Path | str = ROOT,
    *,
    manifest_path: Path | str | None = None,
) -> list[dict[str, object]]:
    """Return sorted hash records for all regular, publishable files below *root*."""
    root_path = _resolved(root)
    if not root_path.is_dir():
        raise NotADirectoryError(f"skill root is not a directory: {root_path}")

    resolved_manifest = _resolved(manifest_path) if manifest_path is not None else None
    manifest_relative = _relative_manifest_path(root_path, resolved_manifest)
    records: list[dict[str, object]] = []
    for directory, directory_names, file_names in os.walk(
        root_path, followlinks=False, onerror=_raise_walk_error
    ):
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name != "__pycache__" and not (Path(directory) / name).is_symlink()
        )
        for name in sorted(file_names):
            path = Path(directory) / name
            relative = PurePosixPath(path.relative_to(root_path).as_posix())
            if _is_excluded(relative, manifest_relative) or path.is_symlink():
                continue
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError:
                raise RuntimeError(f"file disappeared while creating manifest: {relative}") from None
            if not stat.S_ISREG(mode):
                continue
            records.append(_file_record(path, relative.as_posix()))
    records.sort(key=lambda item: str(item["path"]))
    return records


def compute_tree_sha256(files: Iterable[dict[str, object]]) -> str:
    """Hash canonical, path-sorted file records into one deterministic tree digest."""
    records = sorted(
        (
            {
                "path": str(record["path"]),
                "sha256": str(record["sha256"]),
                "size": int(record["size"]),
            }
            for record in files
        ),
        key=lambda item: item["path"],
    )
    canonical = json.dumps(
        records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def generate_manifest(
    root: Path | str = ROOT,
    *,
    manifest_path: Path | str | None = None,
) -> dict[str, object]:
    """Build a deterministic manifest without writing it to disk."""
    root_path = _resolved(root)
    resolved_manifest = _manifest_path(manifest_path, root_path)
    files = collect_files(root_path, manifest_path=resolved_manifest)
    return {
        "schema_version": MANIFEST_SCHEMA,
        "package_version": PACKAGE_VERSION,
        "tree_sha256": compute_tree_sha256(files),
        "files": files,
    }


build_manifest = generate_manifest


def write_manifest(
    path: Path | str | None = None,
    *,
    root: Path | str = ROOT,
) -> dict[str, object]:
    """Atomically write a manifest and return the generated data."""
    root_path = _resolved(root)
    destination = _manifest_path(path, root_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = generate_manifest(root_path, manifest_path=destination)
    payload = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return manifest


def _empty_report(root: Path, manifest_path: Path) -> dict[str, object]:
    return {
        "ok": False,
        "root": str(root),
        "manifest_path": str(manifest_path),
        "missing": [],
        "changed": [],
        "unexpected": [],
        "errors": [],
    }


def _valid_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and path.as_posix() == value
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _validated_entries(
    raw_files: object,
    errors: list[str],
    *,
    manifest_relative: str | None,
) -> list[dict[str, object]]:
    if not isinstance(raw_files, list):
        errors.append("files must be a list")
        return []

    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_files):
        label = f"files[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{label} must be an object")
            continue
        path = raw.get("path")
        sha256 = raw.get("sha256")
        size = raw.get("size")
        valid = True
        if not _valid_relative_path(path):
            errors.append(f"{label}.path must be a normalized relative POSIX path")
            valid = False
        elif path in seen:
            errors.append(f"duplicate file path: {path}")
            valid = False
        elif _is_excluded(PurePosixPath(path), manifest_relative):
            errors.append(f"manifest contains excluded file: {path}")
            valid = False
        if (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
        ):
            errors.append(f"{label}.sha256 must be a lowercase SHA-256 digest")
            valid = False
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            errors.append(f"{label}.size must be a non-negative integer")
            valid = False
        if valid:
            assert isinstance(path, str)
            assert isinstance(sha256, str)
            assert isinstance(size, int)
            seen.add(path)
            entries.append({"path": path, "sha256": sha256, "size": size})

    paths = [str(entry["path"]) for entry in entries]
    if paths != sorted(paths):
        errors.append("files must be sorted by path")
    return entries


def verify_manifest(
    path: Path | str | None = None,
    *,
    root: Path | str = ROOT,
) -> dict[str, object]:
    """Compare a manifest with disk and report missing, changed, and unexpected files."""
    root_path = _resolved(root)
    source = _manifest_path(path, root_path)
    report = _empty_report(root_path, source)
    errors = report["errors"]
    assert isinstance(errors, list)

    try:
        manifest = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"manifest does not exist: {source}")
        return report
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(f"unable to read manifest: {error}")
        return report

    if not isinstance(manifest, dict):
        errors.append("manifest root must be an object")
        return report
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        errors.append(f"schema_version must be {MANIFEST_SCHEMA!r}")
    if manifest.get("package_version") != PACKAGE_VERSION:
        errors.append(f"package_version must be {PACKAGE_VERSION!r}")

    entries = _validated_entries(
        manifest.get("files"),
        errors,
        manifest_relative=_relative_manifest_path(root_path, source),
    )
    declared_tree = manifest.get("tree_sha256")
    if (
        not isinstance(declared_tree, str)
        or len(declared_tree) != 64
        or any(character not in "0123456789abcdef" for character in declared_tree)
    ):
        errors.append("tree_sha256 must be a lowercase SHA-256 digest")
    elif declared_tree != compute_tree_sha256(entries):
        errors.append("tree_sha256 does not match the manifest file records")

    try:
        current_entries = collect_files(root_path, manifest_path=source)
    except (OSError, RuntimeError) as error:
        errors.append(f"unable to scan skill root: {error}")
        return report

    expected = {str(entry["path"]): entry for entry in entries}
    current = {str(entry["path"]): entry for entry in current_entries}
    expected_paths = set(expected)
    current_paths = set(current)
    report["missing"] = sorted(expected_paths - current_paths)
    report["unexpected"] = sorted(current_paths - expected_paths)
    report["changed"] = sorted(
        relative
        for relative in expected_paths & current_paths
        if expected[relative]["sha256"] != current[relative]["sha256"]
        or expected[relative]["size"] != current[relative]["size"]
    )
    report["ok"] = not any(
        report[key] for key in ("errors", "missing", "changed", "unexpected")
    )
    report["tree_sha256"] = compute_tree_sha256(current_entries)
    return report


verify = verify_manifest


def package_status(root: Path | str = ROOT) -> dict[str, object]:
    """Return package version, provenance, and integrity in one stable contract."""
    root_path = _resolved(root)
    manifest_path = root_path / DEFAULT_MANIFEST_NAME
    verification = verify_manifest(manifest_path, root=root_path)
    errors = list(verification["errors"])

    current_files: list[dict[str, object]] = []
    try:
        current_files = collect_files(root_path, manifest_path=manifest_path)
    except (OSError, RuntimeError) as error:
        message = f"unable to scan skill root: {error}"
        if message not in errors:
            errors.append(message)
    current_tree = compute_tree_sha256(current_files)

    declared_tree: str | None = None
    declared_file_count: int | None = None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        manifest = None
    if isinstance(manifest, dict):
        candidate_tree = manifest.get("tree_sha256")
        if (
            isinstance(candidate_tree, str)
            and len(candidate_tree) == 64
            and all(character in "0123456789abcdef" for character in candidate_tree)
        ):
            declared_tree = candidate_tree
        if isinstance(manifest.get("files"), list):
            declared_file_count = len(manifest["files"])

    return {
        "schema_version": "oil-ppt.version/v1",
        "ok": bool(verification["ok"]) and not errors,
        "version": PACKAGE_VERSION,
        "tree_sha256": declared_tree or current_tree,
        "root": str(root_path),
        "manifest_path": str(manifest_path),
        "file_count": declared_file_count if declared_file_count is not None else len(current_files),
        "missing": list(verification["missing"]),
        "changed": list(verification["changed"]),
        "unexpected": list(verification["unexpected"]),
        "errors": errors,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument(
        "--write",
        nargs="?",
        const=str(ROOT / DEFAULT_MANIFEST_NAME),
        metavar="PATH",
        help="write the manifest (default: skill root/manifest.json)",
    )
    operation.add_argument(
        "--verify",
        nargs="?",
        const=str(ROOT / DEFAULT_MANIFEST_NAME),
        metavar="PATH",
        help="verify the manifest (default: skill root/manifest.json)",
    )
    parser.add_argument("--json", action="store_true", help="emit a JSON result")
    return parser


def _print_verification(report: dict[str, object]) -> None:
    status = "OK" if report["ok"] else "FAILED"
    print(f"{status}: {report['manifest_path']}")
    for key in ("errors", "missing", "changed", "unexpected"):
        for value in report[key]:  # type: ignore[union-attr]
            print(f"{key[:-1] if key == 'errors' else key}: {value}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.write is not None:
        destination = _resolved(args.write)
        try:
            manifest = write_manifest(destination, root=ROOT)
        except (OSError, RuntimeError, ValueError) as error:
            result = {
                "ok": False,
                "action": "write",
                "manifest_path": str(destination),
                "error": str(error),
            }
            if args.json:
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            else:
                print(f"FAILED: {error}", file=sys.stderr)
            return 1
        result = {
            "ok": True,
            "action": "write",
            "manifest_path": str(destination),
            "file_count": len(manifest["files"]),
            "tree_sha256": manifest["tree_sha256"],
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(
                f"WROTE: {destination} "
                f"({result['file_count']} files, tree_sha256={result['tree_sha256']})"
            )
        return 0

    report = verify_manifest(args.verify, root=ROOT)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        _print_verification(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
