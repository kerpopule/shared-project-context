"""Read-only bounded Git inspection. Never run repository code, hooks or tests."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

MAX_FILES = 2000
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024


def git(root, *args):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
    p = subprocess.run(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.untrackedCache=false",
            "-C",
            str(root),
            *args,
        ],
        capture_output=True,
        timeout=8,
        env=env,
    )
    if p.returncode:
        raise ValueError(
            "not_git" if b"not a git repository" in p.stderr else "git_unavailable"
        )
    if len(p.stdout) > 1024 * 1024:
        raise ValueError("git_output_bound")
    return p.stdout.decode("utf-8", errors="surrogateescape")


def identity(workspace):
    try:
        common = git(
            workspace, "rev-parse", "--path-format=absolute", "--git-common-dir"
        ).strip()
        root = git(workspace, "rev-parse", "--show-toplevel").strip()
        return {
            "kind": "git",
            "common_dir": str(Path(common).resolve()),
            "root": str(Path(root).resolve()),
        }
    except ValueError as error:
        return {
            "kind": "non_git" if str(error) == "not_git" else "unavailable",
            "root": str(Path(workspace).resolve()),
        }
    except (OSError, subprocess.TimeoutExpired):
        return {"kind": "unavailable", "root": str(Path(workspace).resolve())}


def snapshot(workspace):
    p = Path(workspace)
    if not p.is_dir():
        return {
            "kind": "unavailable",
            "complete": False,
            "issues": ["workspace_missing"],
            "fingerprint": None,
        }
    info = identity(workspace)
    if info["kind"] == "unavailable":
        return dict(info, complete=False, fingerprint=None, issues=["git_unavailable"])
    if info["kind"] != "git":
        return dict(
            info,
            complete=True,
            fingerprint=None,
            issues=[],
            note="No filesystem content scan for non-Git projects.",
        )
    root = Path(info["root"])
    try:
        head = git(root, "rev-parse", "--verify", "HEAD").strip()
    except ValueError:
        head = None
    try:
        branch = git(root, "symbolic-ref", "--quiet", "--short", "HEAD").strip()
    except ValueError:
        branch = None
    try:
        status = git(root, "status", "--porcelain=v1", "-z")
        paths = sorted(
            set(
                git(
                    root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"
                ).split("\0")
            )
            - {""}
        )
        issues, hashes, total = [], [], 0
        if len(paths) > MAX_FILES:
            issues.append("file_count_bound")
        for name in paths[:MAX_FILES]:
            f = root / name
            # Hash bytes only; do not return contents. Do not follow symlinks or read credentials.
            if (
                f.is_symlink()
                or not f.resolve().is_relative_to(root)
                or any(
                    ".env" in part.lower()
                    or any(
                        s in part.lower()
                        for s in ("credential", "secret", "id_rsa", "id_ed25519")
                    )
                    for part in Path(name).parts
                )
            ):
                hashes.append((name, "excluded"))
                issues.append("excluded_sensitive_or_symlink")
                continue
            try:
                if not f.exists():
                    hashes.append((name, "deleted"))
                    continue
                if not f.is_file() or f.stat().st_size > MAX_FILE_BYTES:
                    issues.append("file_size_or_type_bound")
                    continue
                before = f.stat()
                size = before.st_size
                if total + size > MAX_TOTAL_BYTES:
                    issues.append("total_bytes_bound")
                    break
                total += size
                with f.open("rb") as stream:
                    data = stream.read(MAX_FILE_BYTES + 1)
                if len(data) > MAX_FILE_BYTES:
                    issues.append("file_size_bound")
                    continue
                after = f.stat()
                if (before.st_size, before.st_mtime_ns) != (
                    after.st_size,
                    after.st_mtime_ns,
                ):
                    issues.append("changed_during_inspection")
                hashes.append((name, hashlib.sha256(data).hexdigest()))
            except OSError:
                issues.append("unreadable_file")
        material = json.dumps(
            [head, branch, status, hashes], ensure_ascii=True
        ).encode()
        return dict(
            info,
            head=head,
            branch=branch,
            dirty=bool(status),
            changed_paths=status.split("\0")[:100],
            files_checked=len(hashes),
            complete=not issues,
            issues=sorted(set(issues)),
            fingerprint=hashlib.sha256(material).hexdigest(),
        )
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return dict(info, complete=False, fingerprint=None, issues=["git_probe_failed"])
