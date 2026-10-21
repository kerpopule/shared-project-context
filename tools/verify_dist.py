"""Inspect release archives. Usage: python3 tools/verify_dist.py DIST_DIR."""

import json
from pathlib import Path
import sys
import tarfile
import zipfile


def inspect(directory):
    directory = Path(directory)
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("exactly_one_wheel_and_source_required")
    with zipfile.ZipFile(wheels[0]) as archive:
        wheel_names = archive.namelist()
    with tarfile.open(sources[0]) as archive:
        source_names = archive.getnames()
    forbidden = {
        "node_modules",
        ".env",
        "context.sqlite3",
        "installation.json",
        "CHECKPOINT.md",
        ".venv",
        ".git",
    }
    for name in wheel_names + source_names:
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("unsafe_archive_path")
        if forbidden.intersection(Path(name).parts):
            raise ValueError("private_or_generated_archive_member")
    required = (
        "docs/UNIVERSAL.md",
        "docs/ROOMS.md",
        "docs/HTTP.md",
        "tests_http/test_transport.py",
        "tools/verify_http.py",
        "tools/probe_pi.mjs",
        "tools/verify_universal.py",
    )
    for name in required:
        if not any(member.endswith("/" + name) for member in source_names):
            raise ValueError("missing_distribution_member:" + name)
    for module in ("clients", "scope", "rooms", "http_transport"):
        if "shared_context/" + module + ".py" not in wheel_names:
            raise ValueError("missing_runtime_module:" + module)
    return {
        "archive_member_inspection": True,
        "wheel_members": len(wheel_names),
        "source_members": len(source_names),
    }


if __name__ == "__main__":
    print(json.dumps(inspect(sys.argv[1]), indent=2))
