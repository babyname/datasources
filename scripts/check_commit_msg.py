#!/usr/bin/env python3
"""Commit-message gate for datasources.

Same subject rule as fate/scripts/check_repo.py and qiming/scripts/check_arch.py:
Conventional Commit prefix, English (no CJK), LF line endings. Installed via
the commit-msg hook so a non-English subject cannot enter history at all.

Run:
    python3 scripts/check_commit_msg.py --file .git/COMMIT_EDITMSG
    python3 scripts/check_commit_msg.py --self-test
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CJK = re.compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")
CONVENTIONAL = re.compile(
    r"^(?:feat|fix|refactor|docs|chore|test|style|perf|ci|build|release)"
    r"(?:\([a-z0-9_.-]+\))?!?: .+"
)


def commit_msg_errors(raw: bytes) -> list[str]:
    subject = raw.split(b"\n", 1)[0].decode("utf-8", "replace").strip()
    bad: list[str] = []
    if b"\r" in raw:
        bad.append("CR byte in message")
    if not CONVENTIONAL.match(subject) or CJK.search(subject):
        bad.append(f"non-English/non-conventional subject: {subject!r}")
    return bad


def self_test() -> int:
    cases = [
        ("CJK subject must be rejected",
         "refactor(arch): \u56fa\u5316\u804c\u8d23\u5951\u7ea6".encode(), True),
        ("CR must be rejected", b"feat(data): add pipeline\r\n", True),
        ("non-conventional must be rejected", b"add pipeline\n", True),
        ("English conventional must be accepted",
         b"refactor(arch): codify role contract\n\nbody\n", False),
    ]
    failed = 0
    for name, raw, want_error in cases:
        got = bool(commit_msg_errors(raw))
        ok = got == want_error
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failed += 1
    return failed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", metavar="PATH", help="message file to validate")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        failed = self_test()
        print(f"== self-test: {'PASS' if failed == 0 else str(failed) + ' FAIL'} ==")
        return 1 if failed else 0

    if not args.file:
        ap.error("one of --file or --self-test is required")
    bad = commit_msg_errors(Path(args.file).read_bytes())
    if bad:
        for item in bad:
            print(f"FAIL  {item}")
        print("== commit message: FAIL ==")
        return 1
    print("PASS  commit message: English conventional subject, LF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
