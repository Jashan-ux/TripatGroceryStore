#!/usr/bin/env python3
"""Turn gitleaks output into GitHub annotations.

Step logs are not always downloadable from this environment, so the scan reports
through ``::error`` lines that always show up on the pull request. Takes the
findings report and the captured log from the working directory CI runs in.
"""

from __future__ import annotations

import json
import pathlib


def annotate(title: str, message: str) -> None:
    escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error title={title}::{escaped}")


def main() -> int:
    report = pathlib.Path("gitleaks-report.json")
    log = pathlib.Path("gitleaks-log.txt")

    findings: list[dict[str, object]] = []
    if report.exists() and report.stat().st_size:
        findings = json.loads(report.read_text() or "[]")

    for finding in findings:
        annotate(
            "gitleaks",
            f"{finding.get('RuleID')} in {finding.get('File')}:{finding.get('StartLine')}",
        )
    if findings:
        return 1

    if log.exists():
        lines = [line for line in log.read_text(errors="replace").splitlines() if line.strip()]
        for line in lines[-6:]:
            annotate("gitleaks log", line)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
