"""Generate bounded build identity metadata for source and packaged builds."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


UNKNOWN = "unknown"


def _git_value(root, argv, runner=subprocess.run):
    try:
        result = runner(
            tuple(argv),
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def collect_build_info(
    root,
    *,
    environ=None,
    clock=None,
    runner=subprocess.run,
):
    root = Path(root).resolve()
    env = dict(os.environ if environ is None else environ)
    try:
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        version = UNKNOWN
    commit = env.get("SUS_ADB_REVISION") or _git_value(
        root, ("git", "rev-parse", "HEAD"), runner
    )
    ref = env.get("SUS_ADB_REF") or _git_value(
        root, ("git", "branch", "--show-current"), runner
    )
    if not ref:
        ref = _git_value(
            root, ("git", "describe", "--all", "--exact-match", "HEAD"), runner
        )
    timestamp = env.get("SUS_ADB_BUILD_TIMESTAMP")
    if not timestamp:
        now = clock() if clock else datetime.now(timezone.utc)
        timestamp = now.astimezone(timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")
    channel = env.get("SUS_ADB_BUILD_CHANNEL", "local")
    commit = commit or UNKNOWN
    return {
        "format": 1,
        "product": "SUS Companion",
        "version": version or UNKNOWN,
        "commit": commit,
        "short_commit": (
            commit[:12] if commit != UNKNOWN else UNKNOWN
        ),
        "ref": ref or UNKNOWN,
        "timestamp": timestamp,
        "channel": channel,
    }


def write_build_info(output, info):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(info, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    info = collect_build_info(args.root)
    write_build_info(args.output, info)
    print(json.dumps(info, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
